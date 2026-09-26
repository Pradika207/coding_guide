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
from app.models.lesson import LessonProgressStatus
from app.models.language import ProgrammingLanguage
from app.models.question import Topic
from app.services import lesson_seed
from app.services import lessons as lesson_service
from app.services import roadmap as roadmap_service
from app.services.security import get_current_user


class FakeCursor(list):
    def sort(self, key, direction):
        return FakeCursor(sorted(self, key=lambda item: item[key], reverse=direction < 0))


class FakeUpdateResult:
    def __init__(self, inserted=False):
        self.upserted_id = "new" if inserted else None


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    def create_index(self, *_args, **_kwargs):
        return None

    def find(self, query, *_args, **_kwargs):
        return FakeCursor([doc for doc in self.documents if _matches(doc, query)])

    def find_one(self, query, *_args, **_kwargs):
        return next((doc for doc in self.documents if _matches(doc, query)), None)

    def insert_one(self, document):
        self.documents.append(document)

    def update_one(self, query, update, upsert=False):
        document = self.find_one(query)
        if document:
            document.update(update.get("$set", {}))
            return FakeUpdateResult()
        if upsert:
            inserted = dict(update.get("$setOnInsert", {}))
            if not inserted:
                inserted = dict(query)
                inserted.update(update.get("$set", {}))
            self.documents.append(inserted)
            return FakeUpdateResult(inserted=True)
        return FakeUpdateResult()


def _matches(document, query):
    return all(document.get(key) == value for key, value in query.items())


def _lesson(lesson_id="java-arrays-01", topic="arrays", language="java", order=1):
    return {
        "lesson_id": lesson_id,
        "language": language,
        "topic": topic,
        "title": "Introduction to Arrays",
        "description": "Learn arrays.",
        "order": order,
        "content": [
            {"type": "concept", "title": "Concept", "text": "Arrays group values."},
            {"type": "example", "title": "Example", "text": "int[] values = {1, 2};"},
        ],
        "quiz_ids": ["quiz-1"],
        "question_ids": ["java-arrays-001"],
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }


def _roadmap(topic_status="recommended", current_topic="Arrays"):
    topics = [
        {"topic": "Fundamentals", "order": 1, "status": "completed", "score": 90},
        {"topic": "Arrays", "order": 6, "status": topic_status, "score": 20},
        {"topic": "Graphs", "order": 16, "status": "locked", "score": None},
    ]
    return {"language": "java", "current_topic": current_topic, "topics": topics}


def _authenticated_client(user_id="user-1"):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}
    return TestClient(app)


def _patch_content(monkeypatch, *, roadmap=None, lessons=None, progress=None, quizzes=None):
    monkeypatch.setattr(roadmap_service, "get_roadmap", lambda **_: roadmap or _roadmap())
    monkeypatch.setattr(lesson_service, "get_lessons_collection", lambda: lessons or FakeCollection([_lesson()]))
    monkeypatch.setattr(lesson_service, "get_progress_collection", lambda: progress or FakeCollection())
    monkeypatch.setattr(lesson_service, "get_quizzes_collection", lambda: quizzes or FakeCollection())


def test_lessons_require_authentication():
    assert TestClient(app).get("/lessons").status_code == 401


def test_list_filters_and_single_lesson(monkeypatch):
    lessons = FakeCollection([_lesson(), _lesson("python-arrays-01", language="python")])
    _patch_content(monkeypatch, lessons=lessons)
    client = _authenticated_client()
    try:
        filtered = client.get("/lessons?language=java&topic=Arrays")
        single = client.get("/lessons/java-arrays-01")
    finally:
        app.dependency_overrides.clear()
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["topic"] == "Arrays"
    assert single.status_code == 200
    assert "quiz_ids" not in single.text
    assert single.json()["content"][0]["type"] == "concept"


def test_locked_topic_is_rejected(monkeypatch):
    _patch_content(monkeypatch, roadmap=_roadmap(topic_status="locked"))
    client = _authenticated_client()
    try:
        response = client.get("/lessons/java-arrays-01")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403


def test_start_lesson_is_idempotent_and_complete_is_safe(monkeypatch):
    lessons = FakeCollection([_lesson()])
    progress = FakeCollection()
    _patch_content(monkeypatch, lessons=lessons, progress=progress)
    client = _authenticated_client()
    try:
        first = client.post("/lessons/java-arrays-01/start")
        second = client.post("/lessons/java-arrays-01/start")
        completed = client.post("/lessons/java-arrays-01/complete")
        completed_again = client.post("/lessons/java-arrays-01/complete")
    finally:
        app.dependency_overrides.clear()
    assert first.status_code == 200
    assert second.status_code == 200
    assert len(progress.documents) == 1
    assert completed.json()["status"] == LessonProgressStatus.COMPLETED.value
    assert completed_again.json()["status"] == LessonProgressStatus.COMPLETED.value


def test_progress_is_user_scoped(monkeypatch):
    lessons = FakeCollection([_lesson()])
    progress = FakeCollection()
    _patch_content(monkeypatch, lessons=lessons, progress=progress)
    first = _authenticated_client("user-1")
    try:
        assert first.post("/lessons/java-arrays-01/start").status_code == 200
    finally:
        app.dependency_overrides.clear()
    second = _authenticated_client("user-2")
    try:
        response = second.post("/lessons/java-arrays-01/complete")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert len(progress.documents) == 2
    assert {item["user_id"] for item in progress.documents} == {"user-1", "user-2"}


def test_current_lesson_returns_first_incomplete(monkeypatch):
    lessons = FakeCollection([_lesson("java-arrays-01", order=1), _lesson("java-arrays-02", order=2)])
    progress = FakeCollection(
        [{"user_id": "user-1", "lesson_id": "java-arrays-01", "status": "completed"}]
    )
    _patch_content(monkeypatch, lessons=lessons, progress=progress)
    client = _authenticated_client()
    try:
        response = client.get("/lessons/current")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["lesson_id"] == "java-arrays-02"


def test_current_lesson_without_content_is_clear(monkeypatch):
    _patch_content(monkeypatch, lessons=FakeCollection())
    client = _authenticated_client()
    try:
        response = client.get("/lessons/current")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404
    assert "not currently available" in response.json()["detail"]


def test_quiz_hides_answer_and_explanation(monkeypatch):
    quizzes = FakeCollection(
        [{
            "quiz_id": "quiz-1",
            "lesson_id": "java-arrays-01",
            "question": "What is an array?",
            "options": ["A", "B", "C", "D"],
            "correct_option": "A",
            "explanation": "It stores multiple values.",
        }]
    )
    _patch_content(monkeypatch, quizzes=quizzes)
    client = _authenticated_client()
    try:
        response = client.get("/lessons/java-arrays-01/quiz")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["options"] == ["A", "B", "C", "D"]
    assert "correct_option" not in response.text
    assert "explanation" not in response.text


def test_seed_catalog_is_small_and_reusable():
    assert len(lesson_seed.SAMPLE_LESSONS) == 18
    assert {lesson["language"] for lesson in lesson_seed.SAMPLE_LESSONS} == {"java", "python"}
    assert {lesson["topic"] for lesson in lesson_seed.SAMPLE_LESSONS} >= {"fundamentals", "variables", "loops", "arrays", "strings", "sorting"}
    assert all({item["type"] for item in lesson["content"]} >= {"concept", "example", "tip", "summary"} for lesson in lesson_seed.SAMPLE_LESSONS)
