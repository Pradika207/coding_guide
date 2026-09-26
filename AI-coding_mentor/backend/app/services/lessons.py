from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection

from app.database.mongodb import get_database
from app.models.language import ProgrammingLanguage
from app.models.lesson import (
    LessonDocument,
    LessonProgressDocument,
    LessonProgressStatus,
    QuizDocument,
)
from app.models.question import Topic
from app.services import roadmap as roadmap_service
from app.services import badges, gamification


class LessonError(RuntimeError):
    pass


class LessonNotFoundError(LessonError):
    pass


class LessonAccessError(LessonError):
    pass


class LearningContentUnavailableError(LessonError):
    pass


def get_lessons_collection() -> Collection:
    lessons = get_database()[LessonDocument.collection_name]
    lessons.create_index("lesson_id", unique=True)
    lessons.create_index([("language", 1), ("topic", 1), ("order", 1)])
    lessons.create_index("is_active")
    return lessons


def get_progress_collection() -> Collection:
    progress = get_database()[LessonProgressDocument.collection_name]
    progress.create_index("user_id")
    progress.create_index("lesson_id")
    progress.create_index([("user_id", 1), ("lesson_id", 1)], unique=True)
    return progress


def get_quizzes_collection() -> Collection:
    quizzes = get_database()[QuizDocument.collection_name]
    quizzes.create_index("lesson_id")
    quizzes.create_index("quiz_id", unique=True)
    return quizzes


def topic_from_filter(value: str | None) -> Topic | None:
    if value is None:
        return None
    normalized = value.strip().lower().replace(" ", "_")
    try:
        return Topic(normalized)
    except ValueError as error:
        raise LessonError("Unsupported topic") from error


def _get_lesson(lesson_id: str) -> dict[str, Any]:
    lesson = get_lessons_collection().find_one({"lesson_id": lesson_id, "is_active": True})
    if lesson is None:
        raise LessonNotFoundError("Lesson not found")
    return lesson


def _verify_access(*, user_id: str, lesson: dict[str, Any]) -> dict[str, Any]:
    roadmap = roadmap_service.get_roadmap(user_id=user_id)
    topic_name = Topic(lesson["topic"]).display_name
    roadmap_topic = next(
        (item for item in roadmap["topics"] if item["topic"] == topic_name),
        None,
    )
    if roadmap_topic is None or roadmap_topic["status"] == "locked":
        raise LessonAccessError("This topic is locked on your roadmap")
    return roadmap


def list_lessons(
    *,
    user_id: str,
    language: ProgrammingLanguage | None = None,
    topic: Topic | None = None,
) -> list[dict[str, Any]]:
    filters: dict[str, Any] = {"is_active": True}
    if language is not None:
        filters["language"] = language.value
    if topic is not None:
        filters["topic"] = topic.value
    lessons = list(get_lessons_collection().find(filters).sort("order", 1))
    accessible: list[dict[str, Any]] = []
    for lesson in lessons:
        try:
            _verify_access(user_id=user_id, lesson=lesson)
        except LessonAccessError:
            continue
        accessible.append(LessonDocument.to_public(lesson))
    return accessible


def get_lesson(*, user_id: str, lesson_id: str) -> dict[str, Any]:
    lesson = _get_lesson(lesson_id)
    _verify_access(user_id=user_id, lesson=lesson)
    return LessonDocument.to_public(lesson)


def _get_progress(*, user_id: str, lesson_id: str) -> dict[str, Any] | None:
    return get_progress_collection().find_one(
        {"user_id": user_id, "lesson_id": lesson_id}
    )


def start_lesson(*, user_id: str, lesson_id: str) -> dict[str, Any]:
    lesson = _get_lesson(lesson_id)
    _verify_access(user_id=user_id, lesson=lesson)
    progress = _get_progress(user_id=user_id, lesson_id=lesson_id)
    if progress is None:
        progress = LessonProgressDocument.new(user_id=user_id, lesson_id=lesson_id)
        get_progress_collection().insert_one(progress)
    elif progress["status"] == LessonProgressStatus.NOT_STARTED.value:
        progress.update(
            {
                "status": LessonProgressStatus.IN_PROGRESS.value,
                "started_at": datetime.now(timezone.utc),
            }
        )
        get_progress_collection().update_one(
            {"user_id": user_id, "lesson_id": lesson_id},
            {"$set": {"status": progress["status"], "started_at": progress["started_at"]}},
        )
    return progress


