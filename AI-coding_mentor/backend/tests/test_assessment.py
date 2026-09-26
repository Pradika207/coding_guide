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
from app.models.language import ProgrammingLanguage
from app.services import assessment as assessment_service
from app.services import judge0
from app.services import questions as question_service
from app.services.security import get_current_user


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    def create_index(self, *_args, **_kwargs):
        return None

    def insert_one(self, document):
        self.documents.append(document)

    def find_one(self, query, *_args, **_kwargs):
        return next((doc for doc in self.documents if _matches(doc, query)), None)

    def find(self, query, *_args, **_kwargs):
        return [doc for doc in self.documents if _matches(doc, query)]

    def count_documents(self, query):
        return sum(_matches(doc, query) for doc in self.documents)

    def update_one(self, query, update):
        document = self.find_one(query)
        if document:
            document.update(update.get("$set", {}))


def _matches(document, query):
    return all(document.get(key) == value for key, value in query.items())


def _question(question_id, language="java", topic="arrays", difficulty="easy"):
    return {
        "question_id": question_id,
        "title": question_id,
        "description": "Solve this coding problem.",
        "language": language,
        "topic": topic,
        "difficulty": difficulty,
        "sample_input": "1",
        "sample_output": "1",
        "constraints": ["1 <= n <= 10"],
        "test_cases": [
            {"input": "1", "expected_output": "1", "is_hidden": False},
            {"input": "2", "expected_output": "2", "is_hidden": True},
        ],
    }


def _result(status):
    return judge0.NormalizedExecutionResult(
        status=status,
        stdout="1\n",
        stderr="",
        compile_output="",
        execution_time=0.01,
        memory=100,
    )


def _authenticated_client(user_id="user-1", language="java"):
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": user_id,
        "selected_language": language,
    }
    return TestClient(app)


def test_assessment_start_requires_authentication():
    response = TestClient(app).post("/assessment/start")
    assert response.status_code == 401


def test_start_uses_selected_language_and_hides_tests(monkeypatch):
    sessions = FakeCollection()
    questions = [
        _question("q-easy-1", topic="arrays", difficulty="easy"),
        _question("q-easy-2", topic="strings", difficulty="easy"),
        _question("q-medium-1", topic="searching", difficulty="medium"),
        _question("q-medium-2", topic="sorting", difficulty="medium"),
        _question("q-hard-1", topic="recursion", difficulty="hard"),
    ]
    monkeypatch.setattr(assessment_service, "get_assessment_sessions_collection", lambda: sessions)
    monkeypatch.setattr(question_service, "find_questions", lambda **_: questions)
    client = _authenticated_client()
    try:
        response = client.post("/assessment/start")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "java"
    assert len(body["questions"]) == 5
    assert "test_cases" not in response.text
    assert sessions.documents[0]["question_ids"] == [question["question_id"] for question in questions]


def test_start_rejects_insufficient_question_bank(monkeypatch):
    sessions = FakeCollection()
    questions = [_question("q-easy", difficulty="easy")]
    monkeypatch.setattr(assessment_service, "get_assessment_sessions_collection", lambda: sessions)
    monkeypatch.setattr(question_service, "find_questions", lambda **_: questions)
    client = _authenticated_client()
    try:
        response = client.post("/assessment/start")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert sessions.documents == []


def test_submit_rejects_unknown_session(monkeypatch):
    monkeypatch.setattr(
        assessment_service,
        "get_owned_session",
        lambda **_: (_ for _ in ()).throw(assessment_service.AssessmentNotFoundError("missing")),
    )
    client = _authenticated_client()
    try:
        response = client.post(
            "/assessment/missing/submit",
            json={"question_id": "q1", "source_code": "class Main {}", "stdin": ""},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404


def test_submit_rejects_question_outside_session(monkeypatch):
    session = {"user_id": "user-1", "status": "in_progress", "question_ids": ["q1"]}
    monkeypatch.setattr(assessment_service, "get_owned_session", lambda **_: session)
    client = _authenticated_client()
    try:
        response = client.post(
            "/assessment/session-1/submit",
            json={"question_id": "q2", "source_code": "class Main {}", "stdin": ""},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_submit_supports_attempts_and_hidden_tests(monkeypatch):
    session = {
        "user_id": "user-1",
        "language": "java",
        "status": "in_progress",
        "question_ids": ["q1"],
    }
    submissions = FakeCollection()
    monkeypatch.setattr(assessment_service, "get_owned_session", lambda **_: session)
    monkeypatch.setattr(assessment_service, "get_assessment_submissions_collection", lambda: submissions)
    monkeypatch.setattr(question_service, "find_question", lambda _question_id: _question("q1"))
    results = iter([_result("wrong_answer"), _result("wrong_answer"), _result("accepted"), _result("accepted")])
    monkeypatch.setattr(judge0, "execute_code", lambda **_: next(results))
    client = _authenticated_client()
    try:
        first = client.post(
            "/assessment/session-1/submit",
            json={"question_id": "q1", "source_code": "class Main {}", "stdin": ""},
        )
        second = client.post(
            "/assessment/session-1/submit",
            json={"question_id": "q1", "source_code": "class Main {}", "stdin": ""},
        )
    finally:
        app.dependency_overrides.clear()
    assert first.status_code == 200
    assert first.json()["status"] == "wrong_answer"
    assert first.json()["attempt_number"] == 1
    assert second.status_code == 200
    assert second.json()["status"] == "accepted"
    assert second.json()["attempt_number"] == 2
    assert "is_hidden" not in second.text
    assert len(submissions.documents) == 2


def test_completed_session_rejects_submission(monkeypatch):
    session = {"user_id": "user-1", "status": "completed", "question_ids": ["q1"]}
    monkeypatch.setattr(assessment_service, "get_owned_session", lambda **_: session)
    client = _authenticated_client()
    try:
        response = client.post(
            "/assessment/session-1/submit",
            json={"question_id": "q1", "source_code": "class Main {}", "stdin": ""},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 409


def test_complete_calculates_score_and_solved_count(monkeypatch):
    session = {
        "session_id": "session-1",
        "user_id": "user-1",
        "language": "java",
        "status": "in_progress",
        "question_ids": ["q1", "q2", "q3"],
        "started_at": datetime.now(timezone.utc),
        "score": None,
    }
    sessions = FakeCollection([session])
    submissions = FakeCollection(
        [
            {"session_id": "session-1", "question_id": "q1", "status": "accepted"},
            {"session_id": "session-1", "question_id": "q2", "status": "wrong_answer"},
        ]
    )
    monkeypatch.setattr(assessment_service, "get_assessment_sessions_collection", lambda: sessions)
    monkeypatch.setattr(assessment_service, "get_assessment_submissions_collection", lambda: submissions)
    client = _authenticated_client()
    try:
        response = client.post("/assessment/session-1/complete")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {
        "session_id": "session-1",
        "status": "completed",
        "score": 33,
        "total_questions": 3,
        "solved_questions": 1,
        "accuracy": 33,
        "language": "java",
    }
    assert session["status"] == "completed"


def test_complete_rejects_second_completion(monkeypatch):
    session = {
        "session_id": "session-1",
        "user_id": "user-1",
        "language": "java",
        "status": "completed",
        "question_ids": ["q1"],
        "started_at": datetime.now(timezone.utc),
    }
    monkeypatch.setattr(
        assessment_service,
        "get_assessment_sessions_collection",
        lambda: FakeCollection([session]),
    )
    client = _authenticated_client()
    try:
        response = client.post("/assessment/session-1/complete")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 409
