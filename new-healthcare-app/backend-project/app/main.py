import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers import assessments, business_rules, care_notes, care_plan, cases, custom_assessments, documents, notifications, patients, pgi, programs, question_library, results, reviews, staff, tasks
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Kidney-Cardiology Platform API", lifespan=lifespan)

# Without this, curl-based testing looks perfect (curl doesn't enforce CORS) while every
# request from the actual React dev server fails silently in the browser — this is
# specifically why it needs a real browser check, not just an API-level test, to catch.
# Local dev origins are always allowed; deployed origins (e.g. the Azure Static Web
# App's real URL) are added via CORS_ALLOWED_ORIGINS, a comma-separated env var — set
# it once the frontend has a real deployed URL, no code change or rebuild needed.
_default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_extra_origins = [o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(programs.router)
app.include_router(patients.router)
app.include_router(cases.router)
app.include_router(assessments.router)
app.include_router(results.router)
app.include_router(reviews.router)
app.include_router(question_library.router)
app.include_router(care_plan.router)
app.include_router(custom_assessments.router)
app.include_router(documents.router)
app.include_router(staff.router)
app.include_router(care_notes.router)
app.include_router(tasks.router)
app.include_router(pgi.router)
app.include_router(notifications.router)
app.include_router(business_rules.router)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}

