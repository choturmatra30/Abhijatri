"""Destination, advisory and contact services against real PostgreSQL."""

import uuid
from collections.abc import Generator
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.destination_services import today_in_display_tz
from app.main import create_app
from app.models import (
    AdvisorySeverity,
    ContactKind,
    Destination,
    DestinationAdvisory,
    DestinationContact,
    DestinationGuideItem,
    DestinationRatingStats,
    DestinationStatus,
    GuideCategory,
    SourceType,
)

pytestmark = pytest.mark.integration

TODAY = today_in_display_tz()


def _provenance(verified_on: date | None = None, effective_on: date | None = None) -> dict[str, Any]:
    return {
        "source_type": SourceType.TEAM_RESEARCH,
        "source_ref": "test fixture",
        "publisher": "Abhijatri test team",
        "effective_on": effective_on or TODAY - timedelta(days=10),
        "verified_on": verified_on or TODAY,
        "licence": "CC-BY-4.0",
        "researcher": "Test Researcher",
    }


def _destination(
    session: Session, name: str, status: DestinationStatus = DestinationStatus.PUBLISHED
) -> Destination:
    destination = Destination(status=status, name_bn=f"{name} (bn)", name_en=name)
    session.add(destination)
    session.flush()
    session.add(DestinationRatingStats(destination_id=destination.id))
    return destination


def _advisory(
    session: Session,
    destination: Destination,
    title: str,
    *,
    valid_until: date,
    effective_on: date | None = None,
    verified_on: date | None = None,
    published: bool = True,
    severity: AdvisorySeverity = AdvisorySeverity.CAUTION,
) -> DestinationAdvisory:
    advisory = DestinationAdvisory(
        destination_id=destination.id,
        severity=severity,
        title_bn=f"{title} (bn)",
        title_en=title,
        text_bn="সতর্কতা",
        text_en="Take care",
        valid_until=valid_until,
        is_published=published,
        **_provenance(verified_on, effective_on),
    )
    session.add(advisory)
    session.flush()
    return advisory


def _contact(
    session: Session,
    destination: Destination,
    name: str,
    kind: ContactKind,
    *,
    phone: str = "999",
    published: bool = True,
) -> DestinationContact:
    contact = DestinationContact(
        destination_id=destination.id,
        kind=kind,
        name_bn=f"{name} (bn)",
        name_en=name,
        phone=phone,
        is_published=published,
        **_provenance(),
    )
    session.add(contact)
    session.flush()
    return contact


@pytest.fixture()
def client(postgres_session: Session) -> Generator[TestClient, None, None]:
    application = create_app()

    def override() -> Generator[Session, None, None]:
        yield postgres_session

    application.dependency_overrides[get_session] = override
    yield TestClient(application)


def test_list_returns_only_published_destinations_in_stable_pages(
    postgres_session: Session, client: TestClient
) -> None:
    for name in ("Bandarban", "Cox's Bazar", "Sajek", "Sylhet"):
        _destination(postgres_session, name)
    _destination(postgres_session, "Draft Place", DestinationStatus.DRAFT)
    _destination(postgres_session, "Old Place", DestinationStatus.ARCHIVED)
    postgres_session.commit()

    first = client.get("/api/v1/destinations", params={"limit": 3}).json()
    assert [item["name_en"] for item in first["items"]] == ["Bandarban", "Cox's Bazar", "Sajek"]
    assert first["next_cursor"] is not None
    second = client.get(
        "/api/v1/destinations", params={"limit": 3, "after": first["next_cursor"]}
    ).json()
    assert [item["name_en"] for item in second["items"]] == ["Sylhet"]
    assert second["next_cursor"] is None


def test_list_item_is_bilingual_and_summarises_ratings_and_active_advisories(
    postgres_session: Session, client: TestClient
) -> None:
    destination = _destination(postgres_session, "Sajek")
    destination.region_bn, destination.region_en = "রাঙ্গামাটি", "Rangamati"
    destination.latitude, destination.longitude = Decimal("23.381400"), Decimal("92.293500")
    stats = postgres_session.get(DestinationRatingStats, destination.id)
    assert stats is not None
    stats.guest_rating_sum, stats.guest_rating_count = 9, 2
    _advisory(postgres_session, destination, "Active", valid_until=TODAY + timedelta(days=5))
    _advisory(postgres_session, destination, "Expired", valid_until=TODAY - timedelta(days=1))
    _advisory(postgres_session, destination, "Draft", valid_until=TODAY + timedelta(days=5), published=False)
    postgres_session.commit()

    (item,) = client.get("/api/v1/destinations").json()["items"]
    assert item["name_bn"] == "Sajek (bn)"
    assert item["region_bn"] == "রাঙ্গামাটি"
    assert item["latitude"] == pytest.approx(23.3814)
    assert item["guest_feedback"] == {"average": 4.5, "count": 2, "category_averages": []}
    assert item["community_rating"] == {"average": None, "count": 0, "category_averages": []}
    assert item["active_advisory_count"] == 1


