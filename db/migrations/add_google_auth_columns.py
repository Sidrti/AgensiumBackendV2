"""
Migration: Add Google OAuth columns to users table

Adds auth_provider, google_id, and profile_picture columns.
Makes hashed_password nullable (Google users have no password).

Run with: python -m db.migrations.add_google_auth_columns
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from db.database import engine


MIGRATION_STEPS = [
    {
        "description": "Make hashed_password nullable",
        "sql": "ALTER TABLE users MODIFY COLUMN hashed_password VARCHAR(255) NULL;"
    },
    {
        "description": "Add auth_provider column",
        "sql": "ALTER TABLE users ADD COLUMN auth_provider VARCHAR(20) NOT NULL DEFAULT 'local' AFTER hashed_password;"
    },
    {
        "description": "Add google_id column",
        "sql": "ALTER TABLE users ADD COLUMN google_id VARCHAR(255) NULL UNIQUE AFTER auth_provider;"
    },
    {
        "description": "Add profile_picture column",
        "sql": "ALTER TABLE users ADD COLUMN profile_picture VARCHAR(500) NULL AFTER google_id;"
    },
    {
        "description": "Add index on google_id",
        "sql": "CREATE INDEX idx_users_google_id ON users(google_id);"
    },
    {
        "description": "Add index on auth_provider",
        "sql": "CREATE INDEX idx_users_auth_provider ON users(auth_provider);"
    },
]


def run_migration():
    """Execute the migration to add Google auth columns."""
    print("=" * 60)
    print("Running migration: Add Google OAuth columns to users table")
    print("=" * 60)

    with engine.connect() as conn:
        for i, step in enumerate(MIGRATION_STEPS, 1):
            print(f"\n[{i}/{len(MIGRATION_STEPS)}] {step['description']}...")
            try:
                conn.execute(text(step["sql"]))
                conn.commit()
                print(f"      ✓ Done")
            except Exception as e:
                error_msg = str(e).lower()
                if "duplicate" in error_msg or "already exists" in error_msg:
                    print(f"      ⚠ Already exists, skipping")
                else:
                    print(f"      ✗ Error: {e}")
                    raise

    print("\n" + "=" * 60)
    print("Migration completed successfully!")
    print("=" * 60)


def verify_columns():
    """Verify the new columns were added."""
    print("\nVerifying users table structure...")

    with engine.connect() as conn:
        result = conn.execute(text("DESCRIBE users"))
        columns = result.fetchall()

        print("\nUsers table columns:")
        print("-" * 50)
        for col in columns:
            print(f"  {col[0]:<25} {col[1]}")
        print("-" * 50)
        print(f"Total columns: {len(columns)}")

        # Check for new columns
        col_names = [col[0] for col in columns]
        new_cols = ["auth_provider", "google_id", "profile_picture"]
        for nc in new_cols:
            status = "✓" if nc in col_names else "✗"
            print(f"  {status} {nc}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Add Google auth columns migration")
    parser.add_argument("--verify", action="store_true", help="Only verify table structure")
    args = parser.parse_args()

    if args.verify:
        verify_columns()
    else:
        run_migration()
        verify_columns()
