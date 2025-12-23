"""
Script to fetch and print all users with encrypted passwords using JWT.
"""
import sys
import os
sys.path.insert(0, '/Users/VIVEK BANSAL/Desktop/Agensium/Agensium-V2/backend')

from db.database import SessionLocal
from db.models import User
from jose import jwt
from dotenv import load_dotenv

load_dotenv()

# JWT Configuration from .env
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

def encrypt_password(password: str) -> str:
    """
    Encrypt a password using JWT.
    
    Args:
        password: The plain password to encrypt
        
    Returns:
        JWT encrypted password
    """
    try:
        encrypted_token = jwt.encode(
            {"password": password},
            SECRET_KEY,
            algorithm=ALGORITHM
        )
        return encrypted_token
    except Exception as e:
        return f"Error encrypting: {str(e)}"

def decrypt_password(encrypted_token: str) -> str:
    """
    Decrypt a JWT encrypted password.
    
    Args:
        encrypted_token: The JWT token containing encrypted password
        
    Returns:
        The decrypted password
    """
    try:
        payload = jwt.decode(
            encrypted_token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        return payload.get("password", "Error: No password in token")
    except Exception as e:
        return f"Error decrypting: {str(e)}"

def get_all_users():
    """Fetch and print all users with JWT encrypted/decrypted passwords."""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        
        if not users:
            print("No users found in the database.")
            return
        
        print("\n" + "="*80)
        print("ALL USERS WITH JWT ENCRYPTED PASSWORDS")
        print("="*80)
        
        for user in users:
            print(f"\nID: {user.id}")
            print(f"Email: {user.email}")
            print(f"Full Name: {user.full_name}")
            print(f"Password (Hashed/Original): {user.hashed_password}")
            print(f"Is Active: {user.is_active}")
            print(f"Is Verified: {user.is_verified}")
            print(f"Created At: {user.created_at}")
            print("-" * 80)
        
        print(f"\nTotal Users: {len(users)}")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"Error fetching users: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    get_all_users()
