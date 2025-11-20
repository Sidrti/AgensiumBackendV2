# Authentication System

This project now includes a complete authentication system using JWT (JSON Web Tokens).

## Structure

- **`db/`**: Database related files.
  - `database.py`: Database connection and session handling.
  - `models.py`: SQLAlchemy database models (e.g., `User`).
  - `schemas.py`: Pydantic models for data validation (e.g., `UserCreate`, `Token`).
- **`auth/`**: Authentication logic.
  - `utils.py`: Utility functions for password hashing and JWT generation.
  - `dependencies.py`: FastAPI dependencies for protecting routes (e.g., `get_current_user`).
  - `router.py`: API endpoints for authentication (`/register`, `/token`, `/users/me`).

## Setup

1.  **Install Dependencies**:
    The required packages (`sqlalchemy`, `passlib[bcrypt]`, `python-jose[cryptography]`) have been added to `requirements.txt`.
    Run: `pip install -r requirements.txt`

2.  **Environment Variables**:
    Set `SECRET_KEY` in your `.env` file for JWT signing.
    ```
    SECRET_KEY=your_super_secret_key_here
    ```

## API Endpoints

- **POST `/auth/register`**: Register a new user.
  - Body: `{"email": "user@example.com", "password": "password", "full_name": "John Doe"}`
- **POST `/auth/token`**: Login to get an access token.
  - Body (Form Data): `username=user@example.com`, `password=password`
  - Returns: `{"access_token": "...", "token_type": "bearer"}`
- **GET `/auth/users/me`**: Get current user profile (Protected).
  - Header: `Authorization: Bearer <token>`

## Protecting Routes

To protect a route, use the `get_current_user` dependency:

```python
from fastapi import Depends
from auth.dependencies import get_current_user
from db.models import User

@router.get("/protected-route")
def protected_route(current_user: User = Depends(get_current_user)):
    return {"message": f"Hello {current_user.email}"}
```
