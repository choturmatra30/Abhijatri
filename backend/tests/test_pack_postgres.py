"""R14 offline packs against real PostgreSQL: contract, versioning, freshness, privacy and concurrency."""

import hashlib
import json
import threading
import time
import uuid
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db import get_session
from app.destination_services import today_in_display_tz
from app.limits import limiter
from app.main import create_app
from app.models import (
    AdvisorySeverity,
    ComfortTier,
    ContactKind,
    Destination,
    DestinationAdvisory,
    DestinationContact,
    DestinationGuideItem,
    DestinationPackVersion,
    DestinationRatingStats,
    DestinationStatus,
    GuideCategory,
    ModerationDecision,
    RatingEligibility,
    Review,
    ReviewLanguage,
    ReviewMedia,
    ReviewRevision,
    ReviewStatus,
    RevisionStatus,
    SourceType,
    TravellerType,
    User,
)
from app.offline import packs
from app.offline.packs import content_digest, ensure_current_pack
from app.schemas import PackDocument, PackManifest
from app.services import moderate_review, withdraw_review

pytestmark = pytest.mark.integration

TODAY = today_in_display_tz()
EMAIL = "private.member@example.test"


# ---- builders ----


def _provenance(verified_on: date | None = None, effective_on: date | None = None) -> dict[str, Any]:
    return {
        "source_type": SourceType.TEAM_RESEARCH,
        "source_ref": "test fixture",
        "publisher": "Abhijatri test team",
        "effective_on": effective_on or TODAY - timedelta(days=10),
        "verified_on": verified_on or TODAY,
        "licence": "CC-BY-4.0",
        "researcher": "Secret Researcher",
        "reviewer": "Secret Reviewer",
    }


def _destination(session: Session, status: DestinationStatus = DestinationStatus.PUBLISHED) -> Destination:
    destination = Destination(
        status=status,
        name_bn="সাজেক ভ্যালি",
        name_en="Sajek Valley",
        summary_bn="মেঘের উপত্যকা",
        summary_en="Valley of clouds",
        latitude=23.381,
        longitude=92.293,
    )
    session.add(destination)
    session.flush()
    session.add(DestinationRatingStats(destination_id=destination.id))
    session.commit()
    return destination


def _guide(session: Session, destination: Destination, title: str, *, published: bool = True) -> None:
    session.add(
        DestinationGuideItem(
            destination_id=destination.id, category=GuideCategory.TRANSPORT, title_bn=f"{title} (bn)",
            title_en=title, body_bn="বাসে যান", body_en="Take the bus", sort_order=1, is_published=published,
            **_provenance(),
        )
    )  # fmt: skip
    session.commit()


def _advisory(
    session: Session,
    destination: Destination,
    title: str,
    *,
    valid_until: date,
    effective_on: date | None = None,
    verified_on: date | None = None,
    published: bool = True,
) -> DestinationAdvisory:
    advisory = DestinationAdvisory(
        destination_id=destination.id, severity=AdvisorySeverity.WARNING, title_bn=f"{title} (bn)",
        title_en=title, text_bn="সতর্কতা", text_en="Take care", valid_until=valid_until,
        is_published=published, **_provenance(verified_on, effective_on),
    )  # fmt: skip
    session.add(advisory)
    session.commit()
    return advisory


def _contact(session: Session, destination: Destination, name: str, *, published: bool = True) -> None:
    session.add(
        DestinationContact(
            destination_id=destination.id, kind=ContactKind.POLICE, name_bn=f"{name} (bn)", name_en=name,
            phone="999", is_published=published, **_provenance(),
        )
    )  # fmt: skip
    session.commit()


def _user(session: Session, name: str, email: str | None = None) -> User:
    user = User(email=email or f"{uuid.uuid4()}@example.test", display_name=name)
    session.add(user)
    session.commit()
    return user


