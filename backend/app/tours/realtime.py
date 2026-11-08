"""The chat gateway (architecture 8): one WebSocket per user carries all of their tours.

1. ``GET /api/v1/realtime`` upgrades with the existing ``__Host-`` session cookie; the ``Origin`` must be an
   allowed app origin (stops cross-site WebSocket hijacking).
2. The client sends ``{"type": "subscribe", "tour_id": "<public id>", "after_seq": N}``; the gateway checks
   membership and answers with the messages after N (up to 200), then pushes new ones as they commit.
3. ``{"type": "send", ...}`` stores the message first (idempotent on ``client_msg_id``) and answers ``ack``.
4. Heartbeat: the client pings every 25 seconds; the server answers ``pong``.

Fan-out happens only after the database commit (a ``after_commit`` hook), so nobody sees a message that was
rolled back. Within one process the hub hands notices to connected sockets; with ``REDIS_URL`` set, notices
are also published on Redis so every API instance delivers them. Membership is re-checked against a 5-second
cache on every delivery, and an explicit ``revoke`` (leave, removal, suspension) drops the subscription at
once, so a removed member stops receiving within 5 seconds (AC-14).
"""

import asyncio
import contextlib
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.auth.tokens import InvalidToken, verify_access_token
from app.config import get_settings
from app.db import SessionLocal
from app.errors import ApiError
from app.models import User
from app.tours import chat, policy
from app.tours.models import ChatMessage, Tour, TourMember

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["tours"])
MEMBERSHIP_TTL = 5.0
CHANNEL = "abhijatri:tour-chat"


@dataclass
class Connection:
    user_id: uuid.UUID
    queue: asyncio.Queue[dict[str, Any]]
    loop: asyncio.AbstractEventLoop
    tours: dict[uuid.UUID, str] = field(default_factory=dict)  # tour id -> public id


