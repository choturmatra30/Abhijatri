"""Native tour chat (spec 14; architecture 8): the service shared by REST and the WebSocket gateway.

- Open only when the tour is Confirmed, and only to active members (14.1.1). Read only when Suspended,
  Cancelled or Completed; deleted at archive except messages held for an open report.
- Each tour has a strict order: ``seq`` comes from ``chat_channels.last_seq`` incremented under a row lock in
  the insert transaction, so clients fetch "everything after seq N" (architecture 5.4).
- A message carries a client-generated ``client_msg_id``; a retry from the offline queue returns the stored
  message instead of creating a second one (14.2.2; AC-15).
- Messages are stored before fan-out, so a lost publish delays delivery but never loses a message.
"""

import re
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ApiError
from app.models import User
from app.tours import policy
from app.tours.models import (
    ChatChannel,
    ChatMessage,
    ChatRead,
    Tour,
    TourMember,
    TourReport,
    UserBlock,
)
from app.tours.policy import Viewer, now

EDIT_WINDOW = timedelta(minutes=15)
PAGE = 200
REPORT_CONTEXT = 10  # messages on each side: "the 20 messages around it" (14.1.6)
LINK = re.compile(r"https?://[^\s]+", re.IGNORECASE)
SAFE_LINK_HOSTS = ("abhijatri.vercel.app", "maps.google.com", "www.google.com", "goo.gl", "bangladesh.gov.bd")


def _member(session: Session, viewer: Viewer, tour: Tour) -> TourMember:
    member = policy.membership(session, tour.id, viewer.user_id)
    if member is None or member.state != "ACTIVE":
        raise ApiError("NOT_FOUND")  # a non-member, pending requester or removed member reads nothing (AC-14)
    if not policy.feature_on("tours_chat"):
        raise ApiError("NOT_FOUND")
    if tour.confirmed_at is None:
        raise ApiError("CHAT_LOCKED")
    return member


def writable(tour: Tour) -> bool:
    return tour.lifecycle in ("CONFIRMED", "ONGOING") and tour.suspended_at is None


def unread(session: Session, tour_id: uuid.UUID, user_id: uuid.UUID) -> int:
    channel = session.get(ChatChannel, tour_id)
    if channel is None:
        return 0
    read = session.get(ChatRead, (tour_id, user_id))
    return max(channel.last_seq - (read.last_read_seq if read else 0), 0)


def _links(body: str) -> list[dict[str, Any]]:
    out = []
    for match in LINK.findall(body or ""):
        host = re.sub(r"^https?://", "", match, flags=re.IGNORECASE).split("/")[0].lower()
        out.append({"url": match, "host": host, "warn": not host.endswith(SAFE_LINK_HOSTS)})
    return out


def view(message: ChatMessage, names: dict[uuid.UUID, str], viewer_id: uuid.UUID, blocked: set[uuid.UUID], seen: int = 0) -> dict[str, Any]:
    removed = message.hidden_by_staff_at is not None
    deleted = message.deleted_at is not None
    body = None if (removed or deleted) else message.body
    return {
        "seq": message.seq,
        "id": str(message.id),
        "client_msg_id": str(message.client_msg_id) if message.client_msg_id else None,
        "kind": message.kind,
        "sender": names.get(message.sender_id) if message.sender_id else None,
        "is_you": message.sender_id == viewer_id,
        "body": body,
        "status": "removed" if removed else ("deleted" if deleted else "ok"),
        "reply_to": message.reply_to,
        "edited": message.edited_at is not None,
        "pinned": message.pinned_at is not None,
        "collapsed": message.sender_id in blocked,  # 14.1.7: a blocked member's messages are collapsed
        "links": _links(body or ""),
        "seen_by": seen,  # a count, never names (14.1.8)
        "created_at": message.created_at.isoformat(),
    }


def _names(session: Session, tour_id: uuid.UUID) -> dict[uuid.UUID, str]:
    rows = session.execute(select(TourMember.user_id, User.display_name).join(User, User.id == TourMember.user_id).where(TourMember.tour_id == tour_id))
    return {user_id: policy.first_name(name) for user_id, name in rows}


