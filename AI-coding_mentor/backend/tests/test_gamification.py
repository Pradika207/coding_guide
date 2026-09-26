from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import badges, gamification
from app.services.security import get_current_user


class Cursor(list):
    def sort(self, key, direction):
        return Cursor(sorted(self, key=lambda item: item[key], reverse=direction < 0))

    def skip(self, amount):
        return Cursor(self[amount:])

    def limit(self, amount):
        return Cursor(self[:amount])


class Collection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    def create_index(self, *_args, **_kwargs):
        return None

    def find_one(self, query, *_args, **_kwargs):
        return next((doc for doc in self.docs if all(doc.get(k) == v for k, v in query.items())), None)

    def find(self, query, *_args, **_kwargs):
        return Cursor([doc for doc in self.docs if all(doc.get(k) == v for k, v in query.items())])

    def insert_one(self, document):
        self.docs.append(document)

    def update_one(self, query, update, upsert=False):
        document = self.find_one(query)
        if document:
            document.update(update.get("$set", {}))
        elif upsert:
            document = dict(update.get("$setOnInsert", {}))
            self.docs.append(document)

    def count_documents(self, query):
        return len(self.find(query))


def _profile(user_id="user-1", **overrides):
    profile = {
        "user_id": user_id,
        "total_xp": 0,
        "level": 1,
        "current_streak": 0,
        "longest_streak": 0,
        "daily_goal_xp": 100,
        "daily_xp": 0,
        "last_activity_date": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    profile.update(overrides)
    return profile


def test_level_formula_boundaries():
    assert gamification.calculate_level(0) == 1
    assert gamification.calculate_level(100) == 2
    assert gamification.calculate_level(400) == 3
    assert gamification.calculate_level(900) == 4
    assert gamification.calculate_level(1600) == 5


def test_xp_award_and_idempotency(monkeypatch):
    profiles = Collection([_profile()])
    events = Collection()
    monkeypatch.setattr(gamification, "get_profiles_collection", lambda: profiles)
    monkeypatch.setattr(gamification, "get_xp_events_collection", lambda: events)
    first = gamification.record_activity(user_id="user-1", event_type="lesson_completed", source_id="lesson-1")
    second = gamification.record_activity(user_id="user-1", event_type="lesson_completed", source_id="lesson-1")
    assert first["awarded"] is True
    assert second["awarded"] is False
    assert profiles.docs[0]["total_xp"] == 10
    assert len(events.docs) == 1


def test_streak_consecutive_broken_and_same_day(monkeypatch):
    profiles = Collection([_profile()])
    events = Collection()
    monkeypatch.setattr(gamification, "get_profiles_collection", lambda: profiles)
    monkeypatch.setattr(gamification, "get_xp_events_collection", lambda: events)
    monkeypatch.setattr(gamification, "utc_today", lambda: date(2026, 9, 25))
    gamification.record_activity(user_id="user-1", event_type="lesson_completed", source_id="a")
    assert profiles.docs[0]["current_streak"] == 1
    profiles.docs[0]["last_activity_date"] = "2026-09-24"
    gamification.record_activity(user_id="user-1", event_type="lesson_completed", source_id="b")
    assert profiles.docs[0]["current_streak"] == 2
    profiles.docs[0]["last_activity_date"] = "2026-09-20"
    gamification.record_activity(user_id="user-1", event_type="lesson_completed", source_id="c")
    assert profiles.docs[0]["current_streak"] == 1
    assert profiles.docs[0]["longest_streak"] == 2


def test_daily_goal_summary_and_validation(monkeypatch):
    profiles = Collection([_profile(total_xp=120, level=2, daily_xp=60)])
    monkeypatch.setattr(gamification, "get_profiles_collection", lambda: profiles)
    profile = gamification.set_daily_goal(user_id="user-1", daily_goal_xp=50)
    result = gamification.summary(profile)
    assert result["daily_goal_progress"] == 1
    assert result["daily_goal_completed"] is True
    with pytest.raises(Exception):
        from app.schemas.gamification import DailyGoalRequest
        DailyGoalRequest(daily_goal_xp=5)


def test_badge_catalog_has_objective_rules():
    assert len(badges.BADGE_CATALOG) == 8
    assert {item["criteria_type"] for item in badges.BADGE_CATALOG} >= {"lessons_completed", "xp", "streak"}


def test_gamification_endpoints_require_authentication():
    client = TestClient(app)
    assert client.get("/gamification").status_code == 401
    assert client.get("/gamification/badges").status_code == 401
    assert client.get("/gamification/xp-history").status_code == 401
    assert client.put("/gamification/daily-goal", json={"daily_goal_xp": 100}).status_code == 401


def test_quiz_completion_awards_only_correct_answer(monkeypatch):
    from app.services import lessons
    quiz = {"quiz_id": "quiz-1", "lesson_id": "lesson-1", "options": ["A", "B"], "correct_option": "B"}
    monkeypatch.setattr(lessons, "_get_lesson", lambda _: {"lesson_id": "lesson-1", "topic": "arrays"})
    monkeypatch.setattr(lessons, "_verify_access", lambda **_: {})
    monkeypatch.setattr(lessons, "get_quizzes_collection", lambda: Collection([quiz]))
    monkeypatch.setattr(lessons.gamification, "record_activity", lambda **_: {"awarded": True, "event": {"xp_amount": 20}, "profile": _profile()})
    monkeypatch.setattr(lessons.badges, "evaluate_badges", lambda **_: [])
    wrong = lessons.complete_lesson_quiz(user_id="user-1", lesson_id="lesson-1", quiz_id="quiz-1", selected_option="A")
    right = lessons.complete_lesson_quiz(user_id="user-1", lesson_id="lesson-1", quiz_id="quiz-1", selected_option="B")
    assert wrong["passed"] is False and wrong["xp_awarded"] == 0
    assert right["passed"] is True and right["xp_awarded"] == 20


def test_quiz_completion_endpoint_requires_authentication():
    response = TestClient(app).post("/lessons/lesson-1/quiz/complete", json={"quiz_id": "quiz-1", "selected_option": "A"})
    assert response.status_code == 401
