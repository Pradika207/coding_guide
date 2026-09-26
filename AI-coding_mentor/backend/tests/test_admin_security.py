import pytest
from fastapi import HTTPException

from app.services.security import require_admin


def test_require_admin_allows_admin_user():
    current_user = {"user_id": "admin-123", "role": "admin"}

    assert require_admin(current_user) == current_user


def test_require_admin_rejects_student_user():
    with pytest.raises(HTTPException) as exc_info:
        require_admin({"user_id": "student-123", "role": "student"})

    assert exc_info.value.status_code == 403
