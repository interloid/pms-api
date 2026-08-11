from app.core import PaginationEnum


def get_offset(page: int, page_size: int) -> int:

    page = max(page, int(PaginationEnum.DEFAULT_PAGE))
    page_size = min(page_size, int(PaginationEnum.DEFAULT_PAGE_SIZE))

    return (page - 1) * page_size
