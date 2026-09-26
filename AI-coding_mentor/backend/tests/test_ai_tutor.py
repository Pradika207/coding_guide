import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.language import ProgrammingLanguage
from app.models.question import Difficulty, Topic
from app.routes import tutor as tutor_routes
from app.schemas.tutor import TutorRequest
from app.services import security
from app.services.tutor.rule_based_tutor import RuleBasedTutorProvider
from app.services.tutor.tutor_service import (
    TutorQuestionAccessError,
    TutorQuestionNotFoundError,
    TutorService,
    build_tutor_provider,
)


def _payload(**updates):
    request = {
        "question_id": "q-arrays-1",
        "language": "python",
        "code": "def solve(values):\n    return values[0]\n",
        "submission_status": "wrong_answer",
        "compiler_error": None,
        "runtime_error": None,
        "topic": "arrays",
        "difficulty": "easy",
        "hint_level": 1,
    }
    request.update(updates)
    return request


def _request(**updates):
    return TutorRequest.model_validate(_payload(**updates))


def _question(**updates):
    question = {
        "question_id": "q-arrays-1",
        "title": "Find the maximum",
        "description": "Return the largest array value.",
        "language": "python",
        "topic": "arrays",
        "difficulty": "easy",
        "sample_input": "3 1 4",
        "sample_output": "4",
        "constraints": ["At least one value"],
        "test_cases": [{"input": "private", "expected_output": "secret", "is_hidden": True}],
        "hidden_expected_output": "secret",
        "evaluator_notes": "private evaluator detail",
    }
    question.update(updates)
    return question


def test_tutor_request_validates_supported_types_and_defaults():
    request = TutorRequest.model_validate(_payload())

    assert request.language is ProgrammingLanguage.PYTHON
    assert request.topic is Topic.ARRAYS
    assert request.difficulty is Difficulty.EASY
    assert request.hint_level == 1


@pytest.mark.parametrize(
    "updates",
    [
        {"question_id": ""},
        {"language": "rust"},
        {"topic": "invented_topic"},
        {"difficulty": "expert"},
        {"hint_level": 0},
        {"hint_level": 5},
        {"submission_status": "unknown"},
        {"hidden_test_cases": [{"input": "private"}]},
        {"hidden_expected_output": "secret"},
        {"model_path": "C:/private/model.joblib"},
        {"authorization": "Bearer private"},
    ],
)
def test_tutor_request_rejects_invalid_or_untrusted_fields(updates):
    with pytest.raises(ValidationError):
        TutorRequest.model_validate(_payload(**updates))


def test_tutor_request_enforces_code_length_limit():
    with pytest.raises(ValidationError):
        TutorRequest.model_validate(_payload(code="x" * 50001))


def test_rule_provider_returns_progressive_array_hints():
    provider = RuleBasedTutorProvider()
    responses = [provider.provide_hint(_request(hint_level=level)) for level in range(1, 5)]

    assert [response.hint_level for response in responses] == [1, 2, 3, 4]
    assert responses[0].concept == "Array traversal"
    assert responses[0].provider == "rule_based"
    assert responses[0].can_request_next_hint is True
    assert responses[-1].can_request_next_hint is False
    assert len({response.hint for response in responses}) == 4
    assert all("def " not in response.hint for response in responses)


def test_compilation_error_mapping_handles_common_language_errors():
    provider = RuleBasedTutorProvider()
    cases = [
        ("ArrayIndexOutOfBoundsException: index 3", "index"),
        ("SyntaxError: invalid syntax", "syntax"),
        ("NameError: name x is not defined", "scope"),
        ("TypeError: unsupported operand", "types"),
    ]
    for error, expected in cases:
        response = provider.provide_hint(_request(submission_status="compilation_error", compiler_error=error))
        assert expected in (response.hint + response.explanation + response.next_step).lower()


def test_runtime_error_mapping_covers_bounds_null_division_and_recursion():
    provider = RuleBasedTutorProvider()
    cases = [
        ("IndexError: list index out of range", "index"),
        ("NullPointerException", "initialized"),
        ("ZeroDivisionError: division by zero", "divisor"),
        ("StackOverflowError: recursion depth", "base case"),
    ]
    for error, expected in cases:
        response = provider.provide_hint(_request(submission_status="runtime_error", runtime_error=error))
        assert expected in (response.hint + response.explanation + response.next_step).lower()


def test_wrong_answer_and_accepted_statuses_are_educational():
    provider = RuleBasedTutorProvider()
    wrong = provider.provide_hint(_request(submission_status="wrong_answer", topic="loops"))
    accepted = provider.provide_hint(_request(submission_status="accepted", topic="sorting"))

    assert "ran" in wrong.explanation
    assert "loop" in wrong.concept.lower()
    assert "passed" in accepted.explanation
    assert "complexity" in accepted.next_step.lower() or "constraints" in accepted.next_step.lower()


def test_topic_specific_guidance_includes_loop_sort_and_recursion():
    provider = RuleBasedTutorProvider()
    expected = {
        "loops": "stopping condition",
        "sorting": "comparison direction",
        "recursion": "base case",
    }
    for topic, clue in expected.items():
        request = _request(topic=topic, hint_level=3)
        response = provider.provide_hint(request)
        assert clue in response.hint.lower()