def _review(session: Session, destination: Destination, author: User | None, title: str) -> Review:
    review = Review(
        destination_id=destination.id,
        author_user_id=author.id if author else None,
        guest_display_name=None if author else "Rahim Private",
        guest_scope_hash=None if author else b"\x01" * 32,
        guest_scope_key_id=None if author else "k1",
        client_draft_id=uuid.uuid4(),
        status=ReviewStatus.PENDING,
        rating_eligibility=RatingEligibility.NOT_EVALUATED,
        overall_rating=4,
        visit_month=date(2026, 9, 1),
    )
    session.add(review)
    session.flush()
    revision = ReviewRevision(
        review_id=review.id, sequence=1, status=RevisionStatus.PENDING, language=ReviewLanguage.EN,
        traveller_type=TravellerType.SOLO, comfort_tier=ComfortTier.STANDARD, title=title,
        body="The road was steep but the view at sunrise was worth the climb.", overall_rating=4,
        consent_version="v1",
    )  # fmt: skip
    session.add(revision)
    session.flush()
    review.current_revision_id = revision.id
    session.commit()
    return review


def _moderate(session: Session, review: Review, moderator: User, decision: ModerationDecision) -> Review:
    session.refresh(review)
    moderate_review(
        session, review_id=review.id, actor_user_id=moderator.id, expected_version=review.version,
        decision=decision, reason_code="APPROVED" if decision == ModerationDecision.PUBLISH else "PRIVACY", note=None,
    )  # fmt: skip
    session.commit()
    session.refresh(review)
    return review


def _rows(session: Session, destination: Destination) -> list[DestinationPackVersion]:
    session.expire_all()
    return list(
        session.scalars(select(DestinationPackVersion).where(DestinationPackVersion.destination_id == destination.id))
    )


# ---- fixtures ----


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    limiter.reset()


@pytest.fixture()
def client(postgres_session: Session) -> Generator[TestClient, None, None]:
    application = create_app()

    def override() -> Generator[Session, None, None]:
        yield postgres_session

    application.dependency_overrides[get_session] = override
    yield TestClient(application)


@pytest.fixture()
def moderator(postgres_session: Session) -> User:
    return _user(postgres_session, "Moderator")


@pytest.fixture()
def destination(postgres_session: Session, moderator: User) -> Destination:
    """A complete published destination: guide, contact, advisory, a guest and a member review."""
    session = postgres_session
    destination = _destination(session)
    _guide(session, destination, "Getting there")
    _guide(session, destination, "Unpublished guide draft", published=False)
    _contact(session, destination, "Sajek Police")
    _contact(session, destination, "Unpublished contact draft", published=False)
    _advisory(session, destination, "Road works", valid_until=TODAY + timedelta(days=30))
    member = _user(session, "Nadia", EMAIL)
    _moderate(session, _review(session, destination, None, "Guest sunrise"), moderator, ModerationDecision.PUBLISH)
    member_review = _moderate(session, _review(session, destination, member, "Member clouds"), moderator, ModerationDecision.PUBLISH)
    _review(session, destination, None, "Pending review text")  # never published
    session.add(
        ReviewMedia(
            review_id=member_review.id, uploader_id=member.id, kind="image", state="approved", position=0,
            content_type="image/webp", quarantine_key=f"quarantine/{uuid.uuid4()}", processed_key=f"processed/{uuid.uuid4()}",
            alt_text="Clouds below the ridge", caption="Sunrise", ownership_declared=True,
        )
    )  # fmt: skip
    session.commit()
    return destination


def _manifest(client: TestClient, destination: Destination) -> dict[str, Any]:
    response = client.get(f"/api/v1/destinations/{destination.id}/pack/manifest")
    assert response.status_code == 200, response.text
    return dict(response.json())


def _pack(client: TestClient, manifest: dict[str, Any]) -> bytes:
    response = client.get(manifest["pack_url"])
    assert response.status_code == 200, response.text
    return response.content


# ---- contract ----


