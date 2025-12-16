"""
Migration Script: Convert Transaction IDs from Integer to ULID

This script migrates the credit_transactions table to use ULID-based primary keys
instead of auto-incrementing integers.

ULID Format:
- 26 characters (Base32 encoded)
- Time-sortable (first 10 chars = timestamp)
- Globally unique
- No hyphens (more compact than UUID)

Example ULID: 01HGW5Z9K8QRST12345ABCDEFG

Migration Strategy:
1. Add new `id_ulid` column (String 26, nullable)
2. Generate ULIDs for all existing rows (preserving time-order via created_at)
3. Make `id_ulid` NOT NULL and PRIMARY KEY
4. Drop old `id` column (auto-increment integer)
5. Rename `id_ulid` to `id`

IMPORTANT: This is a DESTRUCTIVE migration. Backup your database first!
"""

import sys
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, text, inspect
from sqlalchemy.orm import sessionmaker, Session
import ulid

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from db.database import get_db_url
from db.models import CreditTransaction


def generate_time_based_ulid(created_at: datetime) -> str:
    """
    Generate a ULID based on a specific timestamp.
    
    This preserves the chronological ordering of existing transactions.
    
    Args:
        created_at: The timestamp to use for ULID generation
        
    Returns:
        26-character ULID string
    """
    # Generate ULID from timestamp (expects float in seconds)
    timestamp_seconds = created_at.timestamp()
    new_ulid = ulid.ULID.from_timestamp(timestamp_seconds)
    
    return str(new_ulid)


