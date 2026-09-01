from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleEnum
from app.core.security import create_access_token
from app.models.category_model import Category
from app.models.product_model import Product
from app.models.user_model import User


@pytest.mark.asyncio
async def test_viewer_cannot_delete_product(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    viewer = User(
        email=f"viewer-{uuid4()}@example.com",
        first_name="Viewer",
        last_name="User",
        is_active=True,
        role=RoleEnum.VIEWER,
    )

    db_session.add(viewer)
    await db_session.commit()

    access_token = create_access_token({"sub": str(viewer.id)})
    headers = {"Authorization": f"Bearer {access_token}"}

    product_id = uuid4()
    response = await client.delete(f"/api/v1/products/{product_id}", headers=headers)

    assert response.status_code == 403
    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_viewer_can_list_products(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    viewer = User(
        email=f"viewer-{uuid4()}@example.com",
        first_name="Viewer",
        last_name="User",
        is_active=True,
        role=RoleEnum.VIEWER,
    )

    db_session.add(viewer)
    await db_session.commit()

    access_token = create_access_token({"sub": str(viewer.id)})
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await client.get("/api/v1/products", headers=headers)

    assert response.status_code == 200
    response_data = response.json()

    assert response_data["success"] is True


@pytest.mark.asyncio
async def test_editor_can_create_product(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    editor = User(
        email=f"viewer-{uuid4()}@example.com",
        first_name="Viewer",
        last_name="User",
        is_active=True,
        role=RoleEnum.EDITOR,
    )
    category_name = f"Category-{uuid4().hex[:8]}"
    category = Category(name=category_name)

    product_data = {
        "name": "Test Laptop",
        "sku": f"SKU-{uuid4().hex[:8]}",
        "category_name": category_name,
        "price": "20.00",
        "stock": "10",
        "status": "active",
    }

    db_session.add_all([editor, category])
    await db_session.commit()

    access_token = create_access_token({"sub": str(editor.id)})
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await client.post("/api/v1/products", headers=headers, data=product_data)

    assert response.status_code == 201
    print(response.status_code, response.json())
    response_data = response.json()

    assert response_data["success"] is True
    assert response_data["data"]["sku"] == product_data["sku"]
    assert response_data["data"]["category_name"] == category_name


@pytest.mark.asyncio
async def test_editor_cannot_delete_product(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    editor = User(
        email=f"editor-{uuid4()}@example.com",
        first_name="Editor",
        last_name="User",
        is_active=True,
        role=RoleEnum.EDITOR,
    )

    db_session.add(editor)
    await db_session.commit()

    access_token = create_access_token({"sub": str(editor.id)})
    headers = {"Authorization": f"Bearer {access_token}"}

    product_id = uuid4()
    response = await client.delete(f"/api/v1/products/{product_id}", headers=headers)

    assert response.status_code == 403
    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_delete_missing_product_returns_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = User(
        email=f"editor-{uuid4()}@example.com",
        first_name="Editor",
        last_name="User",
        is_active=True,
        role=RoleEnum.ADMIN,
    )

    db_session.add(admin)
    await db_session.commit()

    access_token = create_access_token({"sub": str(admin.id)})
    headers = {"Authorization": f"Bearer {access_token}"}

    product_id = uuid4()
    response = await client.delete(f"/api/v1/products/{product_id}", headers=headers)

    assert response.status_code == 404
    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_admin_can_delete_existing_product(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = User(
        email=f"admin-{uuid4()}@example.com",
        first_name="Admin",
        last_name="User",
        is_active=True,
        role=RoleEnum.ADMIN,
    )

    category = Category(
        name=f"Category-{uuid4().hex[:8]}",
    )

    db_session.add_all([admin, category])
    await db_session.flush()

    product = Product(
        name="Admin Delete Product",
        sku=f"SKU-{uuid4().hex[:8]}",
        category_id=category.id,
        price=Decimal("20.00"),
        stock=10,
        status="active",
        description="Product created for admin delete test",
    )

    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)

    product_id = product.id

    access_token = create_access_token(
        {"sub": str(admin.id)},
    )
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    response = await client.delete(
        f"/api/v1/products/{product_id}",
        headers=headers,
    )

    assert response.status_code == 204
    assert response.content == b""

    deleted_product = await db_session.get(
        Product,
        product_id,
    )

    assert deleted_product is None


@pytest.mark.asyncio
async def test_viewer_cannot_create_product(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    viewer = User(
        email=f"viewer-{uuid4()}@example.com",
        first_name="Viewer",
        last_name="User",
        is_active=True,
        role=RoleEnum.VIEWER,
    )

    db_session.add(viewer)
    await db_session.commit()

    access_token = create_access_token(
        {"sub": str(viewer.id)},
    )
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    product_data = {
        "name": "Viewer Product",
        "sku": f"SKU-{uuid4().hex[:8]}",
        "category_name": f"Category-{uuid4().hex[:8]}",
        "price": "20.00",
        "stock": "10",
        "status": "active",
    }

    response = await client.post(
        "/api/v1/products",
        data=product_data,
        headers=headers,
    )

    assert response.status_code == 403

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_editor_can_update_existing_product(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    editor = User(
        email=f"editor-{uuid4()}@example.com",
        first_name="Editor",
        last_name="User",
        is_active=True,
        role=RoleEnum.EDITOR,
    )

    category = Category(
        name=f"Category-{uuid4().hex[:8]}",
    )

    db_session.add_all([editor, category])
    await db_session.flush()

    product = Product(
        name="Original Product",
        sku=f"SKU-{uuid4().hex[:8]}",
        category_id=category.id,
        price=Decimal("20.00"),
        stock=10,
        status="active",
        description="Original description",
    )

    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)

    access_token = create_access_token(
        {"sub": str(editor.id)},
    )
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    update_data = {
        "name": "Updated Product",
        "stock": "25",
        "description": "Updated description",
    }

    response = await client.patch(
        f"/api/v1/products/{product.id}",
        data=update_data,
        headers=headers,
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["success"] is True
    assert response_data["data"]["name"] == "Updated Product"
    assert response_data["data"]["stock"] == 25
    assert response_data["data"]["description"] == "Updated description"

    await db_session.refresh(product)

    assert product.name == "Updated Product"
    assert product.stock == 25
    assert product.description == "Updated description"


@pytest.mark.asyncio
async def test_viewer_cannot_update_product(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    viewer = User(
        email=f"viewer-{uuid4()}@example.com",
        first_name="Viewer",
        last_name="User",
        is_active=True,
        role=RoleEnum.VIEWER,
    )

    db_session.add(viewer)
    await db_session.commit()

    access_token = create_access_token(
        {"sub": str(viewer.id)},
    )
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    update_data = {
        "name": "Unauthorized Update",
    }

    response = await client.patch(
        f"/api/v1/products/{uuid4()}",
        data=update_data,
        headers=headers,
    )

    assert response.status_code == 403

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "FORBIDDEN"
