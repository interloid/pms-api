from typing import Any

from arq import Retry

from app.services.email_services import send_passcode_email


async def send_passcode_email_job(
    ctx: dict[str, Any],
    to_email: str,
    first_name: str,
    passcode: str,
    expiry_minutes: int,
    # _expires: int,
) -> None:

    try:
        await send_passcode_email(
            to_email=to_email,
            first_name=first_name,
            passcode=passcode,
            expiry_minutes=expiry_minutes,
            # _expires=_expires,
        )
    except Exception as exc:
        raise Retry(defer=min(ctx["job_try"] * 10, 60)) from exc
