"""Resolve safe public question context and delegate to a tutor provider."""

from __future__ import annotations

import logging
from typing import Any, Callable

from pymongo.errors import PyMongoError

from app.models.language import ProgrammingLanguage
from app.models.question import Difficulty, Topic
from app.schemas.tutor import TutorRequest, TutorResponse
from app.services.questions import find_question
from app.services.tutor.rule_based_tutor import RuleBasedTutorProvider
from app.services.tutor.tutor_provider import TutorProvider

logger = logging.getLogger(__name__)


class TutorQuestionNotFoundError(LookupError):
    pass


class TutorQuestionAccessError(PermissionError):
    pass


class TutorQuestionStoreUnavailableError(RuntimeError):
    pass


class UnavailableLLMTutorProvider:
    """Future-provider placeholder; intentionally has no API client or key."""

    name = "llm_unavailable"

    def provide_hint(
        self,
        request: TutorRequest,
        *,
        hint_level: int | None = None,
        question_context: dict[str, Any] | None = None,
    ) -> TutorResponse:
        raise RuntimeError("LLM tutor provider is not implemented")


class TutorService:
    def __init__(
        self,
        provider: TutorProvider | None = None,
        *,
        question_lookup: Callable[[str], dict[str, Any] | None] = find_question,
        allow_unlisted_questions: bool = False,
    ) -> None:
        self._provider = provider or RuleBasedTutorProvider()
        self._question_lookup = question_lookup
        self._allow_unlisted_questions = allow_unlisted_questions

    @property
    def provider_name(self) -> str:
        return self._provider.name

    def provide_hint(self, request: TutorRequest, *, hint_level: int | None = None) -> TutorResponse:
        question = self._load_public_question(request)
        provider_request = request
        if question is not None:
            provider_request = request.model_copy(update={
                "topic": Topic(question["topic"]),
                "difficulty": Difficulty(question["difficulty"]),
            })
        try:
            return self._provider.provide_hint(
                provider_request,
                hint_level=hint_level,
                question_context=question,
            )
        except (ConnectionError, TimeoutError, RuntimeError) as error:
            if not isinstance(self._provider, RuleBasedTutorProvider):
                logger.warning("Configured tutor provider failed (%s); using rule-based fallback", type(error).__name__)
                return RuleBasedTutorProvider().provide_hint(
                    provider_request,
                    hint_level=hint_level,
                    question_context=question,
                )
            raise

    def _load_public_question(self, request: TutorRequest) -> dict[str, Any] | None:
        try:
            question = self._question_lookup(request.question_id)
        except (PyMongoError, RuntimeError) as error:
            raise TutorQuestionStoreUnavailableError("Question bank is unavailable") from error
        if question is None:
            if self._allow_unlisted_questions:
                return None
            raise TutorQuestionNotFoundError("Question not found")

        try:
            stored_language = ProgrammingLanguage(question["language"])
            stored_topic = Topic(question["topic"])
            stored_difficulty = Difficulty(question["difficulty"])
        except (KeyError, TypeError, ValueError) as error:
            raise TutorQuestionAccessError("Question context is invalid") from error
        if stored_language != request.language:
            raise TutorQuestionAccessError("Question language does not match the request")
        if stored_topic != request.topic or stored_difficulty != request.difficulty:
            raise TutorQuestionAccessError("Question topic or difficulty does not match the request")
        # Public question context is used only for safe existence/ownership checks.
        # Hidden test cases, evaluator state, sample outputs, and credentials are
        # never passed to a provider.
        return {
            "question_id": request.question_id,
            "title": str(question.get("title", "")),
            "description": str(question.get("description", "")),
            "language": stored_language.value,
            "topic": stored_topic.value,
            "difficulty": stored_difficulty.value,
            "constraints": list(question.get("constraints", [])),
        }


def build_tutor_provider(provider_name: str) -> TutorProvider:
    """Resolve provider configuration without initializing a network client."""
    if provider_name.strip().lower() in {"rule_based", "rules", ""}:
        return RuleBasedTutorProvider()
    if provider_name.strip().lower() == "llm":
        return UnavailableLLMTutorProvider()
    logger.warning("Tutor provider %s is unknown; using rule-based fallback", provider_name)
    return RuleBasedTutorProvider()
