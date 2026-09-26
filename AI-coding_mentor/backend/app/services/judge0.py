import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.database.config import settings
from app.models.language import ProgrammingLanguage

JUDGE0_LANGUAGE_IDS: dict[ProgrammingLanguage, int] = {
    ProgrammingLanguage.C: 50,
    ProgrammingLanguage.CPP: 54,
    ProgrammingLanguage.JAVA: 62,
    ProgrammingLanguage.JAVASCRIPT: 63,
    ProgrammingLanguage.PYTHON: 71,
}

_STATUS_BY_ID = {
    1: "pending",
    2: "processing",
    3: "accepted",
    4: "wrong_answer",
    5: "time_limit_exceeded",
    6: "compilation_error",
    7: "runtime_error",
    8: "runtime_error",
    9: "runtime_error",
    10: "runtime_error",
    11: "runtime_error",
    12: "runtime_error",
    13: "internal_error",
    14: "internal_error",
}


class Judge0ConfigurationError(RuntimeError):
    pass


class Judge0RequestError(RuntimeError):
    pass


class Judge0TimeoutError(RuntimeError):
    pass


@dataclass(frozen=True)
class NormalizedExecutionResult:
    status: str
    stdout: str
    stderr: str
    compile_output: str
    execution_time: float | None
    memory: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "compile_output": self.compile_output,
            "execution_time": self.execution_time,
            "memory": self.memory,
        }


def normalize_result(result: dict[str, Any]) -> NormalizedExecutionResult:
    status_data = result.get("status") or {}
    status_id = status_data.get("id")
    description = str(status_data.get("description") or "").lower()

    if "memory limit" in description:
        status = "memory_limit_exceeded"
    else:
        status = _STATUS_BY_ID.get(status_id, "internal_error")

    raw_time = result.get("time")
    try:
        execution_time = float(raw_time) if raw_time is not None else None
    except (TypeError, ValueError):
        execution_time = None

    raw_memory = result.get("memory")
    try:
        memory = int(raw_memory) if raw_memory is not None else None
    except (TypeError, ValueError):
        memory = None

    return NormalizedExecutionResult(
        status=status,
        stdout=str(result.get("stdout") or ""),
        stderr=str(result.get("stderr") or ""),
        compile_output=str(result.get("compile_output") or ""),
        execution_time=execution_time,
        memory=memory,
    )


class Judge0Service:
    def __init__(self, client: httpx.Client | None = None):
        if client is None and not settings.judge0_url:
            raise Judge0ConfigurationError("JUDGE0_URL is not configured")

        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=settings.judge0_url.rstrip("/"),
            headers=self._headers(),
            timeout=settings.judge0_request_timeout_seconds,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    @staticmethod
    def _headers() -> dict[str, str]:
        if settings.judge0_api_key:
            return {"X-Auth-Token": settings.judge0_api_key}
        return {}

    def submit_code(
        self,
        *,
        language: ProgrammingLanguage,
        source_code: str,
        stdin: str,
        expected_output: str | None = None,
    ) -> str:
        submission = {
            "language_id": JUDGE0_LANGUAGE_IDS[language],
            "source_code": source_code,
            "stdin": stdin,
        }
        if expected_output is not None:
            submission["expected_output"] = expected_output

        try:
            response = self._client.post(
                "/submissions",
                params={"base64_encoded": "false", "wait": "false"},
                json=submission,
            )
            response.raise_for_status()
            token = response.json().get("token")
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise Judge0RequestError("Judge0 submission failed") from error

        if not isinstance(token, str) or not token:
            raise Judge0RequestError("Judge0 did not return a submission token")
        return token

    def get_submission_result(self, token: str) -> dict[str, Any]:
        try:
            response = self._client.get(
                f"/submissions/{token}",
                params={"base64_encoded": "false"},
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise Judge0RequestError("Judge0 result request failed") from error

        if not isinstance(result, dict):
            raise Judge0RequestError("Judge0 returned an invalid result")
        return result

    def execute_code(
        self,
        *,
        language: ProgrammingLanguage,
        source_code: str,
        stdin: str,
        expected_output: str | None = None,
    ) -> NormalizedExecutionResult:
        token = self.submit_code(
            language=language,
            source_code=source_code,
            stdin=stdin,
            expected_output=expected_output,
        )

        for attempt in range(settings.judge0_max_poll_attempts):
            result = self.get_submission_result(token)
            normalized = normalize_result(result)
            if normalized.status not in {"pending", "processing"}:
                return normalized
            if attempt + 1 < settings.judge0_max_poll_attempts:
                time.sleep(settings.judge0_poll_interval_seconds)

        raise Judge0TimeoutError("Judge0 execution timed out while processing")


def submit_code(
    *,
    language: ProgrammingLanguage,
    source_code: str,
    stdin: str,
    expected_output: str | None = None,
) -> str:
    service = Judge0Service()
    try:
        return service.submit_code(
            language=language,
            source_code=source_code,
            stdin=stdin,
            expected_output=expected_output,
        )
    finally:
        service.close()


def get_submission_result(token: str) -> dict[str, Any]:
    service = Judge0Service()
    try:
        return service.get_submission_result(token)
    finally:
        service.close()


def execute_code(
    *,
    language: ProgrammingLanguage,
    source_code: str,
    stdin: str,
    expected_output: str | None = None,
) -> NormalizedExecutionResult:
    service = Judge0Service()
    try:
        return service.execute_code(
            language=language,
            source_code=source_code,
            stdin=stdin,
            expected_output=expected_output,
        )
    finally:
        service.close()