def test_manifest_describes_exactly_the_served_bytes(client: TestClient, destination: Destination) -> None:
    response = client.get(f"/api/v1/destinations/{destination.id}/pack/manifest")
    assert response.status_code == 200
    assert response.headers["cache-control"] == f"public, max-age={get_settings().public_cache_max_age_seconds}"
    assert response.headers["etag"].startswith('W/"')
    manifest = PackManifest.model_validate(response.json())
    assert manifest.schema_version == 1 and manifest.pack_version == 1
    assert manifest.languages == ["bn", "en"]
    assert manifest.max_age_seconds == 7 * 86400
    assert manifest.expires_at - manifest.generated_at == timedelta(days=7)
    assert manifest.review_snapshot.model_dump() == {"count": 2, "limit": 20}
    assert manifest.advisories_verified_on == TODAY
    assert manifest.pack_url == f"/api/v1/destinations/{destination.id}/pack?version=1"

    pack = client.get(manifest.pack_url)
    assert pack.status_code == 200
    assert pack.headers["content-type"].startswith("application/json")
    assert pack.headers["cache-control"].startswith("public, max-age=")
    assert hashlib.sha256(pack.content).hexdigest() == manifest.sha256
    assert pack.headers["etag"] == f'"{manifest.sha256}"'
    assert pack.headers["content-digest"] == content_digest(manifest.sha256)
    assert len(pack.content) == manifest.size_bytes

    document = PackDocument.model_validate_json(pack.content)
    assert document.content_version == manifest.content_version
    assert document.pack_version == manifest.pack_version
    assert document.generated_at == manifest.generated_at and document.expires_at == manifest.expires_at
    assert document.generated_on == today_in_display_tz(manifest.generated_at)
    assert [item.title_en for item in document.guide_items] == ["Getting there"]
    assert [item.name_en for item in document.contacts] == ["Sajek Police"]
    assert [item.title_en for item in document.advisories] == ["Road works"]
    assert [state.state for state in document.advisory_states] == ["CURRENT"]
    assert [review.title for review in document.reviews.items] == ["Member clouds", "Guest sunrise"]
    assert document.destination.name_bn == "সাজেক ভ্যালি"
    assert "সাজেক ভ্যালি".encode() in pack.content  # UTF-8, not \\u escapes


def test_pack_without_version_returns_the_current_pack(client: TestClient, destination: Destination) -> None:
    manifest = _manifest(client, destination)
    response = client.get(f"/api/v1/destinations/{destination.id}/pack")
    assert hashlib.sha256(response.content).hexdigest() == manifest["sha256"]


# ---- versioning ----


def test_repeated_reads_reuse_one_build(client: TestClient, postgres_session: Session, destination: Destination) -> None:
    first = _manifest(client, destination)
    second = _manifest(client, destination)
    assert first == second
    assert len(_rows(postgres_session, destination)) == 1


def test_content_change_makes_a_new_version_and_supersedes_the_old(
    client: TestClient, postgres_session: Session, destination: Destination
) -> None:
    first = _manifest(client, destination)
    _advisory(postgres_session, destination, "Landslide", valid_until=TODAY + timedelta(days=3))
    second = _manifest(client, destination)
    assert second["pack_version"] == 2
    assert second["content_version"] != first["content_version"]
    assert second["sha256"] != first["sha256"]
    assert [row.pack_version for row in _rows(postgres_session, destination)] == [2]

    stale = client.get(first["pack_url"])
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "PACK_VERSION_SUPERSEDED"
    assert stale.headers["cache-control"] == "no-store"
    assert "Landslide" in _pack(client, second).decode()


@pytest.mark.parametrize("removal", ["hide", "withdraw"])
def test_a_removed_review_leaves_the_next_pack(
    client: TestClient, postgres_session: Session, destination: Destination, moderator: User, removal: str
) -> None:
    first = _manifest(client, destination)
    assert "Guest sunrise" in _pack(client, first).decode()
    review = postgres_session.scalar(
        select(Review).join(ReviewRevision, ReviewRevision.id == Review.current_revision_id).where(ReviewRevision.title == "Guest sunrise")
    )
    assert review is not None
    if removal == "hide":
        _moderate(postgres_session, review, moderator, ModerationDecision.HIDE)
    else:
        withdraw_review(postgres_session, review.id, review.version)
        postgres_session.commit()
    second = _manifest(client, destination)
    assert second["pack_version"] == first["pack_version"] + 1
    assert second["review_snapshot"]["count"] == 1
    body = _pack(client, second).decode()
    assert "Guest sunrise" not in body
    # No older build that still holds the removed review is kept on the server.
    assert all(b"Guest sunrise" not in row.body for row in _rows(postgres_session, destination))


