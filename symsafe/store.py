"""
store.py — SQLite-based data persistence for SymSafe sessions and exchanges.

Manages a SQLite database that stores session records, individual exchanges
with dual-layer risk classification data, synonym proposals for classifier
improvement, and rule proposals for escalation pattern detection. Provides
the structured data layer that enables clinician review, feedback capture,
and system improvement over time.
"""

import json
import sqlite3
from pathlib import Path

from symsafe.config import DB_PATH


def _get_connection(db_path=None):
    """Create a SQLite connection with foreign key enforcement enabled.

    Args:
        db_path: Path to the database file. Defaults to the configured DB_PATH.

    Returns:
        sqlite3.Connection: An open database connection with row_factory set
        to sqlite3.Row for dict-like access.
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=None):
    """Create the database and all tables if they do not already exist.

    Creates the data/ directory if needed. Safe to call multiple times
    (idempotent). Tables created: sessions, exchanges, synonym_proposals,
    rule_proposals.

    Args:
        db_path: Path to the database file. Defaults to the configured DB_PATH.
    """
    path = db_path or DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = _get_connection(path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT,
                intake_answers TEXT,
                highest_risk TEXT,
                highest_care_level TEXT,
                message_count INTEGER,
                session_symptoms TEXT,
                status TEXT DEFAULT 'pending_review',
                reviewer_notes TEXT,
                zip_code TEXT
            );

            CREATE TABLE IF NOT EXISTS exchanges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                exchange_index INTEGER,
                user_input TEXT,
                assistant_response TEXT,
                local_risk_level TEXT,
                local_risk_flags TEXT,
                gpt_risk_level TEXT,
                gpt_risk_flags TEXT,
                merged_risk_level TEXT,
                care_level TEXT,
                follow_up_questions TEXT,
                evaluation TEXT,
                tree_matches TEXT,
                review_status TEXT DEFAULT 'pending',
                corrected_risk_level TEXT,
                corrected_care_level TEXT,
                review_reason TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS synonym_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_phrase TEXT,
                gpt_risk_level TEXT,
                local_risk_level TEXT,
                proposed_category TEXT,
                proposed_synonym_for TEXT,
                session_id TEXT,
                status TEXT DEFAULT 'pending',
                reviewed_by TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS rule_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_type TEXT,
                description TEXT,
                supporting_evidence TEXT,
                proposed_rule TEXT,
                status TEXT DEFAULT 'pending',
                reviewed_by TEXT,
                created_at TEXT
            );
        """)
        conn.commit()
    finally:
        conn.close()


