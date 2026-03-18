import sys
import os

# Add the backend directory to sys.path so we can import db modules
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from db.database import SessionLocal
from db.models import Profile

def print_profiles():
    print("=" * 60)
    print("Querying Profiles Table...")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        profiles = db.query(Profile).all()
        if not profiles:
            print("The profiles table is completely empty (no users have triggered the creation logic yet).")
            return
            
        print(f"Found {len(profiles)} profiles:")
        print("-" * 80)
        for p in profiles:
            print(f"ID: {p.id} | User ID: {p.user_id} | Handle: @{p.public_handle} | Name: {p.display_name}")
            print(f"  Company: {p.company_name} | Vertical: {p.industry_vertical}")
            print(f"  Business Email: {p.business_email}")
            print("-" * 80)
    except Exception as e:
        print(f"Error querying table: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print_profiles()
