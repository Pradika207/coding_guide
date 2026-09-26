from datetime import datetime
from typing import Any


class UserDocument:
    collection_name = "users"

    @staticmethod
    def to_public(document: dict[str, Any]) -> dict[str, Any]:
        return {
            "user_id": document["user_id"],
            "name": document["name"],
            "email": document["email"],
            "selected_language": document.get("selected_language"),
            "role": document.get("role", "student"),
            "created_at": document["created_at"],
        }

    @staticmethod
    def new(*, user_id: str, name: str, email: str, password_hash: str) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "name": name,
            "email": email,
            "password_hash": password_hash,
            "selected_language": None,
            "role": "student",
            "created_at": datetime.utcnow(),
        }
