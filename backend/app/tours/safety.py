"""Safety module (spec 13.4; architecture 5.5, 10.4).

- Each member's emergency contact and medical notes are sealed separately (``app.fieldcrypt``). Organisers can
  read them only while the tour is Ongoing, or for 24 hours after an SOS; every read is audited (AC-17).
- Meeting points are visible to members only. Check-ins highlight members who have not answered in 30 minutes.
- The SOS screen shows 999, the destination's emergency contacts from the guide, and the meeting point; an
  SOS alerts every member and gives the safety queue 24 hours of access (16.3). No location tracking.
- 30 days after the tour ends, contacts, medical notes and companions' details are deleted (crypto-shredded).
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import fieldcrypt
from app.admin import audit, tasks
from app.errors import ApiError
from app.models import DestinationContact, EmergencyContactDefault, User
from app.tours import policy, service
from app.tours.models import (
    BreakglassGrant,
    CheckIn,
    CheckInAnswer,
    MeetingPoint,
    SafetyProfile,
    SosEvent,
    Tour,
    TourMember,
    TourReport,
)
from app.tours.policy import Viewer, now

SOS_WINDOW = timedelta(hours=24)
CHECKIN_GRACE = timedelta(minutes=30)
PURGE_AFTER = timedelta(days=30)


def _bad(field: str, code: str = "INVALID_VALUE") -> ApiError:
    return ApiError("VALIDATION_FAILED", field_errors=[{"field": field, "code": code}])


def _member(session: Session, viewer: Viewer, tour: Tour) -> TourMember:
    member = policy.membership(session, tour.id, viewer.user_id)
    if member is None or member.state != "ACTIVE":
        raise ApiError("NOT_FOUND")
    if not policy.feature_on("tours_safety") or tour.confirmed_at is None:
        raise ApiError("CHAT_LOCKED")
    return member


def _aad(member_id: uuid.UUID, part: str) -> str:
    return f"safety:{member_id}:{part}"


def _open(blob: bytes | None, aad: str) -> Any:
    if not blob:
        return None
    try:
        return json.loads(fieldcrypt.open_text(blob, aad=aad) or "null")
    except (fieldcrypt.SealError, ValueError):
        return None


def sos_active(session: Session, tour_id: uuid.UUID) -> bool:
    return session.scalar(select(SosEvent.id).where(SosEvent.tour_id == tour_id, SosEvent.created_at > now() - SOS_WINDOW).limit(1)) is not None


def reveal_open(session: Session, tour: Tour) -> bool:
    """Others' contacts: only during Ongoing, or on an SOS (13.2 table, 13.4.1)."""
    return tour.lifecycle == "ONGOING" or sos_active(session, tour.id)


def copy_default_contact(session: Session, member: TourMember) -> None:
    """The emergency contact from the verification application is copied in when a person joins (sign-up form 7)."""
    if session.get(SafetyProfile, member.id) is not None:
        return
    default = session.get(EmergencyContactDefault, member.user_id)
    if default is None:
        return
    try:
        value = fieldcrypt.open_text(default.sealed, aad=f"emergency_default:{member.user_id}")
    except fieldcrypt.SealError:
        return
    if value:
        session.add(SafetyProfile(member_id=member.id, tour_id=member.tour_id, contact_sealed=fieldcrypt.seal(value, aad=_aad(member.id, "contact"))))
        session.flush()


def put_mine(session: Session, viewer: Viewer, tour: Tour, body: dict[str, Any]) -> dict[str, Any]:
    member = _member(session, viewer, tour)
    if tour.lifecycle not in ("CONFIRMED", "ONGOING"):
        raise ApiError("TRANSITION_NOT_ALLOWED")
    profile = session.get(SafetyProfile, member.id) or SafetyProfile(member_id=member.id, tour_id=tour.id)
    if "contact" in body:
        contact = body.get("contact")
        if contact:
            name = str(contact.get("name") or "").strip()[:80]
            relationship = str(contact.get("relationship") or "").strip()[:40]
            if len(name) < 2 or len(relationship) < 2:
                raise _bad("contact")
            from app.verification.service import normalise_any_phone

            phone = normalise_any_phone(str(contact.get("phone") or ""))
            profile.contact_sealed = fieldcrypt.seal(json.dumps({"name": name, "relationship": relationship, "phone": phone}, ensure_ascii=False), aad=_aad(member.id, "contact"))
        else:
            profile.contact_sealed = None
    if "medical_notes" in body:
        notes = str(body.get("medical_notes") or "").strip()[:500]
        profile.medical_sealed = fieldcrypt.seal(json.dumps(notes, ensure_ascii=False), aad=_aad(member.id, "medical")) if notes else None
    profile.updated_at = now()
    session.add(profile)
    session.flush()
    return view(session, viewer, tour)