def test_non_published_destination_is_404_everywhere(postgres_session: Session, client: TestClient) -> None:
    draft = _destination(postgres_session, "Hidden", DestinationStatus.DRAFT)
    postgres_session.commit()
    assert client.get(f"/api/v1/destinations/{draft.id}").status_code == 404
    assert client.get(f"/api/v1/destinations/{uuid.uuid4()}").status_code == 404


def test_profile_contains_guide_items_advisories_contacts_and_provenance(
    postgres_session: Session, client: TestClient
) -> None:
    destination = _destination(postgres_session, "Cox's Bazar")
    destination.summary_bn, destination.summary_en = "সমুদ্র সৈকত", "Sea beach"
    destination.seasonality_en = "November to March"
    destination.restrictions_en = "No swimming during red flag"
    destination.content_licence = "CC-BY-4.0"
    for sort_order, (category, title) in enumerate(
        [
            (GuideCategory.TRANSPORT, "Bus"),
            (GuideCategory.ATTRACTION, "Laboni Beach"),
            (GuideCategory.ATTRACTION, "Marine Drive"),
        ]
    ):
        postgres_session.add(
            DestinationGuideItem(
                destination_id=destination.id,
                category=category,
                title_bn=f"{title} (bn)",
                title_en=title,
                body_bn="বিবরণ",
                body_en="Details",
                sort_order=sort_order,
                is_published=True,
                **_provenance(),
            )
        )
    postgres_session.add(
        DestinationGuideItem(
            destination_id=destination.id,
            category=GuideCategory.FOOD,
            title_bn="x",
            title_en="Unpublished food",
            body_bn="x",
            body_en="x",
            is_published=False,
            **_provenance(),
        )
    )
    _advisory(postgres_session, destination, "Rough sea", valid_until=TODAY + timedelta(days=3))
    _contact(postgres_session, destination, "Tourist Police", ContactKind.TOURIST_POLICE)
    postgres_session.commit()

    body = client.get(f"/api/v1/destinations/{destination.id}").json()
    assert body["name_bn"] == "Cox's Bazar (bn)"
    assert body["summary_bn"] == "সমুদ্র সৈকত"
    assert body["seasonality_en"] == "November to March"
    assert body["restrictions_en"] == "No swimming during red flag"
    assert body["content_licence"] == "CC-BY-4.0"
    assert body["as_of"] == TODAY.isoformat()
    assert body["stale_after_days"] == 30
    # Ordered by category (enum order) then sort_order; unpublished items are absent.
    assert [(g["category"], g["title_en"]) for g in body["guide_items"]] == [
        ("ATTRACTION", "Laboni Beach"),
        ("ATTRACTION", "Marine Drive"),
        ("TRANSPORT", "Bus"),
    ]
    provenance = body["guide_items"][0]["provenance"]
    assert provenance["licence"] == "CC-BY-4.0"
    assert provenance["publisher"] == "Abhijatri test team"
    assert "researcher" not in provenance and "reviewer" not in provenance
    assert [a["title_en"] for a in body["advisories"]] == ["Rough sea"]
    assert body["advisories"][0]["state"] == "CURRENT"
    assert [c["kind"] for c in body["contacts"]] == ["TOURIST_POLICE"]


def test_expired_advisories_are_hidden_unless_requested_and_never_current(
    postgres_session: Session, client: TestClient
) -> None:
    destination = _destination(postgres_session, "Sylhet")
    _advisory(postgres_session, destination, "Expired", valid_until=TODAY - timedelta(days=1))
    _advisory(postgres_session, destination, "Ends today", valid_until=TODAY)
    _advisory(
        postgres_session,
        destination,
        "Stale",
        valid_until=TODAY + timedelta(days=30),
        verified_on=TODAY - timedelta(days=31),
    )
    _advisory(
        postgres_session,
        destination,
        "Future",
        valid_until=TODAY + timedelta(days=60),
        effective_on=TODAY + timedelta(days=1),
    )
    _advisory(postgres_session, destination, "Unpublished", valid_until=TODAY + timedelta(days=5), published=False)
    postgres_session.commit()

    url = f"/api/v1/destinations/{destination.id}"
    default = client.get(url).json()
    assert {a["title_en"]: a["state"] for a in default["advisories"]} == {
        "Ends today": "CURRENT",
        "Stale": "STALE",
    }
    assert default["as_of"] == TODAY.isoformat()

    everything = client.get(url, params={"include_expired": "true"}).json()
    assert {a["title_en"]: a["state"] for a in everything["advisories"]} == {
        "Expired": "EXPIRED",
        "Ends today": "CURRENT",
        "Stale": "STALE",
    }


