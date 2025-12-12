import streamlit as st
from core.auth import require_role_streamlit
from core.database import get_connection
from core.logger import log_action
from core.encryption import anonymize_patient_record
from core.validators import validate_name, validate_contact, validate_diagnosis


@require_role_streamlit("receptionist")
def receptionist_page():
    # Sidebar logout button
    if st.sidebar.button("Logout"):

        # Clear all session variables
        for key in list(st.session_state.keys()):
            del st.session_state[key]

        st.switch_page("pages/1_Login.py")
        st.rerun()


    st.title("📋 Receptionist Dashboard")
    st.write("Welcome! You can add or edit patient records. Sensitive data is hidden for privacy.")

    # ======================================================
    # ADD NEW PATIENT
    # ======================================================
    st.subheader("➕ Add New Patient")

    name = st.text_input("Patient Name")
    contact = st.text_input("Contact Number")
    diagnosis = st.text_area("Diagnosis")

    if st.button("Add Patient"):

        # -----------------------
        # VALIDATION
        # -----------------------
        from core.validators import validate_patient_input

        errors = validate_patient_input(name, contact, diagnosis)
        if errors:
            for e in errors:
                st.error("❌ " + e)
            st.stop()   # stop execution, don't add invalid data

        # -----------------------
        # ANONYMIZATION + SAVE
        # -----------------------
        anon = anonymize_patient_record({
            "name": name,
            "contact": contact,
            "diagnosis": diagnosis
        })

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO patients (name, contact, diagnosis,
                                anonymized_name, anonymized_contact,
                                date_added)
            VALUES (?, ?, ?, ?, ?, DATE('now'))
        """, (name, contact, anon["encrypted_diagnosis"],
            anon["anonymized_name"], anon["anonymized_contact"]))

        conn.commit()
        conn.close()

        log_action(
            st.session_state["user_id"],
            "receptionist",
            "add",
            f"Added patient: {anon['anonymized_name']}"
        )

        st.success("Patient added successfully! (Sensitive data hidden)")
        st.rerun()


    st.markdown("---")

    # ======================================================
    # VIEW PATIENTS (ANONYMIZED ONLY)
    # ======================================================
    st.subheader("👁 View & Edit Patients (Anonymized Only)")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT patient_id, anonymized_name, anonymized_contact, date_added
        FROM patients
        ORDER BY patient_id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        st.info("No patients found.")
        return

    for pid, anon_name, anon_contact, date_added in rows:
        with st.expander(f"Patient #{pid} - {anon_name}"):

            st.write(f"**Masked Contact:** {anon_contact}")
            st.write(f"**Date Added:** {date_added}")

            # ===============================
            # EDIT FORM (Sensitive data hidden)
            # ===============================
            st.write("### ✏ Edit Patient")

            new_name = st.text_input(f"New Name for Patient #{pid}", key=f"name_{pid}")
            new_contact = st.text_input(f"New Contact for Patient #{pid}", key=f"contact_{pid}")
            new_diagnosis = st.text_area(f"New Diagnosis", key=f"diag_{pid}")

            if st.button(f"Save Changes for {pid}", key=f"save_{pid}"):
                updated_fields = {}

                # Validate Name if changed
                if new_name.strip() and new_name != anon_name:
                    errors = validate_name(new_name)
                    if errors:
                        for e in errors:
                            st.error("❌ " + e)
                        st.stop()
                    updated_fields["name"] = new_name

                # Validate Contact if changed
                if new_contact.strip() and new_contact != anon_contact:
                    errors = validate_contact(new_contact)
                    if errors:
                        for e in errors:
                            st.error("❌ " + e)
                        st.stop()
                    updated_fields["contact"] = new_contact

                # Validate Diagnosis if changed
                if new_diagnosis.strip():
                    errors = validate_diagnosis(new_diagnosis)
                    if errors:
                        for e in errors:
                            st.error("❌ " + e)
                        st.stop()
                    updated_fields["diagnosis"] = new_diagnosis

                # If nothing changed
                if not updated_fields:
                    st.info("No changes detected.")
                    st.stop()

                # --- Anonymize only changed fields ---
                anon_input = {
                    "name": updated_fields.get("name", anon_name),
                    "contact": updated_fields.get("contact", anon_contact),
                    "diagnosis": updated_fields.get("diagnosis", "")  # empty string if not changed
                }
                anon = anonymize_patient_record(anon_input)

                # --- Build dynamic SQL ---
                set_clauses = []
                params = []

                if "name" in updated_fields:
                    set_clauses.append("name = ?")
                    params.append(updated_fields["name"])
                    set_clauses.append("anonymized_name = ?")
                    params.append(anon["anonymized_name"])

                if "contact" in updated_fields:
                    set_clauses.append("contact = ?")
                    params.append(updated_fields["contact"])
                    set_clauses.append("anonymized_contact = ?")
                    params.append(anon["anonymized_contact"])

                if "diagnosis" in updated_fields:
                    set_clauses.append("diagnosis = ?")
                    params.append(anon["encrypted_diagnosis"])

                params.append(pid)
                sql = f"UPDATE patients SET {', '.join(set_clauses)} WHERE patient_id = ?"

                # --- Execute update ---
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(sql, params)
                conn.commit()
                conn.close()

                log_action(
                    st.session_state["user_id"],
                    "receptionist",
                    "update",
                    f"Edited patient #{pid} ({anon['anonymized_name']})"
                )

                st.success("Patient updated successfully.")
                st.rerun()




    # Log view action at end
    log_action(
        st.session_state["user_id"],
        "receptionist",
        "view",
        "Viewed patient list"
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

receptionist_page()