def _contacts_for_sos(session: Session, tour: Tour) -> list[dict[str, Any]]:
    destinations = service.tour_destinations(session, tour.id)
    rows = session.scalars(select(DestinationContact).where(DestinationContact.destination_id.in_([d.id for d in destinations]), DestinationContact.is_published.is_(True)))
    contacts = [{"name_bn": "জাতীয় জরুরি সেবা", "name_en": "National emergency service", "phone": "999", "kind": "EMERGENCY"}]
    contacts += [{"name_bn": c.name_bn, "name_en": c.name_en, "phone": c.phone, "kind": c.kind.value} for c in rows]
    return contacts


def view(session: Session, viewer: Viewer, tour: Tour) -> dict[str, Any]:
    member = _member(session, viewer, tour)
    organiser = member.role in policy.ORGANISER_ROLES
    mine = session.get(SafetyProfile, member.id)
    reveal = organiser and reveal_open(session, tour)
    members: list[dict[str, Any]] = []
    rows = session.execute(select(TourMember, User).join(User, User.id == TourMember.user_id).where(TourMember.tour_id == tour.id, TourMember.state == "ACTIVE")).all()
    revealed = 0
    for other, user in rows:
        profile = session.get(SafetyProfile, other.id)
        entry: dict[str, Any] = {"member_id": str(other.id), "name": user.display_name, "role": other.role, "has_contact": bool(profile and profile.contact_sealed)}
        if reveal and other.user_id != viewer.user_id and profile is not None:
            entry["contact"] = _open(profile.contact_sealed, _aad(other.id, "contact"))
            entry["medical_notes"] = _open(profile.medical_sealed, _aad(other.id, "medical"))
            revealed += 1
        members.append(entry)
    if revealed:
        audit.record(session, actor=None, action="tour.safety_revealed", target_type="tour", target_id=tour.id, metadata={"by": str(viewer.user_id), "count": revealed})
    checkins = []
    for checkin in session.scalars(select(CheckIn).where(CheckIn.tour_id == tour.id).order_by(CheckIn.created_at.desc()).limit(10)):
        answered = set(session.scalars(select(CheckInAnswer.user_id).where(CheckInAnswer.checkin_id == checkin.id)))
        overdue = now() - checkin.created_at > CHECKIN_GRACE
        checkins.append({
            "id": str(checkin.id), "message": checkin.message, "created_at": checkin.created_at.isoformat(), "you_answered": viewer.user_id in answered,
            "answered": len(answered), "total": len(rows),
            "not_answered": [user.display_name for other, user in rows if other.user_id not in answered] if organiser and overdue else [],
        })
    return {
        "lifecycle": tour.lifecycle,
        "mine": {
            "contact": _open(mine.contact_sealed, _aad(member.id, "contact")) if mine else None,
            "medical_notes": _open(mine.medical_sealed, _aad(member.id, "medical")) if mine else None,
            "required_by": tour.start_date.isoformat(),
        },
        "members": members if organiser else [],
        "reveal_open": reveal,
        "meeting_points": [
            {"id": str(p.id), "title": p.title, "meet_at": p.meet_at.isoformat() if p.meet_at else None, "map_url": p.map_url, "notes": p.notes}
            for p in session.scalars(select(MeetingPoint).where(MeetingPoint.tour_id == tour.id).order_by(MeetingPoint.meet_at.nulls_last()))
        ],
        "checkins": checkins,
        "sos": {"contacts": _contacts_for_sos(session, tour), "active": sos_active(session, tour.id)},
        "advisories": service._advisories(session, service.tour_destinations(session, tour.id)),  # noqa: SLF001
        "can_manage": organiser,
        "purge_note": {"en": "Contacts and medical notes are deleted 30 days after the tour ends.", "bn": "ট্যুর শেষের ৩০ দিন পর যোগাযোগ ও স্বাস্থ্য তথ্য মুছে ফেলা হয়।"},
    }


