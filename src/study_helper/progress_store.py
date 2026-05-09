"""Local JSON persistence for learning progress."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError


def default_progress_path() -> Path:
    return Path.home() / ".developer-study-helper" / "progress.json"


class TopicEntry(BaseModel):
    name: str
    sessions: int = 0
    last_touched: str | None = None
    notes: str = ""


class ProgressFile(BaseModel):
    topics: dict[str, TopicEntry] = Field(default_factory=dict)
    interview_sessions: int = 0
    resume_reviews: int = 0
    activity_dates: list[str] = Field(default_factory=list)


def load_progress(path: Path) -> ProgressFile:
    if not path.exists():
        return ProgressFile()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return ProgressFile()
    if "streak_dates" in raw and "activity_dates" not in raw:
        raw["activity_dates"] = raw.pop("streak_dates")
    try:
        return ProgressFile.model_validate(raw)
    except ValidationError:
        return ProgressFile()


def save_progress(path: Path, state: ProgressFile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")


def _touch_today(state: ProgressFile) -> None:
    today = date.today().isoformat()
    dates = sorted(set(state.activity_dates + [today]))
    state.activity_dates = dates[-365:]


def record_topic(path: Path, topic: str, note: str | None = None) -> ProgressFile:
    state = load_progress(path)
    key = topic.strip().lower()
    if not key:
        return state
    now = datetime.now().isoformat(timespec="seconds")
    if key in state.topics:
        t = state.topics[key]
        t.sessions += 1
        t.last_touched = now
        if note:
            t.notes = (t.notes + "\n" + note).strip() if t.notes else note
    else:
        state.topics[key] = TopicEntry(
            name=topic.strip(),
            sessions=1,
            last_touched=now,
            notes=note or "",
        )
    _touch_today(state)
    save_progress(path, state)
    return state


def record_interview_session(path: Path) -> ProgressFile:
    state = load_progress(path)
    state.interview_sessions += 1
    _touch_today(state)
    save_progress(path, state)
    return state


def record_resume_review(path: Path) -> ProgressFile:
    state = load_progress(path)
    state.resume_reviews += 1
    _touch_today(state)
    save_progress(path, state)
    return state


def streak_count(state: ProgressFile) -> int:
    today = date.today().isoformat()
    dates = set(state.activity_dates)
    n = 0
    cur = date.fromisoformat(today)
    while cur.isoformat() in dates:
        n += 1
        cur -= timedelta(days=1)
    return n


def summary_dict(state: ProgressFile) -> dict[str, Any]:
    return {
        "streak_days": streak_count(state),
        "topics": {k: v.model_dump() for k, v in state.topics.items()},
        "interview_sessions": state.interview_sessions,
        "resume_reviews": state.resume_reviews,
        "activity_days_logged": len(state.activity_dates),
    }
