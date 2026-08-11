from enum import StrEnum

class PaginationEnum:
    DEFAULT_PAGE = 1
    DEFAULT_PAGE_SIZE = 10
    MAX_PAGE_SIZE = 100

class ProductStatusEnum(StrEnum):
    ACTIVE = "Active"
    DRAFT = "Draft"
    OUT_OF_STOCK = "Out of Stock"
    ARCHIVED = "Archived"
    