def add_meeting_point(session: Session, viewer: Viewer, tour: Tour, body: dict[str, Any]) -> dict[str, Any]:
    member = _member(session, viewer, tour)
    if not policy.can(member.role, "safety.meeting_points"):
        raise ApiError("FORBIDDEN")
    title = str(body.get("title") or "").strip()[:120]
    if len(title) < 2:
        raise _bad("title", "REQUIRED")
    meet_at = None
    if body.get("meet_at"):
        try:
            meet_at = datetime.fromisoformat(str(body["meet_at"]))
        except ValueError as error:
            raise _bad("meet_at", "INVALID_FORMAT") from error
    url = str(body.get("map_url") or "").strip()[:300] or None
    if url and not url.startswith("https://"):
        raise _bad("map_url", "HTTPS_ONLY")
    session.add(MeetingPoint(tour_id=tour.id, title=title, meet_at=meet_at, map_url=url, notes=str(body.get("notes") or "")[:300] or None, created_by=viewer.user_id))
    session.flush()
    return view(session, viewer, tour)


def delete_meeting_point(session: Session, viewer: Viewer, tour: Tour, point_id: uuid.UUID) -> dict[str, Any]:
    member = _member(session, viewer, tour)
    if not policy.can(member.role, "safety.meeting_points"):
        raise ApiError("FORBIDDEN")
    point = session.get(MeetingPoint, point_id)
    if point is None or point.tour_id != tour.id:
        raise ApiError("NOT_FOUND")
    session.delete(point)
    session.flush()
    return view(session, viewer, tour)


def request_checkin(session: Session, viewer: Viewer, tour: Tour, message: str) -> dict[str, Any]:
    member = _member(session, viewer, tour)
    if not policy.can(member.role, "safety.checkin"):
        raise ApiError("FORBIDDEN")
    if tour.lifecycle not in ("CONFIRMED", "ONGOING"):
        raise ApiError("TRANSITION_NOT_ALLOWED")
    text = (message or "").strip()[:200] or "Everyone OK?"
    checkin = CheckIn(tour_id=tour.id, requested_by=viewer.user_id, message=text)
    session.add(checkin)
    session.flush()
    session.add(CheckInAnswer(checkin_id=checkin.id, user_id=viewer.user_id))
    service._emit(session, "tour.checkin_requested", tour, {"member_ids": service.member_ids(session, tour.id)})  # noqa: SLF001
    session.flush()
    return view(session, viewer, tour)


def answer_checkin(session: Session, viewer: Viewer, tour: Tour, checkin_id: uuid.UUID) -> dict[str, Any]:
    _member(session, viewer, tour)
    checkin = session.get(CheckIn, checkin_id)
    if checkin is None or checkin.tour_id != tour.id:
        raise ApiError("NOT_FOUND")
    if session.get(CheckInAnswer, (checkin.id, viewer.user_id)) is None:
        session.add(CheckInAnswer(checkin_id=checkin.id, user_id=viewer.user_id))
        session.flush()
    return view(session, viewer, tour)


