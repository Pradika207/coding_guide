import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGODB_URL", "")
os.environ.setdefault("DATABASE_NAME", "ai_coding_mentor_test")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRATION_MINUTES", "60")

from app.main import app
from app.models.roadmap import TOPIC_ORDER
from app.services import assessment_results as result_service
from app.services import roadmap as roadmap_service
from app.services.security import get_current_user


class FakeCursor(list):
    def sort(self, key, direction):
        return FakeCursor(sorted(self, key=lambda item: item[key], reverse=direction < 0))


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    def create_index(self, *_args, **_kwargs):
        return None

    def find_one(self, query, *_args, **kwargs):
        matches = [doc for doc in self.documents if _matches(doc, query)]
        if kwargs.get("sort") and matches:
            key, direction = kwargs["sort"][0]
            matches.sort(key=lambda item: item[key], reverse=direction < 0)
        return matches[0] if matches else None

    def find(self, query, *_args, **_kwargs):
        return FakeCursor([doc for doc in self.documents if _matches(doc, query)])

    def insert_one(self, document):
        self.documents.append(document)

    def update_one(self, query, update):
        document = self.find_one(query)
        if document:
            document.update(update.get("$set", {}))


def _matches(document, query):
    return all(document.get(key) == value for key, value in query.items())


def _result(session_id, created_at, *, user_id="user-1", score=40, recommended="Sorting", topic_scores=None):
    return {
        "result_id": f"result-{session_id}",
        "session_id": session_id,
        "user_id": user_id,
        "language": "java",
        "overall_score": score,
        "accuracy": score,
        "skill_level": "intermediate",
        "topic_scores": topic_scores or {"Fundamentals": 90, "Variables": 20, "Sorting": 10},
        "strong_topics": ["Fundamentals"],
        "weak_topics": ["Variables", "Sorting"],
        "recommended_next_topic": recommended,
        "created_at": created_at,
    }


def _authenticated_client(user_id="user-1"):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}
    return TestClient(app)


def test_roadmap_requires_authentication():
    response = TestClient(app).get("/roadmap")
    assert response.status_code == 401


def test_no_assessment_rejects_generation(monkeypatch):
    monkeypatch.setattr(result_service, "get_assessment_results_collection", lambda: FakeCollection())
    client = _authenticated_client()
    try:
        response = client.post("/roadmap/generate")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 400
    assert "Complete an assessment" in response.json()["detail"]


def test_personalized_roadmap_marks_strong_and_recommended_topics(monkeypatch):
    now = datetime.now(timezone.utc)
    result = _result(
        "session-1",
        now,
        score=70,
        recommended="Sorting",
        topic_scores={"Fundamentals": 90, "Variables": 20, "Sorting": 10},
    )
    results = FakeCollection([result])
    roadmaps = FakeCollection()
    monkeypatch.setattr(result_service, "get_assessment_results_collection", lambda: results)
    monkeypatch.setattr(roadmap_service, "get_roadmaps_collection", lambda: roadmaps)
    client = _authenticated_client()
    try:
        response = client.post("/roadmap/generate")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    by_topic = {topic["topic"]: topic for topic in body["topics"]}
    assert body["language"] == "java"
    assert body["current_topic"] == "Sorting"
    assert by_topic["Fundamentals"]["status"] == "completed"
    assert by_topic["Sorting"]["status"] == "recommended"
    assert by_topic["Sorting"]["score"] == 10
    assert by_topic["Graphs"]["status"] == "locked"
    assert len(body["topics"]) == len(TOPIC_ORDER)


def test_unlocking_follows_completed_prerequisites():
    result = _result(
        "session-1",
        datetime.now(timezone.utc),
        topic_scores={"Fundamentals": 90},
        recommended="Variables",
    )
    topics, current = roadmap_service._topic_statuses(result)
    assert topics[0]["status"] == "completed"
    assert topics[1]["status"] == "recommended"
    assert topics[2]["status"] == "locked"
    assert current == "Variables"


def test_completed_recommendation_uses_next_incomplete_topic():
    result = _result(
        "session-1",
        datetime.now(timezone.utc),
        topic_scores={"Fundamentals": 90, "Variables": 90},
        recommended="Variables",
    )
    topics, current = roadmap_service._topic_statuses(result)
    assert topics[0]["status"] == "completed"
    assert topics[1]["status"] == "completed"
    assert topics[2]["status"] == "recommended"
    assert current == "Conditionals"


def test_latest_assessment_is_selected_and_newer_generation_replaces_active(monkeypatch):
    old = _result("old", datetime.now(timezone.utc) - timedelta(days=1), recommended="Variables")
    new = _result("new", datetime.now(timezone.utc), score=80, recommended="Sorting")
    results = FakeCollection([old, new])
    roadmaps = FakeCollection()
    monkeypatch.setattr(result_service, "get_assessment_results_collection", lambda: results)
    monkeypatch.setattr(roadmap_service, "get_roadmaps_collection", lambda: roadmaps)
    first = roadmap_service.generate_roadmap(user_id="user-1")
    second = roadmap_service.generate_roadmap(user_id="user-1")
    assert first["source_assessment_id"] == "new"
    assert second["roadmap_id"] == first["roadmap_id"]
    assert len(roadmaps.documents) == 1


def test_history_or_roadmap_cannot_cross_users(monkeypatch):
    result = _result("other", datetime.now(timezone.utc), user_id="user-2")
    monkeypatch.setattr(result_service, "get_assessment_results_collection", lambda: FakeCollection([result]))
    client = _authenticated_client(user_id="user-1")
    try:
        response = client.post("/roadmap/generate")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 400


def test_get_and_current_roadmap_return_own_data(monkeypatch):
    result = _result("session-1", datetime.now(timezone.utc))
    results = FakeCollection([result])
    roadmaps = FakeCollection()
    monkeypatch.setattr(result_service, "get_assessment_results_collection", lambda: results)
    monkeypatch.setattr(roadmap_service, "get_roadmaps_collection", lambda: roadmaps)
    client = _authenticated_client()
    try:
        generated = client.post("/roadmap/generate")
        fetched = client.get("/roadmap")
        current = client.get("/roadmap/current")
    finally:
        app.dependency_overrides.clear()
    assert generated.status_code == 200
    assert fetched.status_code == 200
    assert current.status_code == 200
    assert current.json()["topic"] == generated.json()["current_topic"]
    assert current.json()["status"] == "recommended"
