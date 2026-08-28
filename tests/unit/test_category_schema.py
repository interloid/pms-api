from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.category_schema import CategoryResponse
from app.schemas.session_schema import SessionResponse
from app.schemas.user_schema import UserResponse


def test_category_response_valid():
    category_id = uuid4()

    category = CategoryResponse(
        id=category_id,
        name="Electronics",
    )

    assert category.id == category_id
    assert category.name == "Electronics"


def test_category_response_missing_id():
    with pytest.raises(ValidationError):
        CategoryResponse(
            name="Electronics",
        )


def test_category_response_missing_name():
    with pytest.raises(ValidationError):
        CategoryResponse(
            id=uuid4(),
        )


def test_category_response_invalid_uuid():
    with pytest.raises(ValidationError):
        CategoryResponse(
            id="not-a-uuid",
            name="Electronics",
        )


def test_session_response_valid():
    user_id = uuid4()

    user = UserResponse(
        id=user_id,
        email="john@example.com",
        first_name="John",
        last_name="Doe",
        is_active=True,
    )

    response = SessionResponse(
        user=user,
    )

    assert response.user.id == user_id
    assert response.user.email == "john@example.com"
    assert response.user.first_name == "John"
    assert response.user.last_name == "Doe"
    assert response.user.is_active is True


def test_session_response_invalid_user():
    with pytest.raises(ValidationError):
        SessionResponse(
            user={
                "id": "invalid-id",
                "email": "john@example.com",
            }
        )
