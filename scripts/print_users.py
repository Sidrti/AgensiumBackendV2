"""Utility script: print all users from the database.

Run from the `backend` directory so the `db` package imports correctly:

    python -u scripts/print_users.py

This script uses the SQLAlchemy SessionLocal from `db.database`.
"""
import sys
import os
# Ensure project root (backend/) is on sys.path so `import db` works when running
# the script as `python scripts/print_users.py` (sys.path[0] would otherwise be
# backend/scripts/ which doesn't contain the `db` package).
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from db.database import SessionLocal
from db.models import User


def main():
    session = SessionLocal()
    try:
        users = session.query(User).all()
        if not users:
            print("No users found")
            return

        for u in users:
            created = u.created_at.isoformat() if getattr(u, "created_at", None) else ""
            updated = u.updated_at.isoformat() if getattr(u, "updated_at", None) else ""
            otp_expires = u.otp_expires_at.isoformat() if getattr(u, "otp_expires_at", None) else ""
            wallet_balance = getattr(u, "wallet", None).balance_credits if getattr(u, "wallet", None) else None

            print(
                "\t".join([
                    f"id={u.id}",
                    f"email={u.email}",
                    f"full_name={u.full_name}",
                    f"auth_provider={u.auth_provider}",
                    f"is_active={u.is_active}",
                    f"is_verified={u.is_verified}",
                    f"stripe_customer_id={u.stripe_customer_id}",
                    f"wallet_balance={wallet_balance}",
                    f"created_at={created}",
                    f"updated_at={updated}",
                    f"otp_expires_at={otp_expires}",
                ])
            )

    except Exception as e:
        print("Error querying users:", e, file=sys.stderr)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