def complete_lesson(*, user_id: str, lesson_id: str) -> dict[str, Any]:
    lesson = _get_lesson(lesson_id)
    _verify_access(user_id=user_id, lesson=lesson)
    progress = _get_progress(user_id=user_id, lesson_id=lesson_id)
    now = datetime.now(timezone.utc)
    was_completed = progress is not None and progress["status"] == LessonProgressStatus.COMPLETED.value
    if progress is None:
        progress = LessonProgressDocument.new(user_id=user_id, lesson_id=lesson_id)
        progress["status"] = LessonProgressStatus.COMPLETED.value
        progress["completed_at"] = now
        get_progress_collection().insert_one(progress)
    elif progress["status"] != LessonProgressStatus.COMPLETED.value:
        progress.update(
            {"status": LessonProgressStatus.COMPLETED.value, "completed_at": now}
        )
        get_progress_collection().update_one(
            {"user_id": user_id, "lesson_id": lesson_id},
            {"$set": {"status": progress["status"], "completed_at": now}},
        )
    if not was_completed:
        try:
            activity = gamification.record_activity(
                user_id=user_id,
                event_type="lesson_completed",
                source_id=lesson_id,
            )
            badges.evaluate_badges(user_id=user_id, profile=activity["profile"])
        except Exception:
            pass
    return progress


def current_lesson(*, user_id: str) -> dict[str, Any]:
    roadmap = roadmap_service.get_roadmap(user_id=user_id)
    current_topic = roadmap["current_topic"]
    language = ProgrammingLanguage(roadmap["language"])
    topic = topic_from_filter(current_topic)
    lessons = list_lessons(user_id=user_id, language=language, topic=topic)
    if not lessons:
        raise LearningContentUnavailableError(
            f"Learning content is not currently available for {current_topic}"
        )
    for lesson in lessons:
        progress = _get_progress(user_id=user_id, lesson_id=lesson["lesson_id"])
        if progress is None or progress["status"] != LessonProgressStatus.COMPLETED.value:
            progress_percent = 100 if progress and progress["status"] == LessonProgressStatus.COMPLETED.value else 0
            return {
                "lesson_id": lesson["lesson_id"],
                "topic": lesson["topic"],
                "title": lesson["title"],
                "progress": progress_percent,
                "status": "available",
            }
    raise LearningContentUnavailableError(
        f"All available lessons for {current_topic} are completed"
    )


def topic_progress(*, user_id: str, topic: Topic, language: ProgrammingLanguage) -> dict[str, Any]:
    lessons = list_lessons(user_id=user_id, language=language, topic=topic)
    completed = sum(
        1
        for lesson in lessons
        if (
            _get_progress(user_id=user_id, lesson_id=lesson["lesson_id"])
            or {}
        ).get("status") == LessonProgressStatus.COMPLETED.value
    )
    total = len(lessons)
    return {
        "topic": topic.display_name,
        "total_lessons": total,
        "completed_lessons": completed,
        "progress_percent": round(completed / total * 100) if total else 0,
    }


def get_lesson_quiz(*, user_id: str, lesson_id: str) -> dict[str, Any]:
    lesson = _get_lesson(lesson_id)
    _verify_access(user_id=user_id, lesson=lesson)
    quiz = get_quizzes_collection().find_one({"lesson_id": lesson_id})
    if quiz is None:
        raise LearningContentUnavailableError("Quiz content is not currently available")
    return QuizDocument.to_public(quiz)


def complete_lesson_quiz(*, user_id: str, lesson_id: str, quiz_id: str, selected_option: str) -> dict[str, Any]:
    lesson = _get_lesson(lesson_id)
    _verify_access(user_id=user_id, lesson=lesson)
    quiz = get_quizzes_collection().find_one({"quiz_id": quiz_id, "lesson_id": lesson_id})
    if quiz is None:
        raise LessonNotFoundError("Quiz not found")
    if selected_option not in quiz["options"]:
        raise LessonError("Selected option is invalid")
    correct = int(selected_option == quiz["correct_option"])
    source_id = f"{lesson_id}:{quiz_id}"
    activity = {"awarded": False, "event": {"xp_amount": 0}}
    if correct:
        activity = gamification.record_activity(
            user_id=user_id,
            event_type="quiz_completed",
            source_id=source_id,
        )
        try:
            badges.evaluate_badges(user_id=user_id, profile=activity["profile"])
        except Exception:
            pass
    return {
        "quiz_id": quiz_id,
        "score": correct * 100,
        "total_questions": 1,
        "correct_answers": correct,
        "passed": bool(correct),
        "xp_awarded": activity["event"]["xp_amount"] if activity["awarded"] else 0,
    }
