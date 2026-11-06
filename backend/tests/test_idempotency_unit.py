"""R16 and B6 without a database: key parsing, fingerprints, scopes and pooler settings."""

import uuid

import pytest
from pydantic import BaseModel

from app import idempotency as idem
from app.config import Settings
from app.db import connect_args_for
from app.errors import ApiError

GOOD_PEPPER = "x" * 40
POOLER = "postgresql://postgres.ref:pw@aws-0-ap-southeast-1.pooler.supabase.com"


@pytest.fixture(autouse=True)
def _hermetic_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {"app_env": "test", "receipt_pepper": GOOD_PEPPER}
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


class Body(BaseModel):
    title: str
    turnstile_token: str | None = None


# ---------- Idempotency-Key header ----------


def test_an_absent_header_means_no_idempotency() -> None:
    assert idem.parse_key(None) is None


def test_a_uuid_key_is_accepted_and_canonical() -> None:
    key = str(uuid.uuid4())
    assert idem.parse_key(key) == key
    assert idem.parse_key(f"  {key}  ") == key
    assert idem.parse_key(key.upper()) == key


@pytest.mark.parametrize(
    "value",
    ["", "not-a-uuid", "1234", "{" + str(uuid.uuid4()) + "}", str(uuid.uuid4()).replace("-", ""), "x" * 36],
)
def test_a_malformed_key_is_a_validation_error_on_the_header(value: str) -> None:
    with pytest.raises(ApiError) as caught:
        idem.parse_key(value)
    assert caught.value.code == "VALIDATION_FAILED"
    assert caught.value.field_errors == [{"field": "Idempotency-Key", "code": "INVALID_VALUE"}]


# ---------- fingerprints ----------


def test_fingerprint_is_stable_and_order_independent() -> None:
    assert idem.fingerprint({"a": 1, "b": [1, 2]}) == idem.fingerprint({"b": [1, 2], "a": 1})
    assert len(idem.fingerprint({})) == 64


def test_the_turnstile_token_does_not_change_the_request_fingerprint() -> None:
    first = idem.request_fingerprint(method="POST", path={}, body=Body(title="t", turnstile_token="one"))
    retry = idem.request_fingerprint(method="POST", path={}, body=Body(title="t", turnstile_token="two"))
    assert first == retry


def test_body_method_and_path_all_change_the_request_fingerprint() -> None:
    base = idem.request_fingerprint(method="POST", path={"review_id": "a"}, body=Body(title="t"))
    assert base != idem.request_fingerprint(method="POST", path={"review_id": "a"}, body=Body(title="u"))
    assert base != idem.request_fingerprint(method="PATCH", path={"review_id": "a"}, body=Body(title="t"))
    assert base != idem.request_fingerprint(method="POST", path={"review_id": "b"}, body=Body(title="t"))


# ---------- scopes ----------


def test_scopes_are_keyed_digests_separated_by_kind() -> None:
    secret = "s" * 43
    guest, receipt = idem.guest_scope(secret), idem.receipt_scope(secret)
    member = idem.member_scope(uuid.UUID(int=1))
    assert len({guest, receipt, member}) == 3, "the same value under two kinds never collides"
    assert all(len(scope) == 32 for scope in (guest, receipt, member))
    assert secret.encode() not in guest + receipt
    assert idem.guest_scope(secret) == guest, "deterministic"


def test_only_success_responses_are_stored() -> None:
    claim = idem.Claim(scope=b"s" * 32, endpoint="x", key_digest="0" * 64)
    with pytest.raises(ValueError):
        idem.finish(None, claim, 409, Body(title="t"))  # type: ignore[arg-type]


def test_a_replay_answers_with_the_stored_status_body_and_marker() -> None:
    response = idem.replay_response(idem.Replay(status_code=201, body={"review_id": "r"}))
    assert response.status_code == 201
    assert response.body == b'{"review_id":"r"}'
    assert response.headers["Idempotent-Replayed"] == "true"
    assert response.headers["Cache-Control"] == "no-store"


# ---------- B6: transaction-mode pooler ----------


def test_prepared_statements_are_off_for_the_transaction_pooler() -> None:
    settings = _settings(database_url=f"{POOLER}:6543/postgres")
    assert settings.uses_prepared_statements is False
    assert connect_args_for(settings)["prepare_threshold"] is None


def test_prepared_statements_stay_on_for_the_session_pooler_and_local_databases() -> None:
    for url in (f"{POOLER}:5432/postgres", "postgresql+psycopg://u:p@127.0.0.1:54322/abhijatri"):
        settings = _settings(database_url=url)
        assert settings.uses_prepared_statements is True
        assert "prepare_threshold" not in connect_args_for(settings)


def test_the_explicit_setting_wins_over_the_port() -> None:
    assert _settings(database_url=f"{POOLER}:5432/postgres", db_prepared_statements=False).uses_prepared_statements is False
    assert _settings(database_url=f"{POOLER}:6543/postgres", db_prepared_statements=True).uses_prepared_statements is True


def test_connect_args_always_carry_the_connect_timeout() -> None:
    assert connect_args_for(_settings(db_connect_timeout=7))["connect_timeout"] == 7


def test_the_replay_window_defaults_to_72_hours_and_is_bounded() -> None:
    assert _settings().idempotency_ttl_hours == 72
    with pytest.raises(ValueError):
        _settings(idempotency_ttl_hours=0)
