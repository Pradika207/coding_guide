import os

import httpx
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGODB_URL", "")
os.environ.setdefault("DATABASE_NAME", "ai_coding_mentor_test")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRATION_MINUTES", "60")

from app.database.config import settings
from app.main import app
from app.models.language import ProgrammingLanguage
from app.services import judge0
from app.services.security import get_current_user


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, results):
        self.results = iter(results)
        self.submission_payload = None

    def post(self, path, *, params, json):
        self.submission_payload = {"path": path, "params": params, "json": json}
        return FakeResponse({"token": "submission-token"})

    def get(self, path, *, params):
        return FakeResponse(next(self.results))


def test_language_mapping_is_centralized():
    assert judge0.JUDGE0_LANGUAGE_IDS[ProgrammingLanguage.JAVA] == 62
    assert judge0.JUDGE0_LANGUAGE_IDS[ProgrammingLanguage.PYTHON] == 71


def test_submit_code_maps_application_language():
    client = FakeClient([])
    service = judge0.Judge0Service(client=client)
    token = service.submit_code(
        language=ProgrammingLanguage.CPP,
        source_code="int main() {}",
        stdin="",
    )
    assert token == "submission-token"
    assert client.submission_payload["json"]["language_id"] == 54
    assert client.submission_payload["params"]["wait"] == "false"


@pytest.mark.parametrize(
    ("status_id", "expected_status"),
    [
        (3, "accepted"),
        (4, "wrong_answer"),
        (5, "time_limit_exceeded"),
        (6, "compilation_error"),
        (7, "runtime_error"),
        (13, "internal_error"),
    ],
)
def test_normalize_execution_statuses(status_id, expected_status):
    result = judge0.normalize_result(
        {
            "status": {"id": status_id, "description": "status"},
            "stdout": "out",
            "stderr": "err",
            "compile_output": "compile",
            "time": "0.01",
            "memory": 12345,
        }
    )
    assert result.status == expected_status
    assert result.execution_time == 0.01
    assert result.memory == 12345


def test_normalize_memory_limit_status():
    result = judge0.normalize_result(
        {"status": {"id": 14, "description": "Memory Limit Exceeded"}}
    )
    assert result.status == "memory_limit_exceeded"


def test_execute_accepted_result():
    client = FakeClient(
        [
            {
                "status": {"id": 3, "description": "Accepted"},
                "stdout": "hello\n",
                "time": "0.01",
                "memory": 123,
            }
        ]
    )
    result = judge0.Judge0Service(client=client).execute_code(
        language=ProgrammingLanguage.PYTHON,
        source_code="print('hello')",
        stdin="",
    )
    assert result.status == "accepted"
    assert result.stdout == "hello\n"


def test_execute_polls_until_finished(monkeypatch):
    monkeypatch.setattr(settings, "judge0_poll_interval_seconds", 0)
    client = FakeClient(
        [
            {"status": {"id": 1, "description": "In Queue"}},
            {"status": {"id": 2, "description": "Processing"}},
            {"status": {"id": 3, "description": "Accepted"}},
        ]
    )
    result = judge0.Judge0Service(client=client).execute_code(
        language=ProgrammingLanguage.C,
        source_code="int main() { return 0; }",
        stdin="",
    )
    assert result.status == "accepted"


def test_execute_times_out(monkeypatch):
    monkeypatch.setattr(settings, "judge0_poll_interval_seconds", 0)
    monkeypatch.setattr(settings, "judge0_max_poll_attempts", 2)
    client = FakeClient(
        [
            {"status": {"id": 1, "description": "In Queue"}},
            {"status": {"id": 2, "description": "Processing"}},
        ]
    )
    with pytest.raises(judge0.Judge0TimeoutError):
        judge0.Judge0Service(client=client).execute_code(
            language=ProgrammingLanguage.JAVA,
            source_code="class Main {}",
            stdin="",
        )


def test_execute_endpoint_requires_authentication():
    client = TestClient(app)
    response = client.post(
        "/code/execute",
        json={"language": "python", "source_code": "print(1)", "stdin": ""},
    )
    assert response.status_code == 401


def test_execute_endpoint_valid_request(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "test-user"}
    monkeypatch.setattr(
        judge0,
        "execute_code",
        lambda **_: judge0.NormalizedExecutionResult(
            status="accepted",
            stdout="1\n",
            stderr="",
            compile_output="",
            execution_time=0.01,
            memory=100,
        ),
    )
    try:
        response = TestClient(app).post(
            "/code/execute",
            json={"language": "python", "source_code": "print(1)", "stdin": ""},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_execute_endpoint_rejects_unsupported_language():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "test-user"}
    try:
        response = TestClient(app).post(
            "/code/execute",
            json={"language": "rust", "source_code": "fn main() {}", "stdin": ""},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_execute_endpoint_rejects_missing_source_code():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "test-user"}
    try:
        response = TestClient(app).post(
            "/code/execute",
            json={"language": "python", "stdin": ""},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_execute_endpoint_rejects_oversized_source_code():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "test-user"}
    try:
        response = TestClient(app).post(
            "/code/execute",
            json={
                "language": "python",
                "source_code": "x" * (settings.max_source_code_bytes + 1),
                "stdin": "",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
