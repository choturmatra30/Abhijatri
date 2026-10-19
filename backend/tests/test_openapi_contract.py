import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_exporter():
    spec = importlib.util.spec_from_file_location("export_openapi", ROOT / "scripts" / "export_openapi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_openapi_snapshot_matches_code() -> None:
    exporter = _load_exporter()
    committed = exporter.SNAPSHOT.read_text(encoding="utf-8")
    assert committed == exporter.render(), (
        "API contract drift: run `uv run python scripts/export_openapi.py` and commit Docs/api/openapi-v1.json"
    )


def test_every_implemented_route_is_documented() -> None:
    exporter = _load_exporter()
    api_doc = (exporter.SNAPSHOT.parent / "API.md").read_text(encoding="utf-8")
    from app.main import create_app

    for route in create_app().openapi()["paths"]:
        path = route.removeprefix("/api/v1")
        assert path in api_doc, f"{path} missing from Docs/api/API.md"
