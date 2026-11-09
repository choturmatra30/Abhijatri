"""Grant or revoke a staff role from the command line (server-side, audited).

    python -m app.jobs.grant_role --email person@example.com --role moderator
    python -m app.jobs.grant_role --email person@example.com --role superadmin
    python -m app.jobs.grant_role --email person@example.com --role none      (revoke)

Unlike ``bootstrap_admin`` this works when a superadmin already exists. Whoever can run it already
controls the server, the same trust as ``reset_mfa``. The rules of ``roles.set_staff_role`` still
apply: the account must be active, a moderator must be a Verified Member, and the last superadmin
cannot be removed. The change is audited like one made from the staff screen.
"""

import argparse
import sys

from sqlalchemy import select

from app.admin import roles
from app.db import SessionLocal
from app.errors import ApiError
from app.models import User


def run(email: str, role: str, *, assume_yes: bool = False) -> int:
    email = email.strip().lower()
    new_role = None if role == "none" else role
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == email))
        if user is None or user.email_verified_at is None:
            print("Refused: no verified account with that email. Register and verify it first.", file=sys.stderr)
            return 3
        if not assume_yes:
            typed = input(f"Set role of {user.display_name} <{email}> to {role}? Type the email to confirm: ").strip().lower()
            if typed != email:
                print("Cancelled.", file=sys.stderr)
                return 1
        try:
            roles.set_staff_role(session, actor=None, target_user_id=user.id, role=new_role, reason=f"cli: {role}")
            session.commit()
        except ApiError as error:
            session.rollback()
            print(f"Refused: {error.code}", file=sys.stderr)
            return 4
    print(f"Done. {email} now has role: {role}. Staff sign in with an authenticator app (TOTP) on first use.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Grant or revoke a staff role.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True, choices=["moderator", "superadmin", "none"])
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    arguments = parser.parse_args()
    sys.exit(run(arguments.email, arguments.role, assume_yes=arguments.yes))


if __name__ == "__main__":
    main()
