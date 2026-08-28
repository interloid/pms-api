from enum import StrEnum


class PaginationEnum:
    DEFAULT_PAGE = 1
    DEFAULT_PAGE_SIZE = 10
    MAX_PAGE_SIZE = 100


class ProductStatusEnum(StrEnum):
    ACTIVE = "active"
    DRAFT = "draft"
    OUT_OF_STOCK = "out_of_stock"
    ARCHIVED = "archived"


class OAuthProviderEnum(StrEnum):
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    GITHUB = "github"


class ProductImageConstants:
    MAX_IMAGES = 6
    MAX_FILE_SIZE = 5 * 1024 * 1024

    ALLOWED_CONTENT_TYPES = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }
