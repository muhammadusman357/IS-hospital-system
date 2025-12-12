import os
import sqlite3
from pathlib import Path
import datetime
from datetime import datetime, timedelta
from dotenv import load_dotenv

DB_PATH = os.getenv("DB_PATH", "data/hospital.db")  # fallback if not set in .env


def get_connection():
    """Return a SQLite connection with row access by column name."""
    print("Connected to: ",DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    """Create all required tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # --------------------- Users Table ---------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    );
    """)

    # --------------------- Patients Table ---------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        contact TEXT,
        diagnosis TEXT,
        anonymized_name TEXT,
        anonymized_contact TEXT,
        date_added TEXT NOT NULL
    );
    """)

    # --------------------- Logs Table ---------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        role TEXT,
        action TEXT,
        timestamp TEXT,
        details TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """)

    conn.commit()
    conn.close()

def initialize_database():
    """Run full initialization."""
    # Ensure /data folder exists
    DB_PATH.parent.mkdir(exist_ok=True)

    create_tables()
    print("Database initialized successfully.")


def get_all_patients():
    """Return all patients as list of sqlite3.Row objects."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients ORDER BY patient_id ASC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_users():
    """Return all patients as list of sqlite3.Row objects."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY user_id ASC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_patient_by_id(patient_id: int):
    """Return a single patient row by id or None."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def update_patient(patient_id: int, name: str, contact: str, encrypted_diagnosis: str, anonymized_name: str, anonymized_contact: str):
    """Update patient record fields. Returns number of affected rows."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE patients
        SET name = ?, contact = ?, diagnosis = ?, anonymized_name = ?, anonymized_contact = ?
        WHERE patient_id = ?
        """,
        (name, contact, encrypted_diagnosis, anonymized_name, anonymized_contact, patient_id)
    )
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected


def delete_patient(patient_id: int):
    """Delete a patient by id. Returns number of deleted rows."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return deleted

# --------------------------
# GDPR: Delete/Anonymize old data
# --------------------------
def gdpr_data_retention(retention_days=1825):  # default ~5 years
    """
    Delete or anonymize patient records older than retention_days.
    """
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    # Delete old patients
    cursor.execute("DELETE FROM patients WHERE date_added <= ?", (cutoff_str,))
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_count



if __name__ == "__main__":
    initialize_database()
