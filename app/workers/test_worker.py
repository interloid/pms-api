from app.core.arq import (
    ARQ_QUEUE_NAME,
    ARQ_REDIS_SETTINGS,
)
from app.jobs.test_jobs import test_job


class WorkerSettings:
    functions = [
        test_job,
    ]

    redis_settings = ARQ_REDIS_SETTINGS
    queue_name = ARQ_QUEUE_NAME

    max_jobs = 10
    job_timeout = 300
    max_tries = 5
    keep_result = 3600
