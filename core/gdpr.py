import json
from datetime import datetime, timedelta
from core.database import get_connection
from core.logger import log_action  # import logger

GDPR_FILE = "data/gdpr_settings.json"

# Load GDPR settings
def load_gdpr_settings():
    try:
        with open(GDPR_FILE, "r") as f:
            settings = json.load(f)
    except FileNotFoundError:
        settings = {
            "retention_days": 1825,  # 5 years
            "last_deleted_count": 0,
            "total_deleted_count": 0,
            "last_run": None
        }
        save_gdpr_settings(settings)
    return settings

def save_gdpr_settings(settings):
    with open(GDPR_FILE, "w") as f:
        json.dump(settings, f, indent=4)

# Run GDPR Data Retention
def run_data_retention(user_id=None, role="system"):
    
    settings = load_gdpr_settings()
    retention_days = settings["retention_days"]
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")

    # Delete old patients
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM patients WHERE date_added <= ?", (cutoff_str,))
    deleted_now = cursor.rowcount
    conn.commit()
    conn.close()

    # Update GDPR settings
    settings["last_deleted_count"] = deleted_now
    settings["total_deleted_count"] = settings.get("total_deleted_count", 0) + deleted_now
    settings["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_gdpr_settings(settings)

    # Log action in audit logs
    # Log action in audit logs
    if deleted_now > 0:
        log_action(
            user_id=user_id,  # Use user_id or "system"
            role=role if role is not None else "system",           # Use role or "system"
            action="gdpr_delete",
            details=f"Deleted {deleted_now} patient records older than {retention_days} days."
        )


    return deleted_now, settings["total_deleted_count"], retention_days