class Hub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connections: set[Connection] = set()
        self._membership: dict[tuple[uuid.UUID, uuid.UUID], tuple[float, bool]] = {}

    def add(self, connection: Connection) -> None:
        with self._lock:
            self._connections.add(connection)

    def remove(self, connection: Connection) -> None:
        with self._lock:
            self._connections.discard(connection)

    def is_member(self, tour_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        key = (tour_id, user_id)
        cached = self._membership.get(key)
        if cached and time.monotonic() - cached[0] < MEMBERSHIP_TTL:
            return cached[1]
        with SessionLocal() as session:
            ok = session.scalar(select(TourMember.id).where(TourMember.tour_id == tour_id, TourMember.user_id == user_id, TourMember.state == "ACTIVE")) is not None
        self._membership[key] = (time.monotonic(), ok)
        return ok

    def forget(self, tour_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self._membership[(tour_id, user_id)] = (time.monotonic(), False)

    def deliver(self, notice: dict[str, Any]) -> None:
        """Called from any thread. Hands the notice to every subscribed socket's event loop."""
        tour_id = uuid.UUID(notice["tour_id"])
        if notice.get("type") == "revoke":
            user_id = uuid.UUID(notice["user_id"])
            self.forget(tour_id, user_id)
            with self._lock:
                targets = [c for c in self._connections if c.user_id == user_id and tour_id in c.tours]
            for connection in targets:
                public_id = connection.tours.pop(tour_id, "")
                connection.loop.call_soon_threadsafe(connection.queue.put_nowait, {"type": "revoked", "tour_id": public_id})
            return
        with self._lock:
            targets = [c for c in self._connections if tour_id in c.tours]
        for connection in targets:
            payload = dict(notice) | {"tour_id": connection.tours.get(tour_id, "")}
            connection.loop.call_soon_threadsafe(connection.queue.put_nowait, payload)


HUB = Hub()
_bridge_started = False


def _publish(notice: dict[str, Any]) -> None:
    from app.redis_client import get_redis

    client = None
    with contextlib.suppress(Exception):
        client = get_redis()
    if client is not None:
        try:
            client.publish(CHANNEL, json.dumps(notice))
            return
        except Exception:  # Redis down: fall back to this instance only
            logger.warning("realtime publish failed; delivering locally only")
    HUB.deliver(notice)


def _start_bridge() -> None:
    """With Redis, every instance listens for notices published by the others."""
    global _bridge_started
    if _bridge_started:
        return
    _bridge_started = True
    from app.redis_client import get_redis

    try:
        client = get_redis()
    except Exception:
        client = None
    if client is None:
        return

    def listen() -> None:
        while True:
            try:
                pubsub = client.pubsub()  # type: ignore[no-untyped-call]
                pubsub.subscribe(CHANNEL)
                for item in pubsub.listen():
                    if item.get("type") == "message":
                        HUB.deliver(json.loads(item["data"]))
            except Exception:
                logger.warning("realtime bridge lost Redis; retrying", exc_info=True)
                time.sleep(2)

    threading.Thread(target=listen, name="realtime-bridge", daemon=True).start()


def _pending(session: Session) -> list[dict[str, Any]]:
    notices: list[dict[str, Any]] = session.info.setdefault("realtime_notices", [])
    if not session.info.get("realtime_hooked"):
        session.info["realtime_hooked"] = True

        @event.listens_for(session, "after_commit")
        def _flush(committed: Session) -> None:
            items = committed.info.pop("realtime_notices", [])
            for notice in items:
                _publish(notice)

        @event.listens_for(session, "after_rollback")
        def _drop(rolled: Session) -> None:
            rolled.info.pop("realtime_notices", None)

    return notices


def after_commit(session: Session, tour_id: uuid.UUID, seq: int, *, kind: str = "message") -> None:
    _pending(session).append({"type": kind, "tour_id": str(tour_id), "seq": seq})


def revoke(session: Session, tour_id: uuid.UUID, user_id: uuid.UUID) -> None:
    _pending(session).append({"type": "revoke", "tour_id": str(tour_id), "user_id": str(user_id)})


def revoke_all(session: Session, tour_id: uuid.UUID) -> None:
    for user_id in session.scalars(select(TourMember.user_id).where(TourMember.tour_id == tour_id)):
        revoke(session, tour_id, user_id)


# ---------------------------------------------------------------- the WebSocket


def _authenticate(websocket: WebSocket) -> uuid.UUID | None:
    settings = get_settings()
    origin = (websocket.headers.get("origin") or "").rstrip("/")
    if origin not in settings.cors_origins:
        return None
    token = websocket.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    try:
        claims = verify_access_token(token)
    except InvalidToken:
        return None
    with SessionLocal() as session:
        user = session.get(User, claims.user_id)
        if user is None or user.status != "active":
            return None
        viewer = policy.viewer_for(session, user.id)
        if not viewer.verified or not viewer.adult or not policy.feature_on("tours_chat"):
            return None
        return user.id


def _subscribe(user_id: uuid.UUID, public_id: str, after_seq: int) -> tuple[uuid.UUID, dict[str, Any]]:
    with SessionLocal() as session:
        tour = session.scalar(select(Tour).where(Tour.public_id == public_id.upper()))
        if tour is None:
            raise ApiError("NOT_FOUND")
        return tour.id, chat.history(session, policy.viewer_for(session, user_id), tour, after_seq=after_seq)


def _one(user_id: uuid.UUID, tour_id: uuid.UUID, seq: int) -> dict[str, Any] | None:
    with SessionLocal() as session:
        message = session.get(ChatMessage, (tour_id, seq))
        if message is None:
            return None
        names = chat._names(session, tour_id)  # noqa: SLF001
        return chat.view(message, names, user_id, chat._blocked(session, user_id))  # noqa: SLF001


def _send(user_id: uuid.UUID, public_id: str, body: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as session:
        try:
            tour = session.scalar(select(Tour).where(Tour.public_id == public_id.upper()))
            if tour is None:
                raise ApiError("NOT_FOUND")
            result = chat.post(
                session, policy.viewer_for(session, user_id), tour, client_msg_id=uuid.UUID(str(body.get("client_msg_id"))), body=str(body.get("body") or ""),
                reply_to=body.get("reply_to"),
            )
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise


@router.websocket("/realtime")
async def realtime(websocket: WebSocket) -> None:
    user_id = await run_in_threadpool(_authenticate, websocket)
    if user_id is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    _start_bridge()
    connection = Connection(user_id=user_id, queue=asyncio.Queue(), loop=asyncio.get_running_loop())
    HUB.add(connection)

    async def pump() -> None:
        while True:
            notice = await connection.queue.get()
            if notice["type"] == "revoked":
                await websocket.send_json(notice)
                continue
            tour_id = next((tid for tid, pid in connection.tours.items() if pid == notice["tour_id"]), None)
            if tour_id is None or not await run_in_threadpool(HUB.is_member, tour_id, user_id):
                if tour_id is not None:
                    connection.tours.pop(tour_id, None)
                    await websocket.send_json({"type": "revoked", "tour_id": notice["tour_id"]})
                continue
            message = await run_in_threadpool(_one, user_id, tour_id, int(notice["seq"]))
            if message is not None:
                await websocket.send_json({"type": "message" if notice["type"] == "message" else "update", "tour_id": notice["tour_id"], "message": message})

    sender = asyncio.create_task(pump())
    try:
        while True:
            data = await websocket.receive_json()
            kind = data.get("type")
            if kind == "ping":
                await websocket.send_json({"type": "pong"})
            elif kind == "subscribe":
                public_id = str(data.get("tour_id") or "")
                try:
                    tour_id, page = await run_in_threadpool(_subscribe, user_id, public_id, int(data.get("after_seq") or 0))
                except ApiError as error:
                    await websocket.send_json({"type": "error", "tour_id": public_id, "code": error.code})
                    continue
                connection.tours[tour_id] = public_id.upper()
                await websocket.send_json({"type": "history", "tour_id": public_id.upper(), **page})
            elif kind == "send":
                public_id = str(data.get("tour_id") or "")
                try:
                    result = await run_in_threadpool(_send, user_id, public_id, data)
                    await websocket.send_json({"type": "ack", "tour_id": public_id.upper(), "client_msg_id": data.get("client_msg_id"), "seq": result["seq"], "message": result["message"]})
                except ApiError as error:
                    await websocket.send_json({"type": "nack", "tour_id": public_id.upper(), "client_msg_id": data.get("client_msg_id"), "code": error.code})
                except (ValueError, TypeError):
                    await websocket.send_json({"type": "nack", "client_msg_id": data.get("client_msg_id"), "code": "VALIDATION_FAILED"})
            elif kind == "unsubscribe":
                for tid, pid in list(connection.tours.items()):
                    if pid == str(data.get("tour_id") or "").upper():
                        connection.tours.pop(tid, None)
    except (WebSocketDisconnect, RuntimeError, json.JSONDecodeError):
        pass
    finally:
        sender.cancel()
        HUB.remove(connection)
