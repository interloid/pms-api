from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleEnum
from app.core.security import create_access_token
from app.models.category_model import Category
from app.models.user_model import User


async def create_authenticated_headers(
    *,
    db_session: AsyncSession,
    role: RoleEnum = RoleEnum.VIEWER,
    is_active: bool = True,
) -> dict[str, str]:
    user = User(
        email=f"category-user-{uuid4()}@example.com",
        first_name="Category",
        last_name="User",
        is_active=is_active,
        role=role,
    )

    db_session.add(user)
    await db_session.commit()

    access_token = create_access_token(
        {
            "sub": str(user.id),
        }
    )

    return {
        "Authorization": f"Bearer {access_token}",
    }


@pytest.mark.asyncio
async def test_get_categories_requires_authentication(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/categories",
    )

    assert response.status_code == 401

    response_data = response.json()

    assert response_data["success"] is False


@pytest.mark.asyncio
async def test_get_categories_rejects_inactive_user(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    headers = await create_authenticated_headers(
        db_session=db_session,
        role=RoleEnum.VIEWER,
        is_active=False,
    )

    response = await client.get(
        "/api/v1/categories",
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json()["success"] is False


@pytest.mark.asyncio
async def test_get_categories_requires_view_products_permission(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    headers = await create_authenticated_headers(
        db_session=db_session,
    )

    with patch(
        "app.api.authorization.has_permission",
        return_value=False,
    ):
        response = await client.get(
            "/api/v1/categories",
            headers=headers,
        )

    assert response.status_code == 403

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize(
    "role",
    [
        RoleEnum.VIEWER,
        RoleEnum.EDITOR,
        RoleEnum.ADMIN,
    ],
)
@pytest.mark.asyncio
async def test_authenticated_roles_can_get_categories(
    role: RoleEnum,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    search_value = uuid4().hex[:8]

    category = Category(
        id=uuid4(),
        name=f"Electronics-{search_value}",
    )

    db_session.add(category)
    await db_session.commit()

    headers = await create_authenticated_headers(
        db_session=db_session,
        role=role,
    )

    response = await client.get(
        "/api/v1/categories",
        params={
            "search": search_value,
        },
        headers=headers,
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["success"] is True
    assert response_data["message"] == "Categories retrieved successfully"
    assert len(response_data["data"]) == 1
    assert response_data["data"][0]["id"] == str(category.id)
    assert response_data["data"][0]["name"] == (category.name)


@pytest.mark.asyncio
async def test_get_categories_returns_categories_in_name_order(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    search_value = uuid4().hex[:8]

    categories = [
        Category(
            id=uuid4(),
            name=f"Zulu-{search_value}",
        ),
        Category(
            id=uuid4(),
            name=f"Alpha-{search_value}",
        ),
        Category(
            id=uuid4(),
            name=f"Middle-{search_value}",
        ),
    ]

    db_session.add_all(categories)
    await db_session.commit()

    headers = await create_authenticated_headers(
        db_session=db_session,
    )

    response = await client.get(
        "/api/v1/categories",
        params={
            "search": search_value,
            "page": 1,
            "page_size": 10,
        },
        headers=headers,
    )

    assert response.status_code == 200

    response_data = response.json()

    returned_names = [category["name"] for category in response_data["data"]]

    assert returned_names == [
        f"Alpha-{search_value}",
        f"Middle-{search_value}",
        f"Zulu-{search_value}",
    ]


@pytest.mark.asyncio
async def test_get_categories_returns_pagination_metadata(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    search_value = uuid4().hex[:8]

    categories = [
        Category(
            id=uuid4(),
            name=f"Category-A-{search_value}",
        ),
        Category(
            id=uuid4(),
            name=f"Category-B-{search_value}",
        ),
        Category(
            id=uuid4(),
            name=f"Category-C-{search_value}",
        ),
    ]

    db_session.add_all(categories)
    await db_session.commit()

    headers = await create_authenticated_headers(
        db_session=db_session,
    )

    response = await client.get(
        "/api/v1/categories",
        params={
            "search": search_value,
            "page": 1,
            "page_size": 2,
        },
        headers=headers,
    )

    assert response.status_code == 200

    response_data = response.json()
    pagination = response_data["pagination"]

    assert len(response_data["data"]) == 2
    assert pagination["page"] == 1
    assert pagination["page_size"] == 2
    assert pagination["total"] == 3
    assert pagination["total_pages"] == 2


@pytest.mark.asyncio
async def test_get_categories_returns_second_page(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    search_value = uuid4().hex[:8]

    categories = [
        Category(
            id=uuid4(),
            name=f"Category-A-{search_value}",
        ),
        Category(
            id=uuid4(),
            name=f"Category-B-{search_value}",
        ),
        Category(
            id=uuid4(),
            name=f"Category-C-{search_value}",
        ),
    ]

    db_session.add_all(categories)
    await db_session.commit()

    headers = await create_authenticated_headers(
        db_session=db_session,
    )

    response = await client.get(
        "/api/v1/categories",
        params={
            "search": search_value,
            "page": 2,
            "page_size": 2,
        },
        headers=headers,
    )

    assert response.status_code == 200

    response_data = response.json()

    assert len(response_data["data"]) == 1
    assert response_data["data"][0]["name"] == (f"Category-C-{search_value}")

    assert response_data["pagination"] == {
        "page": 2,
        "page_size": 2,
        "total": 3,
        "total_pages": 2,
    }


@pytest.mark.asyncio
async def test_get_categories_filters_by_search(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    search_value = uuid4().hex[:8]

    matching_category = Category(
        id=uuid4(),
        name=f"Camera-{search_value}",
    )

    unrelated_category = Category(
        id=uuid4(),
        name=f"Furniture-{uuid4().hex[:8]}",
    )

    db_session.add_all(
        [
            matching_category,
            unrelated_category,
        ]
    )
    await db_session.commit()

    headers = await create_authenticated_headers(
        db_session=db_session,
    )

    response = await client.get(
        "/api/v1/categories",
        params={
            "search": search_value,
        },
        headers=headers,
    )

    assert response.status_code == 200

    response_data = response.json()

    assert len(response_data["data"]) == 1
    assert response_data["data"][0]["id"] == str(matching_category.id)
    assert response_data["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_get_categories_search_is_case_insensitive(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    search_value = uuid4().hex[:8]

    category = Category(
        id=uuid4(),
        name=f"MixedCase-{search_value}",
    )

    db_session.add(category)
    await db_session.commit()

    headers = await create_authenticated_headers(
        db_session=db_session,
    )

    response = await client.get(
        "/api/v1/categories",
        params={
            "search": (f"mixedcase-{search_value}"),
        },
        headers=headers,
    )

    assert response.status_code == 200

    response_data = response.json()

    assert len(response_data["data"]) == 1
    assert response_data["data"][0]["id"] == str(category.id)


@pytest.mark.asyncio
async def test_get_categories_returns_empty_data_when_no_match(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    headers = await create_authenticated_headers(
        db_session=db_session,
    )

    response = await client.get(
        "/api/v1/categories",
        params={
            "search": f"missing-{uuid4().hex}",
        },
        headers=headers,
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["success"] is True
    assert response_data["data"] == []
    assert response_data["pagination"]["total"] == 0
    assert response_data["pagination"]["total_pages"] == 0


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("page", 0),
        ("page", -1),
        ("page_size", 0),
        ("page_size", -1),
        ("page_size", 101),
    ],
)
@pytest.mark.asyncio
async def test_get_categories_rejects_invalid_pagination(
    parameter: str,
    value: int,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    headers = await create_authenticated_headers(
        db_session=db_session,
    )

    response = await client.get(
        "/api/v1/categories",
        params={
            parameter: value,
        },
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["success"] is False


@pytest.mark.asyncio
async def test_get_categories_rejects_empty_search(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    headers = await create_authenticated_headers(
        db_session=db_session,
    )

    response = await client.get(
        "/api/v1/categories",
        params={
            "search": "",
        },
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["success"] is False