def _blocked(session: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    return set(session.scalars(select(UserBlock.blocked_id).where(UserBlock.blocker_id == user_id)))


def history(session: Session, viewer: Viewer, tour: Tour, *, after_seq: int = 0, before_seq: int | None = None, limit: int = PAGE) -> dict[str, Any]:
    _member(session, viewer, tour)
    statement = select(ChatMessage).where(ChatMessage.tour_id == tour.id)
    if before_seq is not None:
        statement = statement.where(ChatMessage.seq < before_seq).order_by(ChatMessage.seq.desc()).limit(min(limit, PAGE))
        rows = list(reversed(list(session.scalars(statement))))
    else:
        statement = statement.where(ChatMessage.seq > after_seq).order_by(ChatMessage.seq).limit(min(limit, PAGE))
        rows = list(session.scalars(statement))
    names = _names(session, tour.id)
    blocked = _blocked(session, viewer.user_id)
    reads = sorted(session.scalars(select(ChatRead.last_read_seq).where(ChatRead.tour_id == tour.id, ChatRead.user_id != viewer.user_id)))
    channel = session.get(ChatChannel, tour.id)
    read = session.get(ChatRead, (tour.id, viewer.user_id))
    return {
        "items": [view(m, names, viewer.user_id, blocked, seen=sum(1 for r in reads if r >= m.seq)) for m in rows],
        "last_seq": channel.last_seq if channel else 0,
        "writable": writable(tour),
        "muted": bool(read and read.muted),
        "last_read_seq": read.last_read_seq if read else 0,
    }


def post(session: Session, viewer: Viewer, tour: Tour, *, client_msg_id: uuid.UUID, body: str, reply_to: int | None, announcement: bool = False) -> dict[str, Any]:
    member = _member(session, viewer, tour)
    if not writable(tour):
        raise ApiError("CHAT_READ_ONLY")
    policy.require_unrestricted(viewer)
    text = (body or "").strip()
    if not 1 <= len(text) <= 2000:
        raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "body", "code": "LENGTH"}])
    if announcement and not policy.can(member.role, "chat.pin"):
        raise ApiError("FORBIDDEN")
    existing = session.scalar(select(ChatMessage).where(ChatMessage.tour_id == tour.id, ChatMessage.sender_id == viewer.user_id, ChatMessage.client_msg_id == client_msg_id))
    if existing is not None:
        return {"seq": existing.seq, "duplicate": True, "message": view(existing, _names(session, tour.id), viewer.user_id, set())}
    recent = session.scalar(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.tour_id == tour.id, ChatMessage.sender_id == viewer.user_id, ChatMessage.created_at > now() - timedelta(minutes=1))
    ) or 0
    if recent >= get_settings().tour_chat_messages_per_minute:
        raise ApiError("RATE_LIMITED", headers={"Retry-After": "30"})  # 14.1.9
    channel = session.scalar(select(ChatChannel).where(ChatChannel.tour_id == tour.id).with_for_update())
    if channel is None:
        raise ApiError("CHAT_LOCKED")
    if reply_to is not None and not session.get(ChatMessage, (tour.id, reply_to)):
        reply_to = None
    channel.last_seq += 1
    seq = channel.last_seq
    inserted = session.execute(
        insert(ChatMessage)
        .values(
            tour_id=tour.id, seq=seq, id=uuid.uuid4(), sender_id=viewer.user_id, client_msg_id=client_msg_id, kind="ANNOUNCEMENT" if announcement else "TEXT",
            body=text, reply_to=reply_to, pinned_at=now() if announcement else None, created_at=now(),
        )
        .on_conflict_do_nothing()
        .returning(ChatMessage.seq)
    ).scalar()
    if inserted is None:  # a twin with this client id committed first
        channel.last_seq -= 1
        twin = session.scalar(select(ChatMessage).where(ChatMessage.tour_id == tour.id, ChatMessage.sender_id == viewer.user_id, ChatMessage.client_msg_id == client_msg_id))
        assert twin is not None
        return {"seq": twin.seq, "duplicate": True, "message": view(twin, _names(session, tour.id), viewer.user_id, set())}
    mark_read(session, viewer, tour, seq)
    from app.tours import realtime

    realtime.after_commit(session, tour.id, seq)
    message = session.get(ChatMessage, (tour.id, seq))
    assert message is not None
    return {"seq": seq, "duplicate": False, "message": view(message, _names(session, tour.id), viewer.user_id, set())}


def _own_message(session: Session, tour: Tour, seq: int) -> ChatMessage:
    message = session.scalar(select(ChatMessage).where(ChatMessage.tour_id == tour.id, ChatMessage.seq == seq).with_for_update())
    if message is None or message.kind == "SYSTEM":
        raise ApiError("NOT_FOUND")
    return message


