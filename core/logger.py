# core/logger.py

from datetime import datetime
from core.database import get_connection

# Expanded set of allowed actions to cover CRUD, export, anonymization, and misc events
VALID_ACTIONS = {
    "login",
    "logout",
    "add",
    "update",
    "delete",
    "view",
    "anonymize",
    "anonymization",
    "export",
    "backup",
    "decrypt",
    "read",
    "gdpr_delete",
    "other",
}


def log_action(user_id: int, role: str, action: str, details: str = ""):
    """
    Logs a user action into the logs table.

    - Normalizes `action` to a known set; unknown actions are recorded as 'other'.
    - Does not raise on logging failures; prints an error for diagnostics.

    Stored fields: user_id, role, action, timestamp, details
    """

    action = (action or "").lower().strip()
    if action not in VALID_ACTIONS:
        action = "other"

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO logs (user_id, role, action, timestamp, details)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                user_id,
                role,
                action,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                details,
            ),
        )

        conn.commit()

    except Exception as e:
        # Non-fatal: logging should not break application flow
        print(f"[LOGGER ERROR] Could not record log: {e}")

    finally:
        if conn:
            conn.close()
