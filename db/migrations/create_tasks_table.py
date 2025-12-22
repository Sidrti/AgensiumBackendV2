"""
Migration: Create tasks table for V2.1 architecture

This migration creates the tasks table with all required columns and indexes.
Run with: python -m db.migrations.create_tasks_table
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from db.database import engine


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id VARCHAR(36) PRIMARY KEY COMMENT 'UUID task identifier',
    user_id INTEGER NOT NULL COMMENT 'Foreign key to users table',
    tool_id VARCHAR(50) NOT NULL COMMENT 'Tool identifier (profile-my-data, clean-my-data, master-my-data)',
    agents JSON NOT NULL COMMENT 'Array of agent IDs to execute',
    status VARCHAR(20) NOT NULL DEFAULT 'CREATED' COMMENT 'Task status',
    progress INTEGER NOT NULL DEFAULT 0 COMMENT 'Progress percentage 0-100',
    current_agent VARCHAR(100) NULL COMMENT 'Currently executing agent',
    error_code VARCHAR(50) NULL COMMENT 'Error code if failed',
    error_message TEXT NULL COMMENT 'Error message if failed',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Task creation time',
    upload_started_at DATETIME NULL COMMENT 'When file upload started',
    processing_started_at DATETIME NULL COMMENT 'When processing started',
    completed_at DATETIME NULL COMMENT 'When task completed successfully',
    failed_at DATETIME NULL COMMENT 'When task failed',
    cancelled_at DATETIME NULL COMMENT 'When task was cancelled',
    expired_at DATETIME NULL COMMENT 'When task expired',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last update time',
    s3_cleaned BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Whether S3 files have been cleaned up',
    CONSTRAINT fk_task_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX idx_tasks_user_id ON tasks(user_id);",
    "CREATE INDEX idx_tasks_status ON tasks(status);",
    "CREATE INDEX idx_tasks_user_status ON tasks(user_id, status);",
    "CREATE INDEX idx_tasks_created_at ON tasks(created_at);",
    "CREATE INDEX idx_tasks_tool_id ON tasks(tool_id);"
]


def run_migration():
    """Execute the migration to create tasks table."""
    print("=" * 60)
    print("Running migration: Create tasks table")
    print("=" * 60)
    
    with engine.connect() as conn:
        # Create table
        print("\n[1/2] Creating tasks table...")
        try:
            conn.execute(text(CREATE_TABLE_SQL))
            conn.commit()
            print("      ✓ Tasks table created successfully")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("      ⚠ Tasks table already exists, skipping")
            else:
                print(f"      ✗ Error creating table: {e}")
                raise
        
        # Create indexes
        print("\n[2/2] Creating indexes...")
        for i, index_sql in enumerate(CREATE_INDEXES_SQL, 1):
            try:
                conn.execute(text(index_sql))
                conn.commit()
                index_name = index_sql.split()[2]
                print(f"      ✓ Index {index_name} created")
            except Exception as e:
                if "Duplicate key name" in str(e) or "already exists" in str(e).lower():
                    index_name = index_sql.split()[2]
                    print(f"      ⚠ Index {index_name} already exists, skipping")
                else:
                    print(f"      ✗ Error creating index: {e}")
                    raise
    
    print("\n" + "=" * 60)
    print("Migration completed successfully!")
    print("=" * 60)


def verify_table():
    """Verify the tasks table was created correctly."""
    print("\nVerifying table structure...")
    
    with engine.connect() as conn:
        result = conn.execute(text("DESCRIBE tasks"))
        columns = result.fetchall()
        
        print("\nTasks table columns:")
        print("-" * 50)
        for col in columns:
            print(f"  {col[0]:<25} {col[1]}")
        print("-" * 50)
        print(f"Total columns: {len(columns)}")
        
        # Verify indexes
        result = conn.execute(text("SHOW INDEX FROM tasks"))
        indexes = result.fetchall()
        
        print("\nTasks table indexes:")
        print("-" * 50)
        index_names = set()
        for idx in indexes:
            index_names.add(idx[2])  # Key_name is at index 2
        for name in sorted(index_names):
            print(f"  {name}")
        print("-" * 50)
        print(f"Total indexes: {len(index_names)}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Create tasks table migration")
    parser.add_argument("--verify", action="store_true", help="Only verify table structure")
    args = parser.parse_args()
    
    if args.verify:
        verify_table()
    else:
        run_migration()
        verify_table()
