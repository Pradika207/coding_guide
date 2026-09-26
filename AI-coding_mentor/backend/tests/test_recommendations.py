from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.language import ProgrammingLanguage
from app.services import assessment as assessment_service
from app.services import assessment_results as result_service
from app.services import questions as question_service
from app.services import recommendations
from app.services import roadmap as roadmap_service
from app.services.security import get_current_user


class Cursor(list):
    def sort(self, key, direction):
        return Cursor(sorted(self, key=lambda item: item[key], reverse=direction < 0))

    def limit(self, value):
        return Cursor(self[:value])


class Collection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    def create_index(self, *_args, **_kwargs):
        return None

    def find_one(self, query, *_args, **kwargs):
        matches = [item for item in self.docs if all(item.get(k) == v for k, v in query.items())]
        if kwargs.get("sort") and matches:
            key, direction = kwargs["sort"][0]
            matches.sort(key=lambda item: item[key], reverse=direction < 0)
        return matches[0] if matches else None

    def find(self, query, *_args, **_kwargs):
        return Cursor([item for item in self.docs if all(item.get(k) == v for k, v in query.items())])

    def insert_one(self, document):
        self.docs.append(document)

    def delete_many(self, query):
        self.docs[:] = [item for item in self.docs if not all(item.get(k) == v for k, v in query.items())]


def question(question_id, topic, difficulty, language="java"):
    return {"question_id": question_id, "title": question_id, "topic": topic, "difficulty": difficulty, "language": language}


def result():
    return {
        "user_id": "user-1", "session_id": "assessment-1", "language": "java",
        "created_at": datetime.now(timezone.utc), "topic_scores": {"Arrays": 20, "Strings": 60, "Sorting": 90},
        "weak_topics": ["Arrays"], "strong_topics": ["Sorting"], "recommended_next_topic": "Arrays",
    }


def setup(monkeypatch, *, questions=None, submissions=None, roadmap=None, results=None):
    collection = Collection()
    monkeypatch.setattr(recommendations, "get_recommendations_collection", lambda: collection)
    monkeypatch.setattr(result_service, "get_assessment_results_collection", lambda: Collection(results if results is not None else [result()]))
    monkeypatch.setattr(question_service, "find_questions", lambda **_: questions or [])
    monkeypatch.setattr(assessment_service, "get_assessment_submissions_collection", lambda: Collection(submissions or []))
    if roadmap is None:
        roadmap = {"current_topic": "Arrays", "topics": [{"topic": "Arrays", "status": "recommended"}, {"topic": "Graphs", "status": "locked"}]}
    monkeypatch.setattr(roadmap_service, "get_roadmap", lambda **_: roadmap)
    return collection


def client(user_id="user-1", language="java"):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id, "selected_language": language}
    return TestClient(app)


def test_authentication_required():
    assert TestClient(app).get("/recommendations").status_code == 401
    assert TestClient(app).get("/recommendations/current").status_code == 401


def test_new_user_has_clear_assessment_state(monkeypatch):
    setup(monkeypatch, results=[])
    current = client()
    try:
        response = current.get("/recommendations")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["status"] == "assessment_required"


def test_weak_topic_priority_and_language_filter(monkeypatch):
    questions = [question("java-arrays-easy", "arrays", "easy"), question("java-sorting-medium", "sorting", "medium"), question("python-arrays-easy", "arrays", "easy", "python")]
    setup(monkeypatch, questions=questions)
    current = client()
    try:
        response = current.post("/recommendations/refresh")
    finally:
        app.dependency_overrides.clear()
    body = response.json()
    assert response.status_code == 200
    assert body["recommendations"][0]["question_id"] == "java-arrays-easy"
    assert all(item["question_id"].startswith("java-") for item in body["recommendations"])
    assert "weak topics" in body["recommendations"][0]["reason"]


def test_solved_and_locked_questions_are_excluded(monkeypatch):
    questions = [question("solved", "arrays", "easy"), question("locked", "graphs", "easy"), question("available", "arrays", "easy")]
    submissions = [{"user_id": "user-1", "question_id": "solved", "status": "accepted"}]
    setup(monkeypatch, questions=questions, submissions=submissions)
    current = client()
    try:
        response = current.post("/recommendations/refresh")
    finally:
        app.dependency_overrides.clear()
    ids = [item["question_id"] for item in response.json()["recommendations"]]
    assert ids == ["available"]


def test_difficulty_progression(monkeypatch):
    questions = [question("weak-medium", "arrays", "medium"), question("weak-hard", "arrays", "hard"), question("weak-easy", "arrays", "easy"), question("strong-medium", "sorting", "medium")]
    setup(monkeypatch, questions=questions)
    context = recommendations._context(user_id="user-1", language=ProgrammingLanguage.JAVA, result=result())
    scorer = recommendations.RuleBasedRecommendationScorer()
    weak_scores = {item["question_id"]: scorer.score(item, context)[0] for item in questions[:3]}
    assert weak_scores["weak-easy"] > weak_scores["weak-medium"] > weak_scores["weak-hard"]


def test_deterministic_order_and_limit(monkeypatch):
    questions = [question(f"q-{index}", "arrays", "easy") for index in range(6)]
    setup(monkeypatch, questions=questions)
    current = client()
    try:
        first = current.post("/recommendations/refresh?limit=3").json()
        second = current.post("/recommendations/refresh?limit=3").json()
    finally:
        app.dependency_overrides.clear()
    assert len(first["recommendations"]) == 3
    assert [x["question_id"] for x in first["recommendations"]] == [x["question_id"] for x in second["recommendations"]]
    assert TestClient(app).get("/recommendations?limit=21").status_code == 401


def test_recent_attempt_penalty(monkeypatch):
    now = datetime.now(timezone.utc)
    questions = [question("recent", "arrays", "easy"), question("unseen", "arrays", "easy")]
    submissions = [{"user_id": "user-1", "question_id": "recent", "status": "wrong_answer", "submitted_at": now}]
    setup(monkeypatch, questions=questions, submissions=submissions)
    context = recommendations._context(user_id="user-1", language=ProgrammingLanguage.JAVA, result=result())
    scorer = recommendations.RuleBasedRecommendationScorer()
    assert scorer.score(questions[1], context)[0] > scorer.score(questions[0], context)[0]


def test_refresh_replaces_active_set_without_duplicates(monkeypatch):
    questions = [question("one", "arrays", "easy"), question("two", "arrays", "easy")]
    collection = setup(monkeypatch, questions=questions)
    current = client()
    try:
        current.post("/recommendations/refresh")
        current.post("/recommendations/refresh")
    finally:
        app.dependency_overrides.clear()
    assert len(collection.docs) == 2
    assert len({item["question_id"] for item in collection.docs}) == 2


def test_topic_normalization_reuses_existing_enum():
    assert recommendations.Topic("arrays").display_name == "Arrays"
    assert recommendations.Topic("object_oriented_programming").display_name == "Object Oriented Programming"
