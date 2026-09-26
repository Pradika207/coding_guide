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
    test_client = TestClient(app)
    registration = test_client.post(
        "/auth/register",
        json={
            "name": "Language Student",
            "email": "language@example.com",
            "password": "TestPassword123",
        },
    )
    assert registration.status_code == 201
    login = test_client.post(
        "/auth/login",
        json={"email": "language@example.com", "password": "TestPassword123"},
    )
    assert login.status_code == 200
    test_client.headers.update(
        {"Authorization": f"Bearer {login.json()['access_token']}"}
    )

    yield test_client
    database.users.delete_many({})
    mongo_client.close()
    get_mongodb_client.cache_clear()


def test_get_available_languages(public_client):
    response = public_client.get("/languages")
    assert response.status_code == 200
    assert response.json() == {
        "languages": [
            {"id": "c", "name": "C"},
            {"id": "cpp", "name": "C++"},
            {"id": "java", "name": "Java"},
            {"id": "python", "name": "Python"},
            {"id": "javascript", "name": "JavaScript"},
        ]
    }


def test_select_java(client):
    response = client.put("/auth/language", json={"language": "java"})
    assert response.status_code == 200
    assert response.json()["user"]["selected_language"] == "java"


def test_select_python(client):
    response = client.put("/auth/language", json={"language": "python"})
    assert response.status_code == 200
    assert response.json()["user"]["selected_language"] == "python"


def test_select_cpp(client):
    response = client.put("/auth/language", json={"language": "cpp"})
    assert response.status_code == 200
    assert response.json()["user"]["selected_language"] == "cpp"


def test_invalid_language(client):
    response = client.put("/auth/language", json={"language": "html"})
    assert response.status_code == 422


def test_select_language_requires_auth(public_client):
    response = public_client.put("/auth/language", json={"language": "java"})
    assert response.status_code == 401


def test_get_current_language(client):
    response = client.get("/auth/language")
    assert response.status_code == 200
    assert response.json() == {"selected_language": "cpp"}


def test_user_can_change_language(client):
    response = client.put("/auth/language", json={"language": "javascript"})
    assert response.status_code == 200
    assert response.json()["user"]["selected_language"] == "javascript"
    assert client.get("/auth/language").json() == {"selected_language": "javascript"}
