"""Create (or fetch) the local demo auth user used for history persistence.

The app's tables FK to auth.users, and auth is not wired into the UI yet, so
local runs need one real Supabase user to own the rows. This uses the Admin
API with the service-role key (never the anon key).

Usage (from backend/):  python -m scripts.create_demo_user
Prints the UUID to put in .env as DEMO_USER_ID (safe to run repeatedly).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
except ImportError:
    pass

EMAIL = os.getenv("DEMO_EMAIL", "demo@careerpilot.local")
PASSWORD = os.getenv("DEMO_PASSWORD", "CareerPilot-demo-2026")


def main() -> int:
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing in .env")
        return 1
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    with httpx.Client(timeout=30) as client:
        existing = None
        page = 1
        while page <= 10 and existing is None:
            r = client.get(f"{url}/auth/v1/admin/users",
                           params={"page": page, "per_page": 100}, headers=headers)
            r.raise_for_status()
            users = r.json().get("users", [])
            if not users:
                break
            existing = next((u for u in users if u.get("email") == EMAIL), None)
            page += 1

        if existing:
            uid = existing["id"]
            print(f"exists: {EMAIL} -> {uid}")
        else:
            r = client.post(f"{url}/auth/v1/admin/users", headers=headers,
                            json={"email": EMAIL, "password": PASSWORD,
                                  "email_confirm": True})
            r.raise_for_status()
            uid = r.json()["id"]
            print(f"created: {EMAIL} -> {uid}")
    print(f"\nAdd to .env:\nDEMO_USER_ID={uid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
