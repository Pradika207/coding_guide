from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection

from app.database.config import settings
from app.database.mongodb import get_database
from app.models.assessment import (
    AssessmentSessionDocument,
    AssessmentStatus,
)
from app.models.language import ProgrammingLanguage
from app.models.question import Difficulty
from app.services import questions as question_service
from app.services import badges, gamification

DIFFICULTY_PLAN = (
    Difficulty.EASY,
    Difficulty.EASY,
    Difficulty.MEDIUM,
    Difficulty.MEDIUM,
    Difficulty.HARD,
)


class AssessmentError(RuntimeError):
    pass


class AssessmentNotFoundError(AssessmentError):
    pass


class AssessmentStateError(AssessmentError):
    pass


class AssessmentQuestionError(AssessmentError):
    pass


def get_assessment_sessions_collection() -> Collection:
    sessions = get_database()[AssessmentSessionDocument.collection_name]
    sessions.create_index("user_id")
    sessions.create_index("session_id", unique=True)
    sessions.create_index([("user_id", 1), ("status", 1)])
    return sessions


def get_assessment_submissions_collection() -> Collection:
    submissions = get_database()["assessment_submissions"]
    submissions.create_index("user_id")
    submissions.create_index("session_id")
    submissions.create_index("question_id")
    submissions.create_index([("session_id", 1), ("question_id", 1)])
    return submissions


def _select_questions(language: ProgrammingLanguage) -> list[dict[str, Any]]:
    all_questions = question_service.find_questions(language=language)
    required_count = settings.assessment_question_count
    if required_count <= 0:
        raise AssessmentQuestionError("Assessment question count must be positive")

    plan = list(DIFFICULTY_PLAN)
    if required_count > len(plan):
        plan.extend([Difficulty.MEDIUM] * (required_count - len(plan)))

    selected: list[dict[str, Any]] = []
    used_topics: set[str] = set()
    for difficulty in plan[:required_count]:
        candidates = [
            question
            for question in all_questions
            if question.get("difficulty") == difficulty.value
            and question.get("question_id") not in {item["question_id"] for item in selected}
        ]
        if not candidates:
            raise AssessmentQuestionError(
                f"Not enough {difficulty.value} questions for {language.value} assessment"
            )
        distinct_topic = next(
            (question for question in candidates if question.get("topic") not in used_topics),
            candidates[0],
        )
        selected.append(distinct_topic)
        used_topics.add(distinct_topic["topic"])

    return selected


def start_assessment(*, user_id: str, language: ProgrammingLanguage) -> dict[str, Any]:
    sessions = get_assessment_sessions_collection()
    if sessions.find_one(
        {"user_id": user_id, "status": AssessmentStatus.IN_PROGRESS.value}
    ):
        raise AssessmentStateError("You already have an assessment in progress")

    selected_questions = _select_questions(language)
    session = AssessmentSessionDocument.new(
        user_id=user_id,
        language=language,
        question_ids=[question["question_id"] for question in selected_questions],
        question_metadata=[
            {
                "question_id": question["question_id"],
                "topic": question["topic"],
                "difficulty": question["difficulty"],
            }
            for question in selected_questions
        ],
    )
    sessions.insert_one(session)
    return {"session": session, "questions": selected_questions}


def get_owned_session(*, session_id: str, user_id: str) -> dict[str, Any]:
    session = get_assessment_sessions_collection().find_one(
        {"session_id": session_id, "user_id": user_id}
    )
    if session is None:
        raise AssessmentNotFoundError("Assessment session not found")
    return session


def get_attempt_count(*, session_id: str, question_id: str) -> int:
    return get_assessment_submissions_collection().count_documents(
        {"session_id": session_id, "question_id": question_id}
    )


def complete_assessment(*, session_id: str, user_id: str) -> dict[str, Any]:
    sessions = get_assessment_sessions_collection()
    session = get_owned_session(session_id=session_id, user_id=user_id)
    if session["status"] != AssessmentStatus.IN_PROGRESS.value:
        raise AssessmentStateError("Assessment session is already completed or abandoned")

    submissions = get_assessment_submissions_collection()
    accepted_question_ids = {
        submission["question_id"]
        for submission in submissions.find(
            {"session_id": session_id, "status": "accepted"},
            {"question_id": 1},
        )
    }
    total_questions = len(session["question_ids"])
    solved_questions = len(accepted_question_ids.intersection(session["question_ids"]))
    score = round((solved_questions / total_questions) * 100) if total_questions else 0

    completed_at = datetime.now(timezone.utc)
    sessions.update_one(
        {"session_id": session_id, "user_id": user_id, "status": AssessmentStatus.IN_PROGRESS.value},
        {
            "$set": {
                "status": AssessmentStatus.COMPLETED.value,
                "completed_at": completed_at,
                "score": score,
            }
        },
    )
    result = {
        "session_id": session_id,
        "status": AssessmentStatus.COMPLETED.value,
        "score": score,
        "total_questions": total_questions,
        "solved_questions": solved_questions,
        "accuracy": score,
        "language": session["language"],
    }
    try:
        activity = gamification.record_activity(
            user_id=user_id,
            event_type="assessment_completed",
            source_id=session_id,
        )
        badges.evaluate_badges(user_id=user_id, profile=activity["profile"])
    except Exception:
        pass
    return result