def test_code_heuristic_identifies_possible_off_by_one_without_echoing_code():
    private_code = "for i in range(len(values) + 1): # private marker"
    response = RuleBasedTutorProvider().provide_hint(
        _request(code=private_code, topic="arrays", hint_level=2)
    )

    assert "one past" in response.hint.lower()
    assert private_code not in response.model_dump_json()
    assert "private marker" not in response.model_dump_json()


def test_all_supported_topics_have_deterministic_guidance():
    provider = RuleBasedTutorProvider()
    for topic in Topic:
        request = _request(topic=topic.value)
        assert provider.provide_hint(request).concept


def test_unknown_error_text_is_not_echoed_into_response():
    secret_diagnostic = "private path C:/users/name/source.py and code token MY_PERSONAL_DATA"
    response = RuleBasedTutorProvider().provide_hint(
        _request(submission_status="compilation_error", compiler_error=secret_diagnostic)
    )

    combined = response.model_dump_json()
    assert secret_diagnostic not in combined
    assert "MY_PERSONAL_DATA" not in combined
    assert "C:/users/name" not in combined


def test_question_context_is_required_and_hidden_fields_never_reach_provider():
    observed = {}

    class CapturingProvider:
        name = "capture"

        def provide_hint(self, request, *, hint_level=None, question_context=None):
            observed["request"] = request
            observed["question_context"] = question_context
            return RuleBasedTutorProvider().provide_hint(request, hint_level=hint_level)

    service = TutorService(CapturingProvider(), question_lookup=lambda _: _question())
    service.provide_hint(_request())

    assert observed["request"].question_id == "q-arrays-1"
    assert set(observed["question_context"]) == {
        "question_id", "title", "description", "language", "topic", "difficulty", "constraints"
    }
    assert not hasattr(observed["request"], "hidden_test_cases")
    assert "secret" not in json.dumps(observed["request"].model_dump(), default=str)
    assert "private evaluator" not in json.dumps(observed["request"].model_dump(), default=str)


def test_safe_public_question_description_can_inform_hint():
    service = TutorService(question_lookup=lambda _: _question())
    response = service.provide_hint(_request(hint_level=2))

    assert "best value seen so far" in response.hint


def test_missing_question_and_mismatched_question_context_are_rejected():
    service = TutorService(question_lookup=lambda _: None)
    with pytest.raises(TutorQuestionNotFoundError):
        service.provide_hint(_request())

    mismatched = TutorService(question_lookup=lambda _: _question(topic="sorting"))
    with pytest.raises(TutorQuestionAccessError):
        mismatched.provide_hint(_request())


def test_llm_configuration_falls_back_without_client_or_credentials():
    provider = build_tutor_provider("llm")
    service = TutorService(provider, question_lookup=lambda _: _question())

    response = service.provide_hint(_request())

    assert response.provider == "rule_based"
    assert response.hint_level == 1


def test_unknown_provider_configuration_selects_rules():
    assert isinstance(build_tutor_provider("not-configured"), RuleBasedTutorProvider)


@pytest.fixture
def authenticated_tutor_client(monkeypatch):
    user = {"user_id": "tutor-user", "selected_language": "python"}
    monkeypatch.setattr(security, "get_database", lambda: type("DB", (), {
        "users": type("Users", (), {"find_one": staticmethod(lambda query: user if query.get("user_id") == user["user_id"] else None)})()
    })())
    monkeypatch.setattr(security.settings, "jwt_secret", "tutor-tests-only-jwt-secret-key-32-bytes")
    service = TutorService(question_lookup=lambda _: _question())
    monkeypatch.setitem(app.dependency_overrides, tutor_routes.get_tutor_service, lambda: service)
    token = security.create_access_token(user["user_id"])
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


def test_hint_endpoint_requires_authentication():
    response = TestClient(app).post("/tutor/hint", json=_payload())

    assert response.status_code == 401


def test_authenticated_hint_endpoint_returns_tutor_response(authenticated_tutor_client):
    response = authenticated_tutor_client.post("/tutor/hint", json=_payload())

    assert response.status_code == 200
    assert response.json()["hint_level"] == 1
    assert response.json()["provider"] == "rule_based"


def test_next_hint_progresses_and_stops_at_maximum(authenticated_tutor_client):
    first = authenticated_tutor_client.post("/tutor/hint", json=_payload()).json()
    next_response = authenticated_tutor_client.post("/tutor/next-hint", json=_payload()).json()
    final_payload = _payload(hint_level=4)
    final_response = authenticated_tutor_client.post("/tutor/next-hint", json=final_payload)

    assert first["hint_level"] == 1
    assert next_response["hint_level"] == 2
    assert final_response.status_code == 409


def test_endpoint_does_not_echo_hidden_data_or_source_code(authenticated_tutor_client):
    payload = _payload(code="private code marker student_email@example.com")
    payload["compiler_error"] = "Compiler error at private path C:/private/source.py"

    response = authenticated_tutor_client.post("/tutor/hint", json=payload)

    assert response.status_code == 200
    assert "student_email@example.com" not in response.text
    assert "C:/private/source.py" not in response.text
    assert "hidden_test_cases" not in response.text


def test_tutor_does_not_log_submitted_code(caplog):
    code = "UNIQUE_PRIVATE_CODE_MARKER_7913"
    service = TutorService(question_lookup=lambda _: _question())

    with caplog.at_level("DEBUG"):
        service.provide_hint(_request(code=code))

    assert code not in caplog.text