def test_an_old_build_is_refreshed_with_the_same_content_version(
    postgres_session: Session, destination: Destination
) -> None:
    now = datetime.now(UTC)
    first = ensure_current_pack(postgres_session, destination.id, now=now).row
    same = ensure_current_pack(postgres_session, destination.id, now=now + timedelta(hours=23)).row
    later = ensure_current_pack(postgres_session, destination.id, now=now + timedelta(hours=25)).row
    assert same.pack_version == first.pack_version == 1
    assert later.pack_version == 2
    assert later.content_version == first.content_version
    assert later.expires_at > first.expires_at
    assert [row.pack_version for row in _rows(postgres_session, destination)] == [2]


def test_snapshot_limit_keeps_the_newest_reviews(
    client: TestClient, destination: Destination, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PACK_REVIEW_SNAPSHOT_LIMIT", "1")
    get_settings.cache_clear()
    try:
        manifest = _manifest(client, destination)
        document = PackDocument.model_validate_json(_pack(client, manifest))
    finally:
        monkeypatch.delenv("PACK_REVIEW_SNAPSHOT_LIMIT")
        get_settings.cache_clear()
    assert manifest["review_snapshot"] == {"count": 1, "limit": 1}
    assert [review.title for review in document.reviews.items] == ["Member clouds"]


# ---- conditional requests ----


def test_matching_etags_return_304_on_every_route(client: TestClient, destination: Destination) -> None:
    paths = [
        f"/api/v1/destinations/{destination.id}/pack/manifest",
        f"/api/v1/destinations/{destination.id}/pack",
        f"/api/v1/packs/freshness?destination_id={destination.id}",
    ]
    for path in paths:
        first = client.get(path)
        assert first.status_code == 200
        again = client.get(path, headers={"If-None-Match": first.headers["etag"]})
        assert again.status_code == 304, path
        assert again.content == b""
        assert again.headers["etag"] == first.headers["etag"]
        assert again.headers["cache-control"] == first.headers["cache-control"]
        assert client.get(path, headers={"If-None-Match": 'W/"other"'}).status_code == 200


# ---- concurrency ----


def test_concurrent_first_requests_build_exactly_once(
    postgres_session: Session, destination: Destination, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Slow the build down so every thread reads "no pack yet" before the first one commits: without
    # the advisory lock they would all insert version 1 and all but one would fail.
    real_build = packs.build_document

    def slow_build(*args: Any, **kwargs: Any) -> PackDocument:
        time.sleep(0.3)
        return real_build(*args, **kwargs)

    monkeypatch.setattr(packs, "build_document", slow_build)
    factory = sessionmaker(bind=postgres_session.get_bind(), expire_on_commit=False)
    barrier = threading.Barrier(8)
    versions: list[int] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            with factory() as session:
                barrier.wait()
                versions.append(ensure_current_pack(session, destination.id).row.pack_version)
        except BaseException as error:  # noqa: BLE001 - surfaced by the assertion below
            errors.append(error)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert errors == []
    assert versions == [1] * 8
    assert len(_rows(postgres_session, destination)) == 1


# ---- lifecycle ----


def test_a_draft_is_indistinguishable_from_an_unknown_id(client: TestClient, postgres_session: Session) -> None:
    draft = _destination(postgres_session, DestinationStatus.DRAFT)
    for path in ("pack/manifest", "pack"):
        hidden = client.get(f"/api/v1/destinations/{draft.id}/{path}")
        unknown = client.get(f"/api/v1/destinations/{uuid.uuid4()}/{path}")
        assert hidden.status_code == unknown.status_code == 404
        strip = lambda body: {**body["error"], "request_id": None}  # noqa: E731
        assert strip(hidden.json()) == strip(unknown.json())
    assert postgres_session.scalar(select(func.count()).select_from(DestinationPackVersion)) == 0


def test_an_archived_destination_is_withdrawn(
    client: TestClient, postgres_session: Session, destination: Destination
) -> None:
    _manifest(client, destination)
    destination.status = DestinationStatus.ARCHIVED
    postgres_session.commit()
    for path in ("pack/manifest", "pack"):
        response = client.get(f"/api/v1/destinations/{destination.id}/{path}", headers={"Accept-Language": "en"})
        assert response.status_code == 410
        assert response.json()["error"]["code"] == "PACK_WITHDRAWN"
        assert response.json()["error"]["message"] == "This destination is no longer published. Delete the saved pack."
        assert response.headers["cache-control"] == "no-store"


def test_freshness_reports_each_pack_in_request_order(
    client: TestClient, postgres_session: Session, destination: Destination
) -> None:
    archived = _destination(postgres_session, DestinationStatus.ARCHIVED)
    draft = _destination(postgres_session, DestinationStatus.DRAFT)
    unknown = uuid.uuid4()
    ids = [archived.id, destination.id, draft.id, unknown]
    response = client.get("/api/v1/packs/freshness", params=[("destination_id", str(value)) for value in ids])
    assert response.status_code == 200
    items = response.json()["items"]
    assert [(item["destination_id"], item["status"]) for item in items] == [
        (str(archived.id), "WITHDRAWN"),
        (str(destination.id), "AVAILABLE"),
        (str(draft.id), "NOT_FOUND"),
        (str(unknown), "NOT_FOUND"),
    ]
    manifest = _manifest(client, destination)
    available = items[1]
    for field in ("pack_version", "content_version", "sha256", "size_bytes", "generated_at", "expires_at", "pack_url"):
        assert available[field] == manifest[field], field


# ---- freshness of safety information ----


def test_advisory_window_and_states(client: TestClient, postgres_session: Session) -> None:
    session = postgres_session
    destination = _destination(session)
    _advisory(session, destination, "Expired yesterday", valid_until=TODAY - timedelta(days=1), effective_on=TODAY - timedelta(days=9))
    _advisory(session, destination, "Starts in three days", valid_until=TODAY + timedelta(days=9), effective_on=TODAY + timedelta(days=3))
    _advisory(session, destination, "Starts on the last day", valid_until=TODAY + timedelta(days=9), effective_on=TODAY + timedelta(days=7))
    _advisory(session, destination, "Starts after expiry", valid_until=TODAY + timedelta(days=20), effective_on=TODAY + timedelta(days=8))
    _advisory(session, destination, "Old verification", valid_until=TODAY + timedelta(days=5), verified_on=TODAY - timedelta(days=40))
    _advisory(session, destination, "Ends today", valid_until=TODAY, effective_on=TODAY - timedelta(days=2))
    _advisory(session, destination, "Unpublished", valid_until=TODAY + timedelta(days=5), published=False)
    manifest = _manifest(client, destination)
    document = PackDocument.model_validate_json(_pack(client, manifest))
    states = {advisory.title_en: state.state for advisory, state in zip(document.advisories, document.advisory_states, strict=True)}
    assert states == {
        "Starts in three days": "NOT_YET_EFFECTIVE",
        "Starts on the last day": "NOT_YET_EFFECTIVE",
        "Old verification": "STALE",
        "Ends today": "CURRENT",
    }
    assert [state.id for state in document.advisory_states] == [advisory.id for advisory in document.advisories]
    assert manifest["advisories_verified_on"] == (TODAY - timedelta(days=40)).isoformat()
    for advisory in document.advisories:  # raw dates travel so the device can recompute offline
        assert advisory.effective_on and advisory.valid_until and advisory.provenance.verified_on


def test_a_destination_without_advisories_has_no_verification_date(client: TestClient, postgres_session: Session) -> None:
    manifest = _manifest(client, _destination(postgres_session))
    assert manifest["advisories_verified_on"] is None
    assert manifest["review_snapshot"] == {"count": 0, "limit": 20}


# ---- privacy and cache safety ----


def test_the_pack_holds_only_public_content(client: TestClient, destination: Destination) -> None:
    manifest = _manifest(client, destination)
    raw = _pack(client, manifest)
    text = raw.decode("utf-8")
    for secret in (
        "Secret Researcher", "Secret Reviewer", "researcher", "reviewer", EMAIL, "Rahim Private",
        "guest_display_name", "author_user_id", "guest_scope", "receipt", "quarantine", "processed",
        "url", "signed", "Pending review text", "Unpublished guide draft", "Unpublished contact draft",
        "visit_month", "rating_eligibility", "client_draft_id",
    ):  # fmt: skip
        assert secret not in text, secret
    document = json.loads(raw)
    member = document["reviews"]["items"][0]
    assert member["author_type"] == "MEMBER" and member["author_display_name"] == "Nadia"
    assert member["media"] == [
        {"id": member["media"][0]["id"], "kind": "image", "alt_text": "Clouds below the ridge", "caption": "Sunrise"}
    ]
    guest = document["reviews"]["items"][1]
    assert guest["author_type"] == "GUEST" and guest["author_display_name"] is None


def test_responses_do_not_reflect_request_headers(client: TestClient, destination: Destination) -> None:
    manifest_path = f"/api/v1/destinations/{destination.id}/pack/manifest"
    plain_manifest = client.get(manifest_path)
    plain_pack = client.get(f"/api/v1/destinations/{destination.id}/pack")
    noisy = {
        "Accept-Language": "en",
        "Authorization": "Bearer not-a-token",
        "Cookie": "__Host-abhijatri_session=forged; __Host-abhijatri_refresh=forged",
        "X-Test-Staff-Id": str(uuid.uuid4()),
    }
    noisy_manifest = client.get(manifest_path + "?utm=1&include_expired=true", headers=noisy)
    noisy_pack = client.get(f"/api/v1/destinations/{destination.id}/pack?debug=1", headers=noisy)
    assert noisy_manifest.content == plain_manifest.content
    assert noisy_manifest.headers["etag"] == plain_manifest.headers["etag"]
    assert noisy_pack.content == plain_pack.content
    assert noisy_pack.headers["etag"] == plain_pack.headers["etag"]
    for response in (plain_manifest, plain_pack, noisy_manifest, noisy_pack):
        assert "set-cookie" not in response.headers
        assert "cookie" not in response.headers.get("vary", "").lower()


def test_cors_allows_the_public_app_without_credentials(client: TestClient, destination: Destination) -> None:
    allowed = get_settings().cors_origins[0]
    response = client.get(f"/api/v1/destinations/{destination.id}/pack/manifest", headers={"Origin": allowed})
    assert response.headers["access-control-allow-origin"] == allowed
    foreign = client.get(f"/api/v1/destinations/{destination.id}/pack/manifest", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in foreign.headers


# ---- abuse ----


def test_pack_downloads_are_rate_limited(
    client: TestClient, destination: Destination, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_PACK_DOWNLOAD", "2/minute")
    get_settings.cache_clear()
    try:
        codes = [client.get(f"/api/v1/destinations/{destination.id}/pack").status_code for _ in range(3)]
        limited = client.get(f"/api/v1/destinations/{destination.id}/pack")
    finally:
        monkeypatch.delenv("RATE_LIMIT_PACK_DOWNLOAD")
        get_settings.cache_clear()
    assert codes == [200, 200, 429]
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert int(limited.headers["retry-after"]) >= 1
    assert limited.headers["cache-control"] == "no-store"


# ---- connection hygiene ----


def test_every_path_ends_its_transaction(postgres_session: Session, destination: Destination) -> None:
    """A finished pack read must not keep its pooled connection idle in a transaction: under load
    that exhausted the pool before the request's dependency teardown ran (load check, 6 Nov 2026)."""
    ensure_current_pack(postgres_session, destination.id)  # build
    assert not postgres_session.in_transaction()
    ensure_current_pack(postgres_session, destination.id)  # reuse
    assert not postgres_session.in_transaction()
    with pytest.raises(packs.PackNotFound):
        ensure_current_pack(postgres_session, uuid.uuid4())
    assert not postgres_session.in_transaction()
