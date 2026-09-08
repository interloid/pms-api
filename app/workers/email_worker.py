from app.core.arq import ARQ_QUEUE_NAME, ARQ_REDIS_SETTINGS
from app.jobs.email_jobs import send_passcode_email_job


class WorkerSettings:
    functions = [send_passcode_email_job]
    redis_settings = ARQ_REDIS_SETTINGS
    queue_name = ARQ_QUEUE_NAME
