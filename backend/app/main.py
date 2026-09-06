import os

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    appointments,
    auth,
    availability,
    availability_rules,
    customers,
    services,
    staff_members,
    tenants,
    webhooks,
)

app = FastAPI()

CORS_ALLOW_ORIGIN = os.environ.get("CORS_ALLOW_ORIGIN", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ALLOW_ORIGIN],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(staff_members.router)
app.include_router(services.router)
app.include_router(availability_rules.router)
app.include_router(customers.router)
app.include_router(appointments.router)
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
