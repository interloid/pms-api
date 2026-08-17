import asyncio
import random
from datetime import timedelta
from decimal import Decimal

from faker import Faker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ProductStatusEnum
from app.db.session import SessionLocal
from app.models.category_model import Category
from app.models.product_model import Product
from app.utils.helpers import utc_now


fake = Faker()

random.seed(42)
Faker.seed(42)


SEED_DAYS = 90
PRODUCTS_PER_DAY = 3


CATEGORY_NAMES = [
    "Electronics",
    "Lighting",
    "Apparel",
    "Home",
    "Outdoor",
    "Stationery",
]


PRODUCT_STATUSES = [
    ProductStatusEnum.ACTIVE,
    ProductStatusEnum.DRAFT,
    ProductStatusEnum.OUT_OF_STOCK,
    ProductStatusEnum.ARCHIVED,
]


def random_created_at():
    """
    Generate a timestamp somewhere within the last 90 days.
    """
    now = utc_now()

    days_ago = random.randint(
        0,
        SEED_DAYS - 1,
    )

    seconds_ago = random.randint(
        0,
        86_399,
    )

    return now - timedelta(
        days=days_ago,
        seconds=seconds_ago,
    )


def random_updated_at(created_at):
    """
    Generate an updated timestamp that is always
    greater than or equal to created_at.
    """
    now = utc_now()

    max_delta = now - created_at

    if max_delta.total_seconds() <= 0:
        return created_at

    delta_seconds = random.randint(
        0,
        int(max_delta.total_seconds()),
    )

    updated_at = created_at + timedelta(
        seconds=delta_seconds,
    )

    return min(
        updated_at,
        now,
    )


def generate_product_name() -> str:
    brands = [
        "Acme",
        "Nova",
        "Orbit",
        "Vertex",
        "Nexus",
        "Apex",
        "Zenith",
        "Pulse",
    ]

    product_types = [
        "Pro Wireless Headphones",
        "Smart Watch",
        "Mechanical Keyboard",
        "USB-C Hub",
        "Gaming Mouse",
        "4K Monitor",
        "Bluetooth Speaker",
        "Webcam",
        "Power Bank",
        "Laptop Stand",
        "Wireless Router",
        "Action Camera",
    ]

    return (
        f"{random.choice(brands)} "
        f"{random.choice(product_types)}"
    )


def generate_sku(index: int) -> str:
    return f"SEED-{index:05d}"


async def seed_categories(
    session: AsyncSession,
) -> list[Category]:

    categories: list[Category] = []

    for name in CATEGORY_NAMES:

        result = await session.execute(
            select(Category).where(
                Category.name == name,
            )
        )

        category = result.scalar_one_or_none()

        if category is not None:
            categories.append(category)
            continue

        created_at = random_created_at()

        category = Category(
            name=name,
            created_at=created_at,
            updated_at=random_updated_at(
                created_at,
            ),
        )

        session.add(category)

        await session.flush()

        categories.append(category)

    return categories


async def seed_products(
    session: AsyncSession,
    categories: list[Category],
) -> tuple[list[Product], int]:

    products: list[Product] = []

    skipped = 0

    sku_counter = 1

    total_products = SEED_DAYS * PRODUCTS_PER_DAY

    for _ in range(total_products):

        sku = generate_sku(
            sku_counter,
        )

        sku_counter += 1

        # --------------------------------------------------
        # Skip product if this seed SKU already exists.
        # This makes the script safe to run again.
        # --------------------------------------------------

        result = await session.execute(
            select(Product).where(
                Product.sku == sku,
            )
        )

        existing_product = result.scalar_one_or_none()

        if existing_product is not None:
            skipped += 1
            continue

        created_at = random_created_at()

        stock = random.randint(
            0,
            500,
        )

        price = Decimal(
            f"{random.uniform(9.99, 2499.99):.2f}"
        )

        product_status = random.choice(
            PRODUCT_STATUSES,
        )

        # An out-of-stock product must have zero stock.
        if product_status == ProductStatusEnum.OUT_OF_STOCK:
            stock = 0

        product = Product(
            name=generate_product_name(),
            sku=sku,
            price=price,
            stock=stock,
            status=product_status,
            description=fake.paragraph(
                nb_sentences=3,
            ),
            category_id=random.choice(
                categories,
            ).id,
            created_at=created_at,
            updated_at=random_updated_at(
                created_at,
            ),
        )

        session.add(product)

        products.append(product)

    if products:
        await session.flush()

    return products, skipped


async def seed():
    async with SessionLocal() as session:

        try:
            print("Starting database seed...")

            # --------------------------------------------------
            # Categories
            # --------------------------------------------------

            categories = await seed_categories(
                session,
            )

            print(
                f"Categories available: "
                f"{len(categories)}"
            )

            # --------------------------------------------------
            # Products
            # --------------------------------------------------

            products, skipped = await seed_products(
                session,
                categories,
            )

            # --------------------------------------------------
            # Commit
            # --------------------------------------------------

            await session.commit()

            print()
            print("Seed completed successfully.")
            print("--------------------------------")
            print(
                f"Categories: {len(categories)}"
            )
            print(
                f"Products created: {len(products)}"
            )
            print(
                f"Products skipped: {skipped}"
            )
            print(
                "Product images: 0"
            )
            print("--------------------------------")
            print(
                "You can now upload product images "
                "through the image upload endpoint."
            )

        except Exception:
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(seed())
    
    