def verify_tables_exist(engine) -> bool:
    """Verify that credit_transactions table exists."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if 'credit_transactions' not in tables:
        print("❌ Error: credit_transactions table does not exist")
        return False
    
    return True


def backup_prompt():
    """Prompt user to confirm database backup."""
    print("\n" + "="*70)
    print("⚠️  WARNING: DESTRUCTIVE MIGRATION")
    print("="*70)
    print("\nThis migration will:")
    print("1. Change the primary key from Integer to ULID (String)")
    print("2. Drop the existing auto-increment 'id' column")
    print("3. All existing transaction IDs will be replaced with ULIDs")
    print("\n💾 IMPORTANT: Have you backed up your database?")
    print("="*70)
    
    response = input("\nType 'YES' to proceed or 'NO' to cancel: ").strip().upper()
    
    if response != 'YES':
        print("\n❌ Migration cancelled")
        sys.exit(0)
    
    print("\n✅ Proceeding with migration...\n")


def migrate_transaction_ids(db_url: str, dry_run: bool = False):
    """
    Migrate transaction IDs from integer to ULID.
    
    Args:
        db_url: Database connection URL
        dry_run: If True, only show what would be done without making changes
    """
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        print(f"\n{'='*70}")
        print(f"🚀 Transaction ID Migration to ULID")
        print(f"{'='*70}")
        print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE MIGRATION'}")
        print(f"Database: {db_url.split('@')[1] if '@' in db_url else 'local'}")
        print(f"{'='*70}\n")
        
        # Verify tables exist
        if not verify_tables_exist(engine):
            return False
        
        # Get transaction count
        count_query = text("SELECT COUNT(*) as cnt FROM credit_transactions")
        result = db.execute(count_query)
        total_transactions = result.fetchone()[0]
        
        print(f"📊 Found {total_transactions} existing transactions\n")
        
        if total_transactions == 0:
            print("✅ No transactions to migrate. Table is empty.")
            return True
        
        if not dry_run:
            backup_prompt()
        
        # STEP 1: Add id_ulid column
        print("STEP 1: Adding id_ulid column...")
        if not dry_run:
            try:
                alter_add_column = text("""
                    ALTER TABLE credit_transactions 
                    ADD COLUMN id_ulid VARCHAR(26) NULL
                """)
                db.execute(alter_add_column)
                db.commit()
                print("✅ Added id_ulid column\n")
            except Exception as e:
                if 'Duplicate column name' in str(e):
                    print("⚠️  Column id_ulid already exists, skipping...\n")
                else:
                    raise
        else:
            print("  [DRY RUN] Would add id_ulid VARCHAR(26) NULL column\n")
        
        # STEP 2: Generate ULIDs for existing rows
        print("STEP 2: Generating ULIDs for existing transactions...")
        
        # Fetch all transactions ordered by created_at
        fetch_query = text("""
            SELECT id, created_at 
            FROM credit_transactions 
            ORDER BY created_at ASC, id ASC
        """)
        transactions = db.execute(fetch_query).fetchall()
        
        print(f"  Processing {len(transactions)} transactions...")
        
        ulid_map = {}
        for idx, (old_id, created_at) in enumerate(transactions, 1):
            new_ulid = generate_time_based_ulid(created_at)
            ulid_map[old_id] = new_ulid
            
            if not dry_run:
                update_query = text("""
                    UPDATE credit_transactions 
                    SET id_ulid = :ulid 
                    WHERE id = :old_id
                """)
                db.execute(update_query, {"ulid": new_ulid, "old_id": old_id})
                
                if idx % 100 == 0:
                    db.commit()
                    print(f"  ✓ Processed {idx}/{len(transactions)} transactions")
        
        if not dry_run:
            db.commit()
            print(f"✅ Generated and assigned ULIDs for all {len(transactions)} transactions\n")
        else:
            print(f"  [DRY RUN] Would generate ULIDs for {len(transactions)} transactions")
            print(f"  Example mappings:")
            for old_id, new_ulid in list(ulid_map.items())[:5]:
                print(f"    {old_id} → {new_ulid}")
            print("\n")
        
        # STEP 3: Verify no NULL ULIDs
        print("STEP 3: Verifying ULID generation...")
        if not dry_run:
            null_check = text("SELECT COUNT(*) FROM credit_transactions WHERE id_ulid IS NULL")
            result = db.execute(null_check)
            null_count = result.fetchone()[0]
            
            if null_count > 0:
                raise Exception(f"❌ Found {null_count} transactions with NULL ULIDs!")
            
            print("✅ All transactions have valid ULIDs\n")
        else:
            print("  [DRY RUN] Would verify no NULL ULIDs\n")
        
        # STEP 4: Drop primary key constraint on old id
        print("STEP 4: Dropping old primary key and creating new one...")
        if not dry_run:
            # Since sql_require_primary_key is set, we need to add new PK before dropping old one
            # First, drop old PK and add new PK in one ALTER statement
            alter_pk_query = text("""
                ALTER TABLE credit_transactions 
                DROP PRIMARY KEY,
                ADD PRIMARY KEY (id_ulid)
            """)
            db.execute(alter_pk_query)
            db.commit()
            print("✅ Switched primary key from id to id_ulid\n")
        else:
            print("  [DRY RUN] Would drop old PRIMARY KEY and add new PRIMARY KEY to id_ulid\n")
        
        # STEP 5: Make id_ulid NOT NULL (already done by PRIMARY KEY)
        # STEP 5: Make id_ulid NOT NULL (already done by PRIMARY KEY)
        print("STEP 5: Verifying id_ulid is NOT NULL...")
        if not dry_run:
            print("✅ id_ulid is NOT NULL (enforced by PRIMARY KEY)\n")
        else:
            print("  [DRY RUN] Would verify id_ulid is NOT NULL\n")
        
        # STEP 6: Drop old id column (no longer needed)
        # STEP 6: Drop old id column (no longer needed)
        print("STEP 6: Dropping old integer id column...")
        if not dry_run:
            drop_old_id = text("ALTER TABLE credit_transactions DROP COLUMN id")
            db.execute(drop_old_id)
            db.commit()
            print("✅ Dropped old integer id column\n")
        else:
            print("  [DRY RUN] Would drop old 'id' column\n")
        
        # STEP 7: Rename id_ulid to id
        print("STEP 7: Renaming id_ulid to id...")
        if not dry_run:
            rename_query = text("ALTER TABLE credit_transactions CHANGE COLUMN id_ulid id VARCHAR(26)")
            db.execute(rename_query)
            db.commit()
            print("✅ Renamed id_ulid to id\n")
        else:
            print("  [DRY RUN] Would rename id_ulid to id\n")
        
        # STEP 8: Verify final state
        print("STEP 8: Verifying migration...")
        if not dry_run:
            verify_query = text("""
                SELECT COUNT(*) as cnt, 
                       MIN(LENGTH(id)) as min_len, 
                       MAX(LENGTH(id)) as max_len
                FROM credit_transactions
            """)
            result = db.execute(verify_query).fetchone()
            count, min_len, max_len = result
            
            print(f"  ✓ Total transactions: {count}")
            print(f"  ✓ ID length range: {min_len}-{max_len} chars")
            
            if min_len != 26 or max_len != 26:
                print(f"  ⚠️  Warning: Expected all IDs to be 26 chars (ULID format)")
            
            # Show sample
            sample_query = text("SELECT id, type, delta_credits FROM credit_transactions LIMIT 3")
            samples = db.execute(sample_query).fetchall()
            print("\n  Sample transactions:")
            for sample_id, sample_type, delta in samples:
                print(f"    ID: {sample_id} | Type: {sample_type} | Delta: {delta}")
            
            print("\n✅ Migration completed successfully!\n")
        else:
            print("  [DRY RUN] Would verify final state\n")
        
        print(f"{'='*70}")
        print(f"✨ Migration {'would be' if dry_run else 'is'} complete!")
        print(f"{'='*70}\n")
        
        if not dry_run:
            print("📝 Summary:")
            print(f"  - Migrated {total_transactions} transactions")
            print(f"  - Old integer IDs replaced with ULID strings")
            print(f"  - Primary key changed from Integer to VARCHAR(26)")
            print(f"  - Time-ordering preserved via ULID timestamps\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def rollback_migration(db_url: str):
    """
    Rollback the ULID migration (if migration was incomplete).
    
    WARNING: This will NOT recover the old integer IDs.
    This is only useful if the migration partially failed.
    """
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        print("\n⚠️  Attempting rollback...")
        print("NOTE: This will NOT restore old integer IDs.")
        print("This only removes the id_ulid column if migration failed partway.\n")
        
        response = input("Type 'YES' to proceed with rollback: ").strip().upper()
        if response != 'YES':
            print("Rollback cancelled")
            return
        
        # Check if id_ulid column exists
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('credit_transactions')]
        
        if 'id_ulid' in columns:
            print("Dropping id_ulid column...")
            drop_query = text("ALTER TABLE credit_transactions DROP COLUMN id_ulid")
            db.execute(drop_query)
            db.commit()
            print("✅ Dropped id_ulid column")
        else:
            print("⚠️  id_ulid column not found - nothing to rollback")
        
    except Exception as e:
        print(f"❌ Rollback failed: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate transaction IDs to ULID")
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='Rollback migration (removes id_ulid column if exists)'
    )
    
    args = parser.parse_args()
    
    # Get database URL from environment
    try:
        db_url = get_db_url()
    except Exception as e:
        print(f"❌ Error getting database URL: {e}")
        print("Make sure DATABASE_URL is set in your .env file")
        sys.exit(1)
    
    if args.rollback:
        rollback_migration(db_url)
    else:
        try:
            success = migrate_transaction_ids(db_url, dry_run=args.dry_run)
            if success:
                sys.exit(0)
            else:
                sys.exit(1)
        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            sys.exit(1)
