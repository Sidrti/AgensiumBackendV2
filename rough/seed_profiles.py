import sys
import os
import re
import ulid

# Add the backend directory to sys.path so we can import db modules
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from db.database import SessionLocal
from db.models import User, Profile

def generate_unique_handle(full_name: str, db) -> str:
    """Safely generate a unique handle for backfilling."""
    base_handle = full_name.lower().replace(" ", "_")
    base_handle = re.sub(r'[^a-z0-9_]', '', base_handle)
    
    if not base_handle:
        base_handle = "user"

    unique_handle = base_handle
    
    while True:
        exists = db.query(Profile).filter(Profile.public_handle == unique_handle).first()
        if not exists:
            return unique_handle
        random_suffix = str(ulid.ULID()).lower()[-6:]
        unique_handle = f"{base_handle}_{random_suffix}"

def seed_existing_profiles():
    print("=" * 60)
    print("Backfilling profiles for existing users...")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        users = db.query(User).all()
        created_count = 0
        
        for user in users:
            # Check if this user already has a profile using our model relationship
            if user.profile: 
                continue
                
            handle = generate_unique_handle(user.full_name, db)
            new_profile = Profile(
                user_id=user.id,
                display_name=user.full_name,
                public_handle=handle
            )
            db.add(new_profile)
            db.flush()  # Flush so the next handle generation query sees this new handle
            created_count += 1
            print(f"Created profile for User {user.id} ({user.email}) -> @{handle}")
            
        db.commit()
        print("-" * 60)
        print(f"Successfully backfilled profiles for {created_count} users.")
    except Exception as e:
        print(f"Error seeding profiles: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_existing_profiles()
