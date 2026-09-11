import logging
import os

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api import (
    appointments,
    auth,
    availability,
    availability_rules,
    customers,
    legal,
    services,
    staff_members,
    tenants,
    webhooks,
)
from app.rate_limit import limiter, rate_limit_exceeded_handler

# Uvicorn varsayilan olarak SADECE kendi ("uvicorn"/"uvicorn.access")
# logger'larini yapilandiriyor - "app.*" logger'lari (webhooks, notifications
# vb.) root logger'in varsayilan WARNING seviyesine dusup INFO satirlari
# (orn. MOCK SMS/EMAIL - bkz. app/notifications.py) hic gorunmez olurdu.
logging.basicConfig(level=logging.INFO)

app = FastAPI()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

CORS_ALLOW_ORIGIN = os.environ.get("CORS_ALLOW_ORIGIN", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ALLOW_ORIGIN],
    # httpOnly auth cookie'sinin cross-origin (frontend:3000 -> backend:8000)
    # istekleriyle gonderilip alinabilmesi icin gerekli. allow_credentials=True
    # ile birlikte allow_origins ASLA "*" olamaz (tarayici boyle bir yaniti
    # reddeder) - zaten tek, acik bir origin kullaniyoruz.
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(staff_members.router)
app.include_router(services.router)
app.include_router(availability_rules.router)
app.include_router(customers.router)
app.include_router(appointments.router)
app.include_router(legal.router)
app.include_router(availability.router)
app.include_router(tenants.router)
app.include_router(webhooks.router)

DATABASE_URL = os.environ["DATABASE_URL"]


@app.get("/health")
def health():
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        db_ok = True
    except Exception:
        db_ok = False

    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={"status": "ok" if db_ok else "error", "database": db_ok},
    )