def save_session(session_id, intake_answers, highest_risk, highest_care_level,
                 message_count, session_symptoms, zip_code=None, db_path=None):
    """Insert a session record into the database.

    Args:
        session_id: Unique session identifier (timestamp string, e.g. "20260324_154700").
        intake_answers: Dict of intake questionnaire answers, or None.
        highest_risk: Highest risk tier reached ("HIGH", "MODERATE", or "LOW").
        highest_care_level: Highest care level reached (e.g. "emergency").
        message_count: Total number of patient messages in the session.
        session_symptoms: List of symptom strings collected during the session.
        zip_code: Optional patient zip code for future care routing.
        db_path: Path to the database file. Defaults to the configured DB_PATH.
    """
    import datetime

    conn = _get_connection(db_path)
    try:
        conn.execute(
            """INSERT INTO sessions
               (id, created_at, intake_answers, highest_risk, highest_care_level,
                message_count, session_symptoms, zip_code)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                datetime.datetime.now().isoformat(),
                json.dumps(intake_answers) if intake_answers is not None else None,
                highest_risk,
                highest_care_level,
                message_count,
                json.dumps(session_symptoms),
                zip_code,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def save_exchange(session_id, exchange_index, user_input, assistant_response,
                  local_risk_level, local_risk_flags, gpt_risk_level,
                  gpt_risk_flags, merged_risk_level, care_level,
                  follow_up_questions, evaluation, tree_matches, db_path=None):
    """Insert an exchange record into the database.

    Args:
        session_id: The parent session's ID.
        exchange_index: Zero-based position of this exchange within the session.
        user_input: The patient's message text.
        assistant_response: The assistant's reply text.
        local_risk_level: Risk level from the local keyword classifier.
        local_risk_flags: List of matched local risk flags.
        gpt_risk_level: Risk level from GPT's assessment.
        gpt_risk_flags: List of risk flags identified by GPT.
        merged_risk_level: Final merged risk level string.
        care_level: Final care level string.
        follow_up_questions: List of follow-up question strings.
        evaluation: AI self-evaluation text, or None.
        tree_matches: List of matched symptom tree keys.
        db_path: Path to the database file. Defaults to the configured DB_PATH.
    """
    conn = _get_connection(db_path)
    try:
        conn.execute(
            """INSERT INTO exchanges
               (session_id, exchange_index, user_input, assistant_response,
                local_risk_level, local_risk_flags, gpt_risk_level, gpt_risk_flags,
                merged_risk_level, care_level, follow_up_questions, evaluation,
                tree_matches)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                exchange_index,
                user_input,
                assistant_response,
                local_risk_level,
                json.dumps(local_risk_flags),
                gpt_risk_level,
                json.dumps(gpt_risk_flags),
                merged_risk_level,
                care_level,
                json.dumps(follow_up_questions),
                evaluation,
                json.dumps(tree_matches),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_session(session_id, highest_risk, highest_care_level,
                    message_count, session_symptoms, zip_code=None, db_path=None):
    """Update an existing session record's fields.

    Args:
        session_id: The session ID to update.
        highest_risk: Highest risk tier reached.
        highest_care_level: Highest care level reached.
        message_count: Total number of patient messages.
        session_symptoms: List of symptom strings.
        zip_code: Optional patient zip code.
        db_path: Path to the database file. Defaults to the configured DB_PATH.
    """
    conn = _get_connection(db_path)
    try:
        conn.execute(
            """UPDATE sessions
               SET highest_risk = ?, highest_care_level = ?,
                   message_count = ?, session_symptoms = ?, zip_code = ?
               WHERE id = ?""",
            (
                highest_risk,
                highest_care_level,
                message_count,
                json.dumps(session_symptoms),
                zip_code,
                session_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_session(session_id, db_path=None):
    """Retrieve a single session record by ID.

    Args:
        session_id: The session ID to look up.
        db_path: Path to the database file. Defaults to the configured DB_PATH.

    Returns:
        A dict with all session fields (JSON fields parsed), or None if not found.
    """
    conn = _get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_session_dict(row)
    finally:
        conn.close()


def get_all_sessions(status=None, db_path=None):
    """Retrieve all session records, optionally filtered by review status.

    Args:
        status: If provided, only return sessions with this status
                (e.g. "pending_review", "reviewed", "flagged").
        db_path: Path to the database file. Defaults to the configured DB_PATH.

    Returns:
        A list of session dicts ordered by created_at descending.
    """
    conn = _get_connection(db_path)
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_session_dict(r) for r in rows]
    finally:
        conn.close()


def get_exchanges(session_id, db_path=None):
    """Retrieve all exchange records for a given session.

    Args:
        session_id: The session ID whose exchanges to retrieve.
        db_path: Path to the database file. Defaults to the configured DB_PATH.

    Returns:
        A list of exchange dicts ordered by exchange_index ascending.
        JSON fields are returned parsed.
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM exchanges WHERE session_id = ? ORDER BY exchange_index ASC",
            (session_id,),
        ).fetchall()
        return [_row_to_exchange_dict(r) for r in rows]
    finally:
        conn.close()


def update_session_status(session_id, status, reviewer_notes=None, db_path=None):
    """Update the review status (and optional notes) for a session.

    Args:
        session_id: The session ID to update.
        status: New status value ("pending_review", "reviewed", or "flagged").
        reviewer_notes: Optional clinician notes to attach.
        db_path: Path to the database file. Defaults to the configured DB_PATH.
    """
    conn = _get_connection(db_path)
    try:
        conn.execute(
            "UPDATE sessions SET status = ?, reviewer_notes = ? WHERE id = ?",
            (status, reviewer_notes, session_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_exchange_review(exchange_id, review_status, corrected_risk_level=None,
                           corrected_care_level=None, review_reason=None,
                           db_path=None):
    """Update the review status and optional corrections for an exchange.

    Args:
        exchange_id: The exchange's auto-incremented ID.
        review_status: New review status ("pending", "accepted", "corrected", "rejected").
        corrected_risk_level: Clinician's corrected risk level, if any.
        corrected_care_level: Clinician's corrected care level, if any.
        review_reason: Explanation for why the clinician corrected or rejected.
        db_path: Path to the database file. Defaults to the configured DB_PATH.
    """
    conn = _get_connection(db_path)
    try:
        conn.execute(
            """UPDATE exchanges
               SET review_status = ?, corrected_risk_level = ?,
                   corrected_care_level = ?, review_reason = ?
               WHERE id = ?""",
            (review_status, corrected_risk_level, corrected_care_level,
             review_reason, exchange_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_session_stats(db_path=None):
    """Return aggregate statistics about all sessions.

    Args:
        db_path: Path to the database file. Defaults to the configured DB_PATH.

    Returns:
        A dict with keys: total_sessions, high_risk_count, pending_count,
        reviewed_count.
    """
    conn = _get_connection(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        high = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE highest_risk = 'HIGH'"
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE status = 'pending_review'"
        ).fetchone()[0]
        reviewed = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE status = 'reviewed'"
        ).fetchone()[0]
        return {
            "total_sessions": total,
            "high_risk_count": high,
            "pending_count": pending,
            "reviewed_count": reviewed,
        }
    finally:
        conn.close()


def get_synonym_proposals_for_session(session_id, db_path=None):
    """Return synonym proposals filtered by session_id.

    Args:
        session_id: The session ID to filter by.
        db_path: Path to the database file. Defaults to the configured DB_PATH.

    Returns:
        A list of dicts representing synonym proposals for this session.
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM synonym_proposals WHERE session_id = ?",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _row_to_session_dict(row):
    """Convert a sqlite3.Row from sessions into a plain dict with parsed JSON.

    Args:
        row: A sqlite3.Row object from the sessions table.

    Returns:
        A dict with all session fields. JSON string fields (intake_answers,
        session_symptoms) are parsed back into Python objects.
    """
    d = dict(row)
    if d.get("intake_answers") is not None:
        d["intake_answers"] = json.loads(d["intake_answers"])
    if d.get("session_symptoms") is not None:
        d["session_symptoms"] = json.loads(d["session_symptoms"])
    return d


def _row_to_exchange_dict(row):
    """Convert a sqlite3.Row from exchanges into a plain dict with parsed JSON.

    Args:
        row: A sqlite3.Row object from the exchanges table.

    Returns:
        A dict with all exchange fields. JSON string fields (local_risk_flags,
        gpt_risk_flags, follow_up_questions, tree_matches) are parsed back
        into Python objects.
    """
    d = dict(row)
    for field in ("local_risk_flags", "gpt_risk_flags", "follow_up_questions", "tree_matches"):
        if d.get(field) is not None:
            d[field] = json.loads(d[field])
    return d
