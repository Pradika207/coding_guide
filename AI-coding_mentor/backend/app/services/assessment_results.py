from typing import Any

from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from app.database.mongodb import get_database
from app.models.assessment_result import (
    AssessmentResultDocument,
    SkillLevel,
)
from app.models.language import ProgrammingLanguage
from app.models.question import Topic
from app.services import assessment as assessment_service


class AssessmentReportError(RuntimeError):
    pass


def get_assessment_results_collection() -> Collection:
    results = get_database()[AssessmentResultDocument.collection_name]
    results.create_index("user_id")
    results.create_index("session_id", unique=True)
    results.create_index("result_id", unique=True)
    return results


def skill_level_for_score(score: int) -> SkillLevel:
    if score < 40:
        return SkillLevel.BEGINNER
    if score < 70:
        return SkillLevel.INTERMEDIATE
    return SkillLevel.ADVANCED


def _topic_name(topic: str) -> str:
    try:
        return Topic(topic).display_name
    except ValueError as error:
        raise AssessmentReportError("Assessment contains an unsupported topic") from error


def _calculate_topic_scores(
    *,
    question_metadata: list[dict[str, str]],
    accepted_question_ids: set[str],
) -> dict[str, int]:
    totals: dict[str, int] = {}
    solved: dict[str, int] = {}
    for question in question_metadata:
        topic_name = _topic_name(question["topic"])
        totals[topic_name] = totals.get(topic_name, 0) + 1
        if question["question_id"] in accepted_question_ids:
            solved[topic_name] = solved.get(topic_name, 0) + 1

    if not totals:
        raise AssessmentReportError("Assessment has no questions to report")
    return {
        topic: round((solved.get(topic, 0) / total) * 100)
        for topic, total in totals.items()
    }


def _build_result(
    *,
    session: dict[str, Any],
    accepted_question_ids: set[str],
) -> dict[str, Any]:
    question_metadata = session.get("question_metadata", [])
    topic_scores = _calculate_topic_scores(
        question_metadata=question_metadata,
        accepted_question_ids=accepted_question_ids,
    )
    overall_score = session.get("score")
    if not isinstance(overall_score, int):
        raise AssessmentReportError("Assessment does not have a final score")

    strong_topics = [topic for topic, score in topic_scores.items() if score >= 80]
    weak_topics = [topic for topic, score in topic_scores.items() if score < 50]
    recommended_next_topic = min(
        topic_scores,
        key=lambda topic: (topic_scores[topic], list(topic_scores).index(topic)),
    )
    language = ProgrammingLanguage(session["language"])
    return AssessmentResultDocument.new(
        session_id=session["session_id"],
        user_id=session["user_id"],
        language=language,
        overall_score=overall_score,
        topic_scores=topic_scores,
        skill_level=skill_level_for_score(overall_score),
        strong_topics=strong_topics,
        weak_topics=weak_topics,
        recommended_next_topic=recommended_next_topic,
    )


def get_or_create_result(*, session_id: str, user_id: str) -> dict[str, Any]:
    session = assessment_service.get_owned_session(session_id=session_id, user_id=user_id)
    if session["status"] != "completed":
        raise assessment_service.AssessmentStateError(
            "Assessment must be completed before generating a report"
        )

    results = get_assessment_results_collection()
    existing = results.find_one({"session_id": session_id, "user_id": user_id})
    if existing is not None:
        return existing

    submissions = assessment_service.get_assessment_submissions_collection()
    accepted_question_ids = {
        submission["question_id"]
        for submission in submissions.find(
            {"session_id": session_id, "status": "accepted"},
            {"question_id": 1},
        )
    }
    result = _build_result(
        session=session,
        accepted_question_ids=accepted_question_ids,
    )
    try:
        results.insert_one(result)
    except DuplicateKeyError:
        existing = results.find_one({"session_id": session_id, "user_id": user_id})
        if existing is not None:
            return existing
        raise
    return result


def get_history(*, user_id: str) -> list[dict[str, Any]]:
    results = get_assessment_results_collection()
    return list(results.find({"user_id": user_id}).sort("created_at", -1))
