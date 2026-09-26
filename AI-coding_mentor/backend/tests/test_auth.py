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
    yield TestClient(app)
    database.users.delete_many({})
    mongo_client.close()
    get_mongodb_client.cache_clear()


def test_register_user(client):
    response = client.post(
        "/auth/register",
        json={"name": "Test User", "email": "test@example.com", "password": "TestPassword123"},
    )
    assert response.status_code == 201
    assert "password_hash" not in response.text
    assert response.json()["user"]["email"] == "test@example.com"


def test_duplicate_registration(client):
    response = client.post(
        "/auth/register",
        json={"name": "Test User", "email": "test@example.com", "password": "TestPassword123"},
    )
    assert response.status_code == 409


def test_login_preflight_allows_frontend_origin(client):
    response = client.options(
        "/auth/login",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") in {"http://127.0.0.1:5173", "*"}
    assert "POST" in response.headers.get("access-control-allow-methods", "")


def test_login_with_correct_password(client):
    response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "TestPassword123"},
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


def test_login_with_incorrect_password(client):
    response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_current_user_with_valid_token(client):
    login = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "TestPassword123"},
    )
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


def test_current_user_without_token(client):
    assert client.get("/auth/me").status_code == 401


def test_current_user_with_invalid_token(client):
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401


def test_new_users_default_to_student_role(client):
    response = client.post(
        "/auth/register",
        json={"name": "Role User", "email": "role@example.com", "password": "TestPassword123"},
    )
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "student"


def test_admin_routes_require_admin_role(client):
    student = client.post(
        "/auth/register",
        json={"name": "Student", "email": "student-admin@example.com", "password": "TestPassword123"},
    )
    student_token = client.post(
        "/auth/login",
        json={"email": "student-admin@example.com", "password": "TestPassword123"},
    ).json()["access_token"]

    blocked = client.get(
        "/admin/health",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert blocked.status_code == 403

    database = client.app.dependency_overrides.get(None)
    user_store = client.app.dependency_overrides
    del user_store
    _ = student
    # Use the database directly to promote the user to admin.
    from app.database.mongodb import get_database

    get_database().users.update_one({"email": "student-admin@example.com"}, {"$set": {"role": "admin"}})
    admin_token = client.post(
        "/auth/login",
        json={"email": "student-admin@example.com", "password": "TestPassword123"},
    ).json()["access_token"]
    admin_response = client.get(
        "/admin/health",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_response.status_code == 200
    assert admin_response.json()["backend"]["api_status"] == "healthy"
