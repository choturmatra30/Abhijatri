"""The staff dashboard, served by this API at ``/staff`` (same origin, so no CORS and first-party cookies).

``make staff-bundle`` builds ``staff/`` with the base path ``/staff/`` and copies it to ``app/staff_site/``.
When that folder is absent (local development, tests) nothing is mounted. The page is for signed-in staff only;
it carries ``noindex`` and its own strict Content-Security-Policy, which the API-wide default must not replace.
"""

from pathlib import Path

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

SITE_DIR = Path(__file__).parent / "staff_site"
STAFF_HEADERS = {
    "X-Robots-Tag": "noindex, nofollow, noarchive",
    "Cache-Control": "no-store",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), payment=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data: https://*.supabase.co; "
        "media-src https://*.supabase.co; font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; "
        "frame-ancestors 'none'"
    ),
}


class StaffFiles(StaticFiles):
    def file_response(self, full_path: str | Path, stat_result: object, scope: Scope, status_code: int = 200):  # type: ignore[no-untyped-def,override]
        response = super().file_response(full_path, stat_result, scope, status_code)  # type: ignore[arg-type]
        response.headers.update(STAFF_HEADERS)
        return response


def mount_staff_site(application: FastAPI, directory: Path = SITE_DIR) -> bool:
    if not (directory / "index.html").is_file():
        return False
    application.mount("/staff", StaffFiles(directory=directory, html=True), name="staff")
    return True
