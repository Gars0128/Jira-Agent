import json
import time
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import Settings
from app.projects import projects
from app.run_contracts import RunResult
from app.run_service import RunService, preset_key
from app.run_store import RunLimitError
from app.schemas import NonBlankString
from app.workflow import Approval

router = APIRouter()


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    project_id: NonBlankString = Field(max_length=100)
    transcript: NonBlankString = Field(max_length=20_000)
    preset_id: str | None = Field(default=None, max_length=100)


def service(request: Request) -> RunService:
    with request.app.state.service_lock:
        if request.app.state.service is None:
            try:
                instance = RunService(Settings())
                instance.start()
                request.app.state.service = instance
            except Exception:
                raise HTTPException(
                    503, "Run service unavailable; check server configuration"
                ) from None
    return request.app.state.service


@router.get("/projects")
def list_projects() -> dict:
    return {"projects": projects()}


@router.get("/capabilities")
def capabilities() -> dict:
    try:
        settings = Settings()
    except ValidationError:
        raise HTTPException(503, "Server configuration is incomplete") from None
    return {
        "public_demo": settings.public_demo,
        "jira_dry_run": settings.public_demo or settings.jira_dry_run,
        "transcript_limit": 20_000,
    }


@router.get("/ready")
def ready(runtime: RunService = Depends(service)) -> dict:
    with runtime.store.locked("readiness") as conn:
        if conn is None:
            raise HTTPException(503, "Database is busy")
        conn.execute("SELECT 1")
    return {"status": "ready"}


@router.post("/runs", status_code=202)
def create_run(body: RunRequest, runtime: RunService = Depends(service)) -> dict:
    project = next((item for item in projects() if item["id"] == body.project_id), None)
    if project is None:
        raise HTTPException(404, "Unknown project")
    if runtime.settings.public_demo and body.preset_id is not None:
        preset = next(
            (item for item in project["transcripts"] if item["id"] == body.preset_id),
            None,
        )
        if preset is None or preset["text"] != body.transcript:
            raise HTTPException(422, "Preset transcript does not match")
    try:
        key = preset_key(runtime.settings, body.project_id, body.transcript)
        run_id = runtime.store.create(body.project_id, body.transcript, key)
    except RunLimitError as exc:
        raise HTTPException(429, str(exc), headers={"Retry-After": "60"}) from None
    return {"run_id": run_id}


@router.get("/runs/{run_id}", response_model=RunResult)
def get_run(run_id: UUID, runtime: RunService = Depends(service)) -> dict:
    result = runtime.store.get(str(run_id))
    if result is None:
        raise HTTPException(404, "Unknown run")
    return result


@router.post("/runs/{run_id}/approve", response_model=RunResult)
def approve(
    run_id: UUID, body: Approval, runtime: RunService = Depends(service)
) -> dict:
    try:
        result = runtime.execute(str(run_id), body)
    except (ValidationError, ValueError):
        raise HTTPException(
            409, "Approval rejected; check run state and requirement coverage"
        ) from None
    if result is None:
        raise HTTPException(404, "Unknown run")
    return result


@router.get("/runs/{run_id}/events")
def events(
    run_id: UUID,
    after: int = Query(default=0, ge=0),
    last_event_id: str | None = Header(default=None),
    runtime: RunService = Depends(service),
) -> StreamingResponse:
    identifier = str(run_id)
    if runtime.store.get(identifier) is None:
        raise HTTPException(404, "Unknown run")
    try:
        cursor = max(after, int(last_event_id or 0))
        if cursor < 0:
            raise ValueError
    except ValueError:
        raise HTTPException(400, "Invalid Last-Event-ID") from None

    def stream():
        nonlocal cursor
        while True:
            batch = runtime.store.events(identifier, cursor)
            for event_id, body in batch:
                cursor = event_id
                yield f"id: {event_id}\ndata: {json.dumps(body)}\n\n"
            current = runtime.store.get(identifier)
            if current is None or current["status"] in {
                "done",
                "error",
                "awaiting_review",
            }:
                if not batch:
                    return
                continue
            yield ": keep-alive\n\n"
            time.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
