import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGODB_URL", "")
os.environ.setdefault("DATABASE_NAME", "ai_coding_mentor_test")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRATION_MINUTES", "60")

from app.main import app
from app.models.assessment_result import SkillLevel
from app.services import assessment as assessment_service
from app.services import assessment_results as result_service
from app.services.security import get_current_user


class FakeCursor(list):
    def sort(self, key, direction):
        return FakeCursor(sorted(self, key=lambda item: item[key], reverse=direction < 0))


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    def create_index(self, *_args, **_kwargs):
        return None

    def find_one(self, query, *_args, **_kwargs):
        return next((doc for doc in self.documents if _matches(doc, query)), None)

    def find(self, query, *_args, **_kwargs):
        return FakeCursor([doc for doc in self.documents if _matches(doc, query)])

    def insert_one(self, document):
        self.documents.append(document)


def _matches(document, query):
    return all(document.get(key) == value for key, value in query.items())


def _session(score=60, status="completed"):
    return {
        "session_id": "session-1",
        "user_id": "user-1",
        "language": "java",
        "status": status,
        "score": score,
        "started_at": datetime.now(timezone.utc),
        "question_metadata": [
            {"question_id": "q1", "topic": "arrays", "difficulty": "easy"},
            {"question_id": "q2", "topic": "arrays", "difficulty": "medium"},
            {"question_id": "q3", "topic": "strings", "difficulty": "easy"},
            {"question_id": "q4", "topic": "searching", "difficulty": "hard"},
        ],
    }


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, SkillLevel.BEGINNER),
        (39, SkillLevel.BEGINNER),
        (40, SkillLevel.INTERMEDIATE),
        (69, SkillLevel.INTERMEDIATE),
        (70, SkillLevel.ADVANCED),
        (100, SkillLevel.ADVANCED),
    ],
)
def test_skill_level_thresholds(score, expected):
    assert result_service.skill_level_for_score(score) == expected


def test_topic_scores_and_strong_weak_rules():
    scores = result_service._calculate_topic_scores(
        question_metadata=[
            {"question_id": "a1", "topic": "arrays", "difficulty": "easy"},
            {"question_id": "a2", "topic": "arrays", "difficulty": "medium"},
            {"question_id": "s1", "topic": "strings", "difficulty": "easy"},
            {"question_id": "l1", "topic": "loops", "difficulty": "easy"},
            {"question_id": "l2", "topic": "loops", "difficulty": "medium"},
        ],
        accepted_question_ids={"a1", "a2", "s1", "l1"},
    )
    assert scores == {"Arrays": 100, "Strings": 100, "Loops": 50}
    result = result_service._build_result(
        session={
            **_session(score=80),
            "question_metadata": [
                {"question_id": "a1", "topic": "arrays", "difficulty": "easy"},
                {"question_id": "s1", "topic": "strings", "difficulty": "easy"},
                {"question_id": "l1", "topic": "loops", "difficulty": "easy"},
                {"question_id": "l2", "topic": "loops", "difficulty": "medium"},
            ],
        },
        accepted_question_ids={"a1", "s1", "l1"},
    )
    assert result["strong_topics"] == ["Arrays", "Strings"]
    assert result["weak_topics"] == []
    assert result["recommended_next_topic"] == "Loops"


def test_weak_topic_and_tied_recommendation_are_deterministic():
    result = result_service._build_result(
        session={
            **_session(score=20),
            "question_metadata": [
                {"question_id": "first", "topic": "searching", "difficulty": "easy"},
                {"question_id": "second", "topic": "sorting", "difficulty": "easy"},
            ],
        },
        accepted_question_ids=set(),
    )
    assert result["topic_scores"] == {"Searching": 0, "Sorting": 0}
    assert result["weak_topics"] == ["Searching", "Sorting"]
    assert result["recommended_next_topic"] == "Searching"


def test_result_persists_once_and_repeats_same_document(monkeypatch):
    session = _session(score=50)
    sessions = FakeCollection([session])
    submissions = FakeCollection(
        [
            {"session_id": "session-1", "question_id": "q1", "status": "accepted"},
            {"session_id": "session-1", "question_id": "q3", "status": "accepted"},
        ]
    )
    results = FakeCollection()
    monkeypatch.setattr(assessment_service, "get_owned_session", lambda **_: session)
    monkeypatch.setattr(assessment_service, "get_assessment_submissions_collection", lambda: submissions)
    monkeypatch.setattr(result_service, "get_assessment_results_collection", lambda: results)

    first = result_service.get_or_create_result(session_id="session-1", user_id="user-1")
    second = result_service.get_or_create_result(session_id="session-1", user_id="user-1")
    assert first["result_id"] == second["result_id"]
    assert len(results.documents) == 1


def test_result_requires_completed_owned_session(monkeypatch):
    session = _session(status="in_progress")
    monkeypatch.setattr(assessment_service, "get_owned_session", lambda **_: session)
    with pytest.raises(assessment_service.AssessmentStateError):
        result_service.get_or_create_result(session_id="session-1", user_id="user-1")


def test_result_endpoint_requires_authentication():
    response = TestClient(app).get("/assessment/session-1/result")
    assert response.status_code == 401


def test_result_endpoint_rejects_another_users_session(monkeypatch):
    monkeypatch.setattr(
        assessment_service,
        "get_owned_session",
        lambda **_: (_ for _ in ()).throw(assessment_service.AssessmentNotFoundError("missing")),
    )
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-2"}
    try:
        response = TestClient(app).get("/assessment/session-1/result")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404


def test_result_endpoint_returns_persisted_report_and_history_is_user_scoped(monkeypatch):
    session = _session(score=70)
    results = FakeCollection()
    submissions = FakeCollection(
        [
            {"session_id": "session-1", "question_id": "q1", "status": "accepted"},
            {"session_id": "session-1", "question_id": "q3", "status": "accepted"},
        ]
    )
    monkeypatch.setattr(assessment_service, "get_owned_session", lambda **_: session)
    monkeypatch.setattr(assessment_service, "get_assessment_submissions_collection", lambda: submissions)
    monkeypatch.setattr(result_service, "get_assessment_results_collection", lambda: results)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1"}
    try:
        response = TestClient(app).get("/assessment/session-1/result")
        results.documents.append(
            {
                "session_id": "other-session",
                "user_id": "user-2",
                "language": "java",
                "overall_score": 100,
                "skill_level": "advanced",
                "created_at": datetime.now(timezone.utc),
            }
        )
        history = TestClient(app).get("/assessment/history")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["skill_level"] == "advanced"
    assert response.json()["recommended_next_topic"] == "Searching"
    assert history.status_code == 200
    assert [item["session_id"] for item in history.json()] == ["session-1"]
