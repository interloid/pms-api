from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):

    print("Application starting...")

    yield

    print("Application shutting down...")
