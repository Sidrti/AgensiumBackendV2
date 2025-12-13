"""
Database Migration Script for Billing Tables

This script creates all required billing tables:
- Adds stripe_customer_id to users table
- Creates credit_wallets table
- Creates credit_transactions table
- Creates stripe_webhook_events table
- Creates agent_costs table

Run this script once to set up billing tables.
For production, consider using Alembic for proper migrations.

Usage:
    python -m billing.migrations.create_billing_tables
"""

import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from db.database import engine, SessionLocal
from db import models
from billing.agent_costs_service import seed_default_agent_costs


def run_migration():
    """Run the billing migration."""
    print("=" * 60)
    print("BILLING TABLES MIGRATION")
    print("=" * 60)
    
    # Create all tables defined in models
    print("\n1. Creating tables...")
    try:
        models.Base.metadata.create_all(bind=engine)
        print("   ✓ All tables created successfully")
    except Exception as e:
        print(f"   ✗ Error creating tables: {e}")
        return False
    
    # Verify tables exist
    print("\n2. Verifying tables...")
    required_tables = [
        "users",
        "credit_wallets",
        "credit_transactions",
        "stripe_webhook_events",
        "agent_costs"
    ]
    
    with engine.connect() as conn:
        for table in required_tables:
            try:
                result = conn.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
                print(f"   ✓ Table '{table}' exists")
            except Exception as e:
                print(f"   ✗ Table '{table}' missing or error: {e}")
    
    # Seed default agent costs
    print("\n3. Seeding default agent costs...")
    try:
        db = SessionLocal()
        seed_default_agent_costs(db)
        db.close()
        print("   ✓ Default agent costs seeded")
    except Exception as e:
        print(f"   ✗ Error seeding agent costs: {e}")
    
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    
    return True


def verify_stripe_columns():
    """Verify stripe_customer_id column exists in users table."""
    print("\n4. Verifying stripe_customer_id column...")
    
    try:
        with engine.connect() as conn:
            # MySQL specific query
            result = conn.execute(text("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'stripe_customer_id'
            """))
            
            if result.fetchone():
                print("   ✓ stripe_customer_id column exists in users table")
                return True
            else:
                print("   ✗ stripe_customer_id column NOT FOUND in users table")
                print("   Run: ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR(255) UNIQUE;")
                return False
    except Exception as e:
        print(f"   ✗ Error checking column: {e}")
        return False


def show_migration_sql():
    """Print SQL statements for manual migration."""
    print("\n" + "=" * 60)
    print("MANUAL MIGRATION SQL (if needed)")
    print("=" * 60)
    
    sql = """
-- Add stripe_customer_id to users (if not exists)
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255) UNIQUE;

-- Create credit_wallets table
CREATE TABLE IF NOT EXISTS credit_wallets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    balance_credits INT NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT check_balance_non_negative CHECK (balance_credits >= 0),
    INDEX idx_credit_wallets_user_id (user_id)
);

-- Create credit_transactions table
CREATE TABLE IF NOT EXISTS credit_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    delta_credits INT NOT NULL,
    type VARCHAR(50) NOT NULL,
    reason VARCHAR(500),
    agent_id VARCHAR(100),
    tool_id VARCHAR(100),
    analysis_id VARCHAR(100),
    stripe_checkout_session_id VARCHAR(255) UNIQUE,
    stripe_payment_intent_id VARCHAR(255) UNIQUE,
    stripe_event_id VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_credit_transactions_user_id (user_id),
    INDEX idx_credit_transactions_agent_id (agent_id),
    INDEX idx_credit_transactions_stripe_event_id (stripe_event_id)
);

-- Create stripe_webhook_events table
CREATE TABLE IF NOT EXISTS stripe_webhook_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stripe_event_id VARCHAR(255) NOT NULL UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_at DATETIME,
    payload_json JSON,
    INDEX idx_stripe_webhook_events_event_id (stripe_event_id)
);

-- Create agent_costs table
CREATE TABLE IF NOT EXISTS agent_costs (
    agent_id VARCHAR(100) PRIMARY KEY,
    cost INT NOT NULL,
    description VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Seed default agent costs
INSERT IGNORE INTO agent_costs (agent_id, cost, description) VALUES
    ('unified-profiler', 30, 'Data profiling and statistics'),
    ('readiness-rater', 25, 'Data readiness assessment'),
    ('drift-detector', 40, 'Data drift detection'),
    ('score-risk', 35, 'Risk scoring'),
    ('governance-checker', 45, 'Governance compliance check'),
    ('test-coverage-agent', 30, 'Test coverage analysis'),
    ('null-handler', 30, 'Null value handling'),
    ('outlier-remover', 35, 'Outlier detection and removal'),
    ('type-fixer', 25, 'Data type correction'),
    ('duplicate-resolver', 50, 'Duplicate detection and resolution'),
    ('field-standardization', 40, 'Field value standardization'),
    ('quarantine-agent', 35, 'Data quarantine management'),
    ('cleanse-writeback', 30, 'Cleaned data writeback'),
    ('cleanse-previewer', 20, 'Cleanse preview generation'),
    ('key-identifier', 45, 'Key field identification'),
    ('contract-enforcer', 75, 'Data contract enforcement'),
    ('semantic-mapper', 50, 'Semantic mapping'),
    ('lineage-tracer', 55, 'Data lineage tracing'),
    ('golden-record-builder', 150, 'Golden record construction'),
    ('survivorship-resolver', 100, 'Survivorship rule resolution'),
    ('master-writeback-agent', 60, 'Master data writeback'),
    ('stewardship-flagger', 40, 'Data stewardship flagging');
"""
    print(sql)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Billing tables migration")
    parser.add_argument("--sql", action="store_true", help="Print SQL statements only")
    parser.add_argument("--verify", action="store_true", help="Verify tables only")
    
    args = parser.parse_args()
    
    if args.sql:
        show_migration_sql()
    elif args.verify:
        verify_stripe_columns()
    else:
        run_migration()
        verify_stripe_columns()
