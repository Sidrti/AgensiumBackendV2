import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from db.database import engine

def fix():
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE profiles MODIFY COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL;"))
            conn.commit()
        print("Successfully fixed `updated_at` column to have a default timestamp!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix()
