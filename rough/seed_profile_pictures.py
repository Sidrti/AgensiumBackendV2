"""
Backfill profile pictures for all existing users who do not have one.
Sets them to DiceBear bottts avatars.
"""
import os
import sys
import urllib.parse
from sqlalchemy.orm import Session

# Add project root to python path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import SessionLocal
from db import models

def seed_profile_pictures():
    db: Session = SessionLocal()
    try:
        users = db.query(models.User).filter(
            (models.User.profile_picture == None) | (models.User.profile_picture == "")
        ).all()
        
        updated_count = 0
        for user in users:
            # Default to "User" if full_name is somehow empty
            encoded_name = urllib.parse.quote(user.full_name or "User")
            user.profile_picture = f"https://api.dicebear.com/9.x/bottts/svg?seed={encoded_name}&backgroundColor=00aeef"
            updated_count += 1
            
        if updated_count > 0:
            db.commit()
            print(f"✅ Successfully updated {updated_count} users with default profile pictures.")
        else:
            print("✅ All users already have profile pictures. No updates needed.")
            
    except Exception as e:
        db.rollback()
        print(f"❌ Error updating profile pictures: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("--- Starting Profile Picture Seed ---")
    seed_profile_pictures()
