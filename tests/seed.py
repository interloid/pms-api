import asyncio

from app.core.security import hash_password
from app.db.database import engine
from app.db.session import SessionLocal
from app.models.category_model import Category
from app.models.product_image_model import ProductImage
from app.models.product_model import Product
from app.models.user_model import User


async def seed():
    async with SessionLocal() as db:
        try:
            # -------------------------
            # User
            # -------------------------
            user = User(
                email="admin@example.com",
                hashed_password=hash_password("password123"),
                first_name="Admin",
                last_name="User",
                phone_number="9876543210",
                is_active=True,
            )

            db.add(user)

            # -------------------------
            # Categories
            # -------------------------
            electronics = Category(
                name="Electronics",
            )

            furniture = Category(
                name="Furniture",
            )

            db.add_all([electronics, furniture])

            await db.flush()

            # -------------------------
            # Products
            # -------------------------
            laptop = Product(
                name="Dell Laptop",
                sku="LAP-001",
                price=Decimal("75000.00"),
                stock=10,
                status="active",
                description="Dell business laptop",
                category_id=electronics.id,
            )

            phone = Product(
                name="Samsung Galaxy",
                sku="PHONE-001",
                price=Decimal("45000.00"),
                stock=20,
                status="active",
                description="Samsung smartphone",
                category_id=electronics.id,
            )

            chair = Product(
                name="Office Chair",
                sku="CHAIR-001",
                price=Decimal("8500.00"),
                stock=15,
                status="active",
                description="Ergonomic office chair",
                category_id=furniture.id,
            )

            db.add_all([laptop, phone, chair])

            await db.flush()

            # -------------------------
            # Product Images
            # -------------------------
            images = [
                ProductImage(
                    product_id=laptop.id,
                    url="https://example.com/images/laptop.jpg",
                    is_primary=True,
                ),
                ProductImage(
                    product_id=phone.id,
                    url="https://example.com/images/phone.jpg",
                    is_primary=True,
                ),
                ProductImage(
                    product_id=chair.id,
                    url="https://example.com/images/chair.jpg",
                    is_primary=True,
                ),
            ]

            db.add_all(images)

            await db.commit()

            print("Seed completed successfully.")

            print("\nLogin credentials:")
            print("Email: admin@example.com")
            print("Password: password123")

        except Exception:
            await db.rollback()
            raise

        finally:
            await engine.dispose()


if __name__ == "__main__":
    from decimal import Decimal

    asyncio.run(seed())
