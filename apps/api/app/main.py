import logging
from contextlib import asynccontextmanager
from threading import Lock

import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    sdk_logger = logging.getLogger("langsmith")
    sdk_logger.handlers = [logging.NullHandler()]
    sdk_logger.propagate = False
    yield
    if app.state.service:
        app.state.service.close()


app = FastAPI(title="Discovery to Jira Agent", lifespan=lifespan)
app.state.service = None
app.state.service_lock = Lock()
app.include_router(router)


@app.exception_handler(psycopg.Error)
async def database_error(request: Request, exc: psycopg.Error) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