def edit(session: Session, viewer: Viewer, tour: Tour, seq: int, body: str) -> dict[str, Any]:
    _member(session, viewer, tour)
    if not writable(tour):
        raise ApiError("CHAT_READ_ONLY")
    message = _own_message(session, tour, seq)
    if message.sender_id != viewer.user_id or message.deleted_at is not None or message.hidden_by_staff_at is not None:
        raise ApiError("FORBIDDEN")
    if now() - message.created_at > EDIT_WINDOW:
        raise ApiError("EDIT_WINDOW_CLOSED")  # 14.1.5
    text = (body or "").strip()
    if not 1 <= len(text) <= 2000:
        raise ApiError("VALIDATION_FAILED", field_errors=[{"field": "body", "code": "LENGTH"}])
    message.body, message.edited_at = text, now()
    from app.tours import realtime

    realtime.after_commit(session, tour.id, seq, kind="update")
    return view(message, _names(session, tour.id), viewer.user_id, set())


def delete(session: Session, viewer: Viewer, tour: Tour, seq: int) -> dict[str, Any]:
    member = _member(session, viewer, tour)
    message = _own_message(session, tour, seq)
    if message.sender_id != viewer.user_id and not policy.can(member.role, "chat.delete_any"):
        raise ApiError("FORBIDDEN")
    message.deleted_at = now()
    from app.tours import realtime

    realtime.after_commit(session, tour.id, seq, kind="update")
    return view(message, _names(session, tour.id), viewer.user_id, set())


def pin(session: Session, viewer: Viewer, tour: Tour, seq: int, pinned: bool) -> dict[str, Any]:
    member = _member(session, viewer, tour)
    if not policy.can(member.role, "chat.pin"):
        raise ApiError("FORBIDDEN")
    message = _own_message(session, tour, seq)
    message.pinned_at = now() if pinned else None
    from app.tours import realtime

    realtime.after_commit(session, tour.id, seq, kind="update")
    return view(message, _names(session, tour.id), viewer.user_id, set())


def mark_read(session: Session, viewer: Viewer, tour: Tour, seq: int) -> None:
    session.execute(
        insert(ChatRead).values(tour_id=tour.id, user_id=viewer.user_id, last_read_seq=seq).on_conflict_do_update(
            index_elements=[ChatRead.tour_id, ChatRead.user_id], set_={"last_read_seq": func.greatest(ChatRead.last_read_seq, seq)}
        )
    )


def mute(session: Session, viewer: Viewer, tour: Tour, muted: bool) -> None:
    _member(session, viewer, tour)
    session.execute(
        insert(ChatRead).values(tour_id=tour.id, user_id=viewer.user_id, last_read_seq=0, muted=muted).on_conflict_do_update(
            index_elements=[ChatRead.tour_id, ChatRead.user_id], set_={"muted": muted}
        )
    )


def report(session: Session, viewer: Viewer, tour: Tour, seq: int, reason_code: str, details: str | None) -> TourReport:
    """14.1.6: the message and the 20 around it are attached, and kept even through deletion or archive."""
    from app.admin import tasks
    from app.tours import reports

    _member(session, viewer, tour)
    reports.check_reason(reason_code)
    target = _own_message(session, tour, seq)
    around = list(
        session.scalars(
            select(ChatMessage).where(ChatMessage.tour_id == tour.id, ChatMessage.seq.between(seq - REPORT_CONTEXT, seq + REPORT_CONTEXT)).order_by(ChatMessage.seq)
        )
    )
    names = _names(session, tour.id)
    for message in around:
        message.held_for_report = True
    snapshot = [
        {"seq": m.seq, "sender": names.get(m.sender_id) if m.sender_id else "system", "sender_id": str(m.sender_id) if m.sender_id else None, "body": m.body, "kind": m.kind, "at": m.created_at.isoformat(), "reported": m.seq == seq}
        for m in around
    ]
    item = TourReport(
        tour_id=tour.id, reporter_id=viewer.user_id, subject_kind="MESSAGE", subject_id=target.id, reason_code=reason_code,
        details=(details or "")[:1000] or None, context={"messages": snapshot},
    )
    session.add(item)
    session.flush()
    tasks.ensure_task(session, "chat_report", item.id, priority=2 if reason_code in ("safety", "harassment") else 1)
    return item


def staff_history(session: Session, tour: Tour, *, limit: int = PAGE) -> list[dict[str, Any]]:
    """Break-glass read (16.3); the caller has checked the grant and audits the read."""
    rows = list(reversed(list(session.scalars(select(ChatMessage).where(ChatMessage.tour_id == tour.id).order_by(ChatMessage.seq.desc()).limit(limit)))))
    names = _names(session, tour.id)
    return [view(m, names, uuid.UUID(int=0), set()) | {"body": m.body, "sender_id": str(m.sender_id) if m.sender_id else None} for m in rows]
