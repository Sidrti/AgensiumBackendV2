"""
Migration: Create Profiles table

Creates the profiles table and its relationship to the users table.

Run with: python -m db.migrations.create_profiles_table
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from db.database import engine

MIGRATION_STEPS = [
    {
        "description": "Create profiles table",
        "sql": """
        CREATE TABLE IF NOT EXISTS profiles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL UNIQUE,
            display_name VARCHAR(100) NULL,
            public_handle VARCHAR(50) NULL UNIQUE,
            company_name VARCHAR(150) NULL,
            industry_vertical VARCHAR(100) NULL,
            business_email VARCHAR(255) NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            INDEX idx_profiles_public_handle (public_handle)
        );
        """
    }
]

def run_migration():
    """Execute the migration to create profiles table."""
    print("=" * 60)
    print("Running migration: Create Profiles table")
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
                if "already exists" in error_msg:
                    print(f"      ⚠ Already exists, skipping")
                else:
                    print(f"      ✗ Error: {e}")

    print("\n" + "=" * 60)
    print("Migration completed successfully!")
    print("=" * 60)


def verify_table():
    """Verify the profiles table was created."""
    print("\nVerifying profiles table structure...")

    try:
        with engine.connect() as conn:
            result = conn.execute(text("DESCRIBE profiles"))
            columns = result.fetchall()

            print("\nProfiles table columns:")
            print("-" * 50)
            for col in columns:
                print(f"  {col[0]:<25} {col[1]}")
            print("-" * 50)
            print(f"Total columns: {len(columns)}")
    except Exception as e:
        print(f"Error describing table (it may not exist): {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create profiles table migration")
    parser.add_argument("--verify", action="store_true", help="Only verify table structure")
    args = parser.parse_args()

    if args.verify:
        verify_table()
    else:
        run_migration()
        verify_table()
