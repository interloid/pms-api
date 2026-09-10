import json
from typing import Any

from arq import Retry

from app.core.logging import get_logger
from app.services.email_services import send_passcode_email

logger = get_logger(__name__)


async def send_passcode_email_job(
    ctx: dict[str, Any],
    email_job_id: str,
) -> None:

    key = f"jobs:passcode-email:{email_job_id}"

    if await ctx["redis"].exists(key):
        return

    raw_data = await ctx["redis"].get(key)

    if raw_data is None:
        return
    email_data = json.loads(raw_data)

    try:
        await send_passcode_email(
            to_email=email_data["to_email"],
            first_name=email_data["first_name"],
            passcode=email_data["passcode"],
            expiry_minutes=email_data["expiry_minutes"],
        )

    except Exception as exc:
        retry_delay = min(ctx.get("job_try", 1) * 10, 60)
        logger.exception("Passcode email delivery failed")
        raise Retry(defer=retry_delay) from exc
    else:
        await ctx["redis"].set(key, "1", ex=86_400)
        await ctx["redis"].delete(key)
