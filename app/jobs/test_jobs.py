from app.core.logging import get_logger

logger = get_logger(__name__)


async def test_job(ctx: dict, name: str) -> str:
    job_id = ctx["job_id"]

    logger.ingo("ARQ test job started | job_id=%s | name=%s", job_id, name)

    return f"Hello {name}, ARQ is working"
