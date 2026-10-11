"""Create or promote an admin user.

Usage:
    python -m scripts.create_admin --email admin@example.com --username admin --password ChangeMe123!
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.auth.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User, UserPreference


async def main(email: str, username: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()
        if user:
            user.is_admin = True
            print(f"Promoted existing user {email} to admin.")
        else:
            user = User(
                email=email.lower(),
                username=username,
                hashed_password=hash_password(password),
                is_admin=True,
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            await db.flush()
            db.add(UserPreference(user_id=user.id))
            print(f"Created admin {email}.")
        await db.commit()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    args = p.parse_args()
    asyncio.run(main(args.email, args.username, args.password))
