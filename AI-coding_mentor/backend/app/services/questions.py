from typing import Any

from pymongo.collection import Collection

from app.database.mongodb import get_database
from app.models.question import Difficulty, QuestionDocument, Topic
from app.models.language import ProgrammingLanguage
from app.schemas.question import QuestionCreate


def get_questions_collection() -> Collection:
    database = get_database()
    questions = database[QuestionDocument.collection_name]
    questions.create_index("language")
    questions.create_index("topic")
    questions.create_index("difficulty")
    questions.create_index([("language", 1), ("topic", 1), ("difficulty", 1)])
    return questions


def create_question(request: QuestionCreate) -> dict[str, Any]:
    question = QuestionDocument.new(
        title=request.title.strip(),
        description=request.description.strip(),
        language=request.language,
        topic=request.topic,
        difficulty=request.difficulty,
        sample_input=request.sample_input,
        sample_output=request.sample_output,
        test_cases=[test_case.model_dump() for test_case in request.test_cases],
        constraints=[constraint.strip() for constraint in request.constraints],
        time_limit=request.time_limit,
        memory_limit=request.memory_limit,
    )
    get_questions_collection().insert_one(question)
    return question


def find_questions(
    *,
    language: ProgrammingLanguage | None = None,
    topic: Topic | None = None,
    difficulty: Difficulty | None = None,
) -> list[dict[str, Any]]:
    filters: dict[str, str] = {}
    if language is not None:
        filters["language"] = language.value
    if topic is not None:
        filters["topic"] = topic.value
    if difficulty is not None:
        filters["difficulty"] = difficulty.value

    return list(get_questions_collection().find(filters).sort("created_at", 1))


def find_question(question_id: str) -> dict[str, Any] | None:
    return get_questions_collection().find_one({"question_id": question_id})
