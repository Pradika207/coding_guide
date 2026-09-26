import os

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

os.environ.setdefault("MONGODB_URL", "")
os.environ.setdefault("DATABASE_NAME", "ai_coding_mentor_test")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRATION_MINUTES", "60")

from app.database.mongodb import get_mongodb_client
from app.main import app


@pytest.fixture(scope="module")
def public_client():
    return TestClient(app)


@pytest.fixture(scope="module")
def client():
    mongodb_url = os.environ.get("MONGODB_URL")
    if not mongodb_url:
        pytest.skip("MONGODB_URL is not configured; integration tests require MongoDB")

    mongo_client = MongoClient(mongodb_url, serverSelectionTimeoutMS=1000)
    try:
        mongo_client.admin.command("ping")
    except Exception as error:
        mongo_client.close()
        pytest.skip(f"MongoDB is unavailable: {error}")

    database = mongo_client[os.environ["DATABASE_NAME"]]
    database.users.delete_many({})
    database.questions.delete_many({})
    test_client = TestClient(app)
    registration = test_client.post(
        "/auth/register",
        json={"name": "Question Admin", "email": "questions@example.com", "password": "TestPassword123"},
    )
    assert registration.status_code == 201
    login = test_client.post(
        "/auth/login",
        json={"email": "questions@example.com", "password": "TestPassword123"},
    )
    assert login.status_code == 200
    test_client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})

    for question in (
        {"title": "Java Array Maximum", "language": "java", "topic": "arrays", "difficulty": "easy"},
        {"title": "Python Loop Sum", "language": "python", "topic": "loops", "difficulty": "medium"},
        {"title": "C++ Array Sort", "language": "cpp", "topic": "arrays", "difficulty": "hard"},
    ):
        response = test_client.post(
            "/questions",
            json={
                **question,
                "description": "Solve this original practice problem.",
                "sample_input": "3\n1 2 3",
                "sample_output": "6",
                "test_cases": [
                    {"input": "3\n1 2 3", "expected_output": "6", "is_hidden": False},
                    {"input": "2\n9 1", "expected_output": "10", "is_hidden": True},
                ],
                "constraints": ["1 <= n <= 100000"],
                "time_limit": 2,
                "memory_limit": 256,
            },
        )
        assert response.status_code == 201

    yield test_client
    database.users.delete_many({})
    database.questions.delete_many({})
    mongo_client.close()
    get_mongodb_client.cache_clear()


def test_create_question(client):
    response = client.post(
        "/questions",
        json={
            "title": "Count Characters",
            "description": "Count the number of characters in a word.",
            "language": "javascript",
            "topic": "strings",
            "difficulty": "easy",
            "sample_input": "hello",
            "sample_output": "5",
            "test_cases": [{"input": "hello", "expected_output": "5", "is_hidden": False}],
            "constraints": ["The word is non-empty."],
            "time_limit": 2,
            "memory_limit": 256,
        },
    )
    assert response.status_code == 201
    assert response.json()["question_id"].startswith("javascript-strings-")
    assert "test_cases" not in response.json()


def test_get_all_questions(client):
    response = client.get("/questions")
    assert response.status_code == 200
    assert len(response.json()["questions"]) == 4


def test_filter_by_language(client):
    response = client.get("/questions?language=java")
    assert response.status_code == 200
    assert all(question["language"] == "java" for question in response.json()["questions"])


def test_filter_by_topic(client):
    response = client.get("/questions?topic=arrays")
    assert response.status_code == 200
    assert all(question["topic"] == "arrays" for question in response.json()["questions"])


def test_filter_by_difficulty(client):
    response = client.get("/questions?difficulty=medium")
    assert response.status_code == 200
    assert all(question["difficulty"] == "medium" for question in response.json()["questions"])


def test_filter_by_all_fields(client):
    response = client.get("/questions?language=cpp&topic=arrays&difficulty=hard")
    assert response.status_code == 200
    assert len(response.json()["questions"]) == 1


def test_get_single_question(client):
    question = client.get("/questions").json()["questions"][0]
    response = client.get(f"/questions/{question['question_id']}")
    assert response.status_code == 200
    assert response.json()["question_id"] == question["question_id"]


def test_invalid_filters(public_client):
    assert public_client.get("/questions?language=rust").status_code == 422
    assert public_client.get("/questions?topic=matrices").status_code == 422
    assert public_client.get("/questions?difficulty=expert").status_code == 422


def test_hidden_test_cases_are_not_exposed(client):
    response = client.get("/questions")
    assert "test_cases" not in response.text
    question_id = response.json()["questions"][0]["question_id"]
    single = client.get(f"/questions/{question_id}")
    assert "test_cases" not in single.text
    assert "is_hidden" not in single.text


def test_create_question_requires_authentication(public_client):
    response = public_client.post("/questions", json={})
    assert response.status_code == 401
