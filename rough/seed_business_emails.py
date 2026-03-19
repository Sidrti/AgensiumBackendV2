"""
Backfill profile business_email for all existing users who do not have one.
Sets them to the user's primary email.
"""
import os
import sys
from sqlalchemy.orm import Session

# Add project root to python path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import SessionLocal
from db import models

def seed_business_emails():
    db: Session = SessionLocal()
    try:
        # Get profiles where business_email is null or empty string
        profiles = db.query(models.Profile).filter(
            (models.Profile.business_email == None) | (models.Profile.business_email == "")
        ).all()
        
        updated_count = 0
        for profile in profiles:
            user = db.query(models.User).filter(models.User.id == profile.user_id).first()
            if user and user.email:
                profile.business_email = user.email
                updated_count += 1
            
        if updated_count > 0:
            db.commit()
            print(f"[SUCCESS] Updated {updated_count} profiles with default business emails.")
        else:
            print("[SUCCESS] All profiles already have a business email. No updates needed.")
            
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error updating business emails: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("--- Starting Profile Business Email Seed ---")
    seed_business_emails()
