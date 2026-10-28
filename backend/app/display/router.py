import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core import clock
from app.core.db import SessionFactory, get_db, get_session_factory
from app.core.events import broker
from app.display import service
from app.modules.models import ModuleName

Db = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/display", tags=["display"])

KEEPALIVE_SECONDS = 20.0


@router.get("")
def get_all(db: Db) -> dict[str, Any]:
    return service.snapshot(db, clock.now())


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _render(open_session: SessionFactory, topics: set[str]) -> list[str]:
    with open_session() as db:
        now = clock.now()
        if "modules" in topics:
            return [_sse("snapshot", service.snapshot(db, now))]
        return [
            _sse("module", {"name": topic, **service.module_envelope(db, ModuleName(topic), now)})
            for topic in sorted(topics)
            if topic in ModuleName.__members__.values()
        ]


@router.get("/stream")
async def stream(
    request: Request, open_session: Annotated[SessionFactory, Depends(get_session_factory)]
) -> StreamingResponse:
    queue = broker.subscribe()

    async def events() -> AsyncIterator[str]:
        try:
            yield "retry: 5000\n\n"
            for chunk in await run_in_threadpool(_render, open_session, {"modules"}):
                yield chunk
            while not await request.is_disconnected():
                try:
                    topics = {await asyncio.wait_for(queue.get(), KEEPALIVE_SECONDS)}
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                while not queue.empty():
                    topics.add(queue.get_nowait())
                for chunk in await run_in_threadpool(_render, open_session, topics):
                    yield chunk
        finally:
            broker.unsubscribe(queue)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{name}")
def get_module(name: ModuleName, db: Db) -> dict[str, Any]:
    return service.module_envelope(db, name, clock.now())
