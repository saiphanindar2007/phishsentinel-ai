"""
PhishSentinel AI — Database Setup
-------------------------------------
SQLite by default (zero setup). Set DATABASE_URL to Postgres for real
traffic — SQLAlchemy keeps every query portable.

Tables:
  verdicts   every analysis result
  feedback   analyst/user corrections (feeds retraining)
  list_entries  organisation allow/deny lists
  audit_log  who did what (list edits, purges, model reloads, exports)

`init_db()` creates missing tables and then `ensure_indexes()` adds the
indexes the dashboard's queries rely on. Both are idempotent, so they're
safe on a database created by an older version of the app.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

_is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if _is_sqlite else {}
engine_kwargs = {"connect_args": connect_args}
if not _is_sqlite:
    # Survive dropped connections and bound the pool under load.
    engine_kwargs.update(pool_pre_ping=True, pool_size=10, max_overflow=10, pool_recycle=1800)
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class VerdictRecord(Base):
    __tablename__ = "verdicts"

    verdict_id = Column(String, primary_key=True, index=True)
    input_type = Column(String)          # "url" | "email" | "batch"
    raw_input = Column(Text)             # original URL or email summary (truncated)
    verdict = Column(String)             # "safe" | "suspicious" | "phishing"
    confidence = Column(Float)
    url_score = Column(Float)
    nlp_score = Column(Float)
    visual_score = Column(Float)
    reputation_score = Column(Float)
    explanation = Column(Text)
    extra_json = Column(Text, nullable=True)   # confidence_detail/counterfactual/evidence_graph/storyline
    created_at = Column(DateTime, default=datetime.utcnow)


class FeedbackRecord(Base):
    __tablename__ = "feedback"

    id = Column(String, primary_key=True, index=True)
    verdict_id = Column(String, index=True)
    is_correct = Column(Boolean)
    actual_label = Column(String, nullable=True)
    source = Column(String, default="web")  # "web" | "extension" | "api"
    created_at = Column(DateTime, default=datetime.utcnow)


class ReviewQueueRecord(Base):
    """Verdicts an analyst (or an automatic low-confidence rule) has
    flagged for a second pair of eyes — the 'Analyst Feedback with Review
    Queue' feature. Separate from FeedbackRecord: feedback is a one-shot
    correction, this is a workflow with a pending/resolved lifecycle."""
    __tablename__ = "review_queue"

    id = Column(String, primary_key=True, index=True)
    verdict_id = Column(String, index=True, nullable=False)
    status = Column(String, default="pending", index=True)   # pending | upheld | overturned
    flagged_note = Column(String, nullable=True)
    flagged_source = Column(String, default="web")
    resolved_note = Column(String, nullable=True)
    actual_label = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)


class ListEntry(Base):
    __tablename__ = "list_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    kind = Column(String, nullable=False)       # "allow" | "deny"
    domain = Column(String, nullable=False, index=True)
    note = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditRecord(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    actor = Column(String)            # hashed key label, e.g. "key:3f9a1c2b"
    action = Column(String, index=True)
    detail = Column(Text)
    ip = Column(String)
    request_id = Column(String)


_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_verdicts_created_at ON verdicts (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_verdicts_verdict ON verdicts (verdict)",
    "CREATE INDEX IF NOT EXISTS ix_verdicts_type_created ON verdicts (input_type, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_feedback_created_at ON feedback (created_at)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_list_kind_domain ON list_entries (kind, domain)",
    "CREATE INDEX IF NOT EXISTS ix_review_status_created ON review_queue (status, created_at)",
]


def ensure_indexes() -> None:
    with engine.begin() as conn:
        for stmt in _INDEXES:
            conn.execute(text(stmt))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_indexes()


def check_db() -> bool:
    """Cheap liveness probe used by /health/ready."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
