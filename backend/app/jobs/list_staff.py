"""List the active staff roles (read-only), to see who the superadmin and moderators are.

    python -m app.jobs.list_staff
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import User, UserRole


def main() -> None:
    with SessionLocal() as session:
        rows = session.execute(
            select(User.email, User.display_name, UserRole.role, UserRole.granted_at)
            .join(UserRole, UserRole.user_id == User.id)
            .where(UserRole.revoked_at.is_(None))
            .order_by(UserRole.role, UserRole.granted_at)
        ).all()
    if not rows:
        print("No active staff roles.")
    for email, name, role, granted_at in rows:
        print(f"{role:12} {email}  ({name})  since {granted_at:%Y-%m-%d}")


if __name__ == "__main__":
    main()
