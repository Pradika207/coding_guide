from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.models.language import ProgrammingLanguage


class Topic(str, Enum):
    FUNDAMENTALS = "fundamentals"
    VARIABLES = "variables"
    CONDITIONALS = "conditionals"
    LOOPS = "loops"
    FUNCTIONS = "functions"
    ARRAYS = "arrays"
    STRINGS = "strings"
    SEARCHING = "searching"
    SORTING = "sorting"
    RECURSION = "recursion"
    LINKED_LISTS = "linked_lists"
    STACK = "stack"
    QUEUE = "queue"
    HASHING = "hashing"
    TREES = "trees"
    GRAPHS = "graphs"
    DYNAMIC_PROGRAMMING = "dynamic_programming"
    OBJECT_ORIENTED_PROGRAMMING = "object_oriented_programming"

    @property
    def display_name(self) -> str:
        return self.value.replace("_", " ").title()


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionDocument:
    collection_name = "questions"

    @staticmethod
    def new(
        *,
        title: str,
        description: str,
        language: ProgrammingLanguage,
        topic: Topic,
        difficulty: Difficulty,
        sample_input: str,
        sample_output: str,
        test_cases: list[dict[str, Any]],
        constraints: list[str],
        time_limit: int,
        memory_limit: int,
        question_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "question_id": question_id or f"{language.value}-{topic.value}-{uuid4().hex[:10]}",
            "title": title,
            "description": description,
            "language": language.value,
            "topic": topic.value,
            "difficulty": difficulty.value,
            "sample_input": sample_input,
            "sample_output": sample_output,
            "test_cases": test_cases,
            "constraints": constraints,
            "time_limit": time_limit,
            "memory_limit": memory_limit,
            "created_at": datetime.now(timezone.utc),
        }

    @staticmethod
    def to_public(document: dict[str, Any]) -> dict[str, Any]:
        return {
            key: document[key]
            for key in (
                "question_id",
                "title",
                "description",
                "language",
                "topic",
                "difficulty",
                "sample_input",
                "sample_output",
                "constraints",
                "time_limit",
                "memory_limit",
                "created_at",
            )
        }
