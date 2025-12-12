import streamlit as st
import pandas as pd

from core.auth import require_role_streamlit
from core.database import get_connection
from core.logger import log_action
from core.encryption import decrypt_data

@require_role_streamlit("doctor")
def doctor_page():
    # Sidebar logout button
    if st.sidebar.button("Logout"):

        # Clear all session variables
        for key in list(st.session_state.keys()):
            del st.session_state[key]

        st.switch_page("pages/1_Login.py")
        st.rerun()

    st.title("👨‍⚕️ Doctor Dashboard")

    def load_anonymized_patients():
        conn = get_connection()
        query = """
        SELECT patient_id, anonymized_name, anonymized_contact, diagnosis, date_added
        FROM patients
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    patients_df = load_anonymized_patients()

    st.subheader("📋 Patient Records (Anonymized)")

    # Decrypt diagnosis for display in the dataframe
    def decrypt_diagnosis_column(row):
        try:
            return decrypt_data(row["diagnosis"])
        except Exception:
            return "[Decryption error]"

    patients_df["diagnosis_decrypted"] = patients_df.apply(decrypt_diagnosis_column, axis=1)

    # Display anonymized data + decrypted diagnosis
    display_df = patients_df[[
        "patient_id",
        "anonymized_name",
        "anonymized_contact",
        "diagnosis_decrypted",
        "date_added"
    ]].rename(columns={
        "anonymized_name": "Name (Anonymized)",
        "anonymized_contact": "Contact (Anonymized)",
        "diagnosis_decrypted": "Diagnosis"
    })

    st.dataframe(display_df)

    # Log the view action
    if "user_id" in st.session_state and "role" in st.session_state:
        log_action(
            user_id=st.session_state["user_id"],
            role=st.session_state["role"],
            action="view",
            details="Doctor viewed anonymized patient data"
        )

    # Footer: show DB last-modified time for availability awareness
    try:
        from pathlib import Path
        from datetime import datetime
        db = Path("data/hospital.db")
        if db.exists():
            st.caption(f"DB last modified: {datetime.fromtimestamp(db.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception:
        pass

doctor_page()