def test_advisories_are_ordered_most_severe_first(postgres_session: Session, client: TestClient) -> None:
    destination = _destination(postgres_session, "Sundarbans")
    for severity in (AdvisorySeverity.INFO, AdvisorySeverity.CRITICAL, AdvisorySeverity.WARNING):
        _advisory(
            postgres_session,
            destination,
            severity.value,
            valid_until=TODAY + timedelta(days=5),
            severity=severity,
        )
    postgres_session.commit()
    items = client.get(f"/api/v1/destinations/{destination.id}").json()["advisories"]
    assert [item["severity"] for item in items] == ["CRITICAL", "WARNING", "INFO"]


def test_profile_contacts_are_destination_scoped_published_and_ordered(
    postgres_session: Session, client: TestClient
) -> None:
    destination = _destination(postgres_session, "Bandarban")
    other = _destination(postgres_session, "Elsewhere")
    _contact(postgres_session, destination, "Police", ContactKind.POLICE)
    _contact(postgres_session, destination, "Hospital", ContactKind.HOSPITAL, phone="+880 361-62000")
    _contact(postgres_session, destination, "Hidden", ContactKind.POLICE, published=False)
    _contact(postgres_session, other, "Other police", ContactKind.POLICE)
    postgres_session.commit()

    contacts = client.get(f"/api/v1/destinations/{destination.id}").json()["contacts"]
    assert [c["name_en"] for c in contacts] == ["Police", "Hospital"]  # enum order: POLICE before HOSPITAL
    assert contacts[0]["provenance"]["licence"] == "CC-BY-4.0"
    assert contacts[1]["phone"] == "+880 361-62000"


def test_public_routes_are_cacheable_and_support_conditional_requests(
    postgres_session: Session, client: TestClient
) -> None:
    destination = _destination(postgres_session, "Sajek")
    postgres_session.commit()

    for url in ("/api/v1/destinations", f"/api/v1/destinations/{destination.id}"):
        first = client.get(url)
        assert first.status_code == 200
        assert first.headers["cache-control"] == "public, max-age=60"
        etag = first.headers["etag"]
        again = client.get(url, headers={"If-None-Match": etag})
        assert again.status_code == 304
        assert again.content == b""
        assert again.headers["etag"] == etag
        assert client.get(url, headers={"If-None-Match": 'W/"stale"'}).status_code == 200


def test_changed_content_changes_the_etag(postgres_session: Session, client: TestClient) -> None:
    destination = _destination(postgres_session, "Sajek")
    postgres_session.commit()
    url = f"/api/v1/destinations/{destination.id}"
    before = client.get(url).headers["etag"]
    _advisory(postgres_session, destination, "New", valid_until=TODAY + timedelta(days=2))
    postgres_session.commit()
    assert client.get(url).headers["etag"] != before


def test_review_feed_has_a_short_public_ttl(postgres_session: Session, client: TestClient) -> None:
    destination = _destination(postgres_session, "Sajek")
    postgres_session.commit()
    response = client.get(f"/api/v1/destinations/{destination.id}/reviews")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=60"
    assert client.get("/api/v1/health").headers["cache-control"] == "no-store"


def test_database_rejects_bad_coordinates_phone_and_validity_window(postgres_session: Session) -> None:
    destination = _destination(postgres_session, "Sajek")
    postgres_session.commit()

    def expect_integrity_error(action: Any) -> None:
        with pytest.raises(IntegrityError):
            action()
        postgres_session.rollback()

    def bad_latitude() -> None:
        destination.latitude, destination.longitude = Decimal("91"), Decimal("90")
        postgres_session.commit()

    def lone_longitude() -> None:
        destination.latitude, destination.longitude = None, Decimal("90")
        postgres_session.commit()

    def bad_phone() -> None:
        _contact(postgres_session, destination, "Bad", ContactKind.OTHER, phone="call me")
        postgres_session.commit()

    def inverted_window() -> None:
        _advisory(postgres_session, destination, "Bad", valid_until=TODAY - timedelta(days=100))
        postgres_session.commit()

    for action in (bad_latitude, lone_longitude, bad_phone, inverted_window):
        expect_integrity_error(action)