def raise_sos(session: Session, viewer: Viewer, tour: Tour, message: str | None) -> dict[str, Any]:
    _member(session, viewer, tour)
    if tour.lifecycle not in ("CONFIRMED", "ONGOING"):
        raise ApiError("TRANSITION_NOT_ALLOWED")
    event = SosEvent(tour_id=tour.id, raised_by=viewer.user_id, message=(message or "")[:300] or None)
    session.add(event)
    session.flush()
    # The safety queue gets 24 hours of access to this tour's Safety module (16.3) and a top-priority task.
    session.add(BreakglassGrant(staff_id=None, tour_id=tour.id, reason="SOS raised by a member", scope=["safety"], via="sos", expires_at=now() + SOS_WINDOW))
    report = TourReport(tour_id=tour.id, reporter_id=viewer.user_id, subject_kind="SAFETY", subject_id=event.id, reason_code="sos", details=event.message, context={"sos_id": str(event.id)})
    session.add(report)
    session.flush()
    tasks.ensure_task(session, "tour_safety", report.id, priority=10)
    user = session.get(User, viewer.user_id)
    service.system_message(session, tour, f"SOS raised by {policy.first_name(user.display_name if user else None)}. Check the Safety tab.")
    service._emit(session, "tour.sos", tour, {"member_ids": service.member_ids(session, tour.id)})  # noqa: SLF001
    events_staff(session, tour)
    audit.record(session, actor=None, action="tour.sos_raised", target_type="tour", target_id=tour.id, metadata={"by": str(viewer.user_id)})
    return view(session, viewer, tour)


def events_staff(session: Session, tour: Tour) -> None:
    from app.notify import events

    events.emit(session, "tour.sos_staff", tour.id, {"public_id": tour.public_id, "tour_title": tour.title}, aggregate_type="tour", staff_roles=("moderator", "superadmin"))


def staff_view(session: Session, tour: Tour) -> list[dict[str, Any]]:
    """Break-glass or SOS read (16.3); the caller checked the grant and audits it."""
    out = []
    for member, user in session.execute(select(TourMember, User).join(User, User.id == TourMember.user_id).where(TourMember.tour_id == tour.id, TourMember.state == "ACTIVE")).all():
        profile = session.get(SafetyProfile, member.id)
        out.append({
            "name": user.display_name, "role": member.role,
            "contact": _open(profile.contact_sealed, _aad(member.id, "contact")) if profile else None,
            "medical_notes": _open(profile.medical_sealed, _aad(member.id, "medical")) if profile else None,
        })
    return out


def purge_due(session: Session, moment: datetime) -> int:
    """30 days after the end (or the cancellation): contacts, medical notes and companions are destroyed."""
    count = 0
    rows = session.scalars(
        select(Tour).where(Tour.safety_purged_at.is_(None), Tour.lifecycle.in_(("COMPLETED", "CANCELLED", "ARCHIVED"))).limit(100).with_for_update(skip_locked=True)
    )
    for tour in rows:
        ended = policy.end_instant(tour.end_date) if tour.lifecycle != "CANCELLED" else (tour.cancelled_at or moment)
        if moment - ended < PURGE_AFTER:
            continue
        for profile in session.scalars(select(SafetyProfile).where(SafetyProfile.tour_id == tour.id)):
            session.delete(profile)
        for member in session.scalars(select(TourMember).where(TourMember.tour_id == tour.id, TourMember.companions_sealed.is_not(None))):
            member.companions_sealed = None
        from app.tours.models import TourJoinRequest

        for request in session.scalars(select(TourJoinRequest).where(TourJoinRequest.tour_id == tour.id, TourJoinRequest.companions_sealed.is_not(None))):
            request.companions_sealed = None
        tour.safety_purged_at = moment
        audit.record(session, actor=None, action="tour.safety_purged", target_type="tour", target_id=tour.id)
        count += 1
    return count


def missing_contact_reminders(session: Session, moment: datetime) -> int:
    """3 days before the start, members without an emergency contact are reminded (15)."""
    sent = 0
    today = policy.dhaka_today(moment)
    for tour in session.scalars(select(Tour).where(Tour.lifecycle == "CONFIRMED", Tour.start_date == today + timedelta(days=3))):
        missing = []
        for member in session.scalars(select(TourMember).where(TourMember.tour_id == tour.id, TourMember.state == "ACTIVE")):
            profile = session.get(SafetyProfile, member.id)
            if profile is None or profile.contact_sealed is None:
                missing.append(str(member.user_id))
        if missing and service._emit(session, "tour.contact_missing", tour, {"member_ids": missing}, dedupe_key=f"tour.contact_missing:{tour.id}:{tour.start_date}"):  # noqa: SLF001
            sent += 1
    return sent
