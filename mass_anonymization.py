"""mass_anonymization.py

Provides a utility to run a bulk anonymization pass over the `patients` table.
This module exposes `anonymize_all_patients(user_id, role)` for use by the admin
dashboard. It updates anonymized fields and re-encrypts diagnosis where needed.
"""

from core.database import get_connection
from core.encryption import anonymize_patient_record
from core.logger import log_action


def anonymize_all_patients(user_id=None, role="admin"):
    """
    Iterate all patients and ensure anonymized_name and anonymized_contact are set
    and diagnosis is stored in encrypted form. Returns the number of rows updated.
    Logs the action via core.logger.log_action.
    """
    conn = None
    updated_count = 0
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT patient_id, name, contact, diagnosis FROM patients")
        records = cursor.fetchall()

        for row in records:
            # sqlite3.Row -> access by key
            pid = row["patient_id"]
            name = row["name"] or ""
            contact = row["contact"] or ""
            diagnosis = row["diagnosis"] or ""

            anon = anonymize_patient_record({
                "name": name,
                "contact": contact,
                "diagnosis": diagnosis,
            })

            cursor.execute(
                """
                UPDATE patients
                SET anonymized_name = ?, anonymized_contact = ?, diagnosis = ?
                WHERE patient_id = ?
                """,
                (anon["anonymized_name"], anon["anonymized_contact"], anon["encrypted_diagnosis"], pid),
            )

            if cursor.rowcount:
                updated_count += 1

        conn.commit()

        # Log action
        try:
            log_action(user_id, role, "anonymization", f"Mass anonymization ran; {updated_count} rows updated")
        except Exception:
            pass

        return updated_count

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    # Run anonymization as a script for convenience
    print("Running mass anonymization...")
    updated = anonymize_all_patients(user_id=None, role="system")
    print(f"Updated {updated} patient records.")