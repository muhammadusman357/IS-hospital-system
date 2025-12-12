import streamlit as st
import pandas as pd
import os
from pathlib import Path
import shutil
from datetime import datetime, timedelta
from core.validators import validate_patient_input
from core.validators import validate_name, validate_contact, validate_diagnosis
from core.gdpr import load_gdpr_settings, save_gdpr_settings, run_data_retention
from core.auth import require_role_streamlit
from core.database import (
    get_connection,
    get_all_patients,
    get_patient_by_id,
    update_patient,
    delete_patient,
    get_all_users,
)
from core.logger import log_action
from core.encryption import (
    decrypt_data,
    anonymize_patient_record
)
from mass_anonymization import anonymize_all_patients

import shutil
from dotenv import load_dotenv
load_dotenv()

# Protect this page → Only Admin can access
@require_role_streamlit("admin")
def admin_page():

    # Sidebar logout button
    if st.sidebar.button("Logout"):
        # Clear all session variables
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        
        st.switch_page("pages/1_Login.py")
        st.rerun()

    st.title("🏥 Admin Dashboard")

    # ==========================
    # SUB-NAVIGATION BAR
    # ==========================
    # Initialize session state for selected tab
    if "admin_tab" not in st.session_state:
        st.session_state.admin_tab = "Patient Records"

    # Create sub-navigation tabs
    
    tabs = st.tabs([
        "📋 Patient Records", 
        "🛡 Mass Anonymization", 
        "📜 Audit Logs",
        "🕒 Data Retention Policy",
        "💾 Data Backup and Recovery"
    ])


    # ==========================
    # Helper Functions
    # ==========================
    def load_patients():
        rows = get_all_patients()  # returns list of sqlite3.Row
        df = pd.DataFrame([dict(row) for row in rows])  # convert rows to dicts first
        return df

    
    def load_users():
        rows = get_all_users()  # returns list of sqlite3.Row
        df = pd.DataFrame([dict(row) for row in rows])  # convert rows to dicts first
        return df


    # ==========================
    # TAB 1: PATIENT RECORDS
    # ==========================
    with tabs[0]:

        st.header("📋 Patient Records (Raw + Anonymized Fields)")

        # -----------------------------------------------
        # Load all patients
        # -----------------------------------------------
        patients_df = load_patients()

        # -----------------------------------------------
        # Heading + Add Button
        # -----------------------------------------------
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader("Patient Records")
        with col2:
            if st.button("➕ Add New Patient"):
                st.session_state["show_add_form"] = True

        st.dataframe(patients_df)

        # -----------------------------------------------
        # Download anonymized CSV
        # -----------------------------------------------
        try:
            anon_df = patients_df[["patient_id", "anonymized_name", "anonymized_contact", "date_added"]]
        except Exception:
            anon_df = pd.DataFrame()

        st.download_button(
            "⬇️ Download Anonymized Patients CSV",
            data=anon_df.to_csv(index=False),
            file_name="anonymized_patients.csv",
            mime="text/csv"
        )

        # =========================================================
        # ADD NEW PATIENT FORM
        # =========================================================
        if st.session_state.get("show_add_form", False):
            st.subheader("➕ Add New Patient")

            with st.form("add_patient_form"):
                name = st.text_input("Patient Name")
                contact = st.text_input("Contact Number")
                diagnosis = st.text_area("Diagnosis (will be encrypted)")
                
                colA, colB = st.columns(2)
                with colA:
                    submit_add = st.form_submit_button("Save Patient")
                with colB:
                    cancel_add = st.form_submit_button("Cancel")

            if cancel_add:
                st.session_state["show_add_form"] = False
                st.info("Add patient cancelled.")
                st.rerun()

            if submit_add:
                # --- VALIDATION ---
                errors = validate_patient_input(name, contact, diagnosis)
                if errors:
                    for e in errors:
                        st.error("❌ " + e)
                    st.stop()
            

                anonymized = anonymize_patient_record({
                    "name": name,
                    "contact": contact,
                    "diagnosis": diagnosis
                })

                conn = get_connection()
                cursor = conn.cursor()
                date_added = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                cursor.execute("""
                    INSERT INTO patients
                    (name, contact, diagnosis, anonymized_name, anonymized_contact, date_added)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    name,
                    contact,
                    anonymized["encrypted_diagnosis"],
                    anonymized["anonymized_name"],
                    anonymized["anonymized_contact"],
                    date_added
                ))

                conn.commit()
                conn.close()

                log_action(
                    user_id=st.session_state["user_id"],
                    role="admin",
                    action="add",
                    details=f"Added patient {name}"
                )

                st.success("Patient added successfully.")
                st.session_state["show_add_form"] = False
                st.rerun()

        # =========================================================
        # ROW ACTIONS — UPDATE / DELETE / DECRYPT DIAGNOSIS
        # =========================================================
        st.subheader("✏️ Update / Delete / Decrypt Diagnosis")

        if len(patients_df) == 0:
            st.info("No patients available.")
            st.stop()

        selected_id = st.selectbox("Select Patient ID", patients_df["patient_id"].tolist())

        colA, colB, colC = st.columns(3)

        # -----------------------------------------------
        # Decrypt Diagnosis
        # -----------------------------------------------
        with colA:
            if st.button("🔐 Decrypt Diagnosis"):
                encrypted = patients_df.loc[
                    patients_df.patient_id == selected_id, "diagnosis"
                ].values[0]

                decrypted = decrypt_data(encrypted)
                st.info(f"Diagnosis: **{decrypted}**")

                log_action(
                    st.session_state["user_id"],
                    "admin",
                    "view",
                    f"Decrypted diagnosis for patient {selected_id}"
                )

        # -----------------------------------------------
        # Update Button
        # -----------------------------------------------
        with colB:
            if st.button("✏️ Update Patient"):
                st.session_state["update_id"] = selected_id

        # -----------------------------------------------
        # Delete Button
        # -----------------------------------------------
        with colC:
            if st.button("❌ Delete Patient"):
                deleted = delete_patient(selected_id)
                if deleted:
                    log_action(
                        st.session_state["user_id"],
                        "admin",
                        "delete",
                        f"Deleted patient {selected_id}"
                    )
                    st.success("Patient deleted.")
                    st.session_state.pop("update_id", None)
                    st.rerun()
                else:
                    st.error("Failed to delete patient")

        # =========================================================
        # UPDATE PATIENT FORM (Individual Field Validation)
        # =========================================================
        if st.session_state.get("update_id", None):
            pid = st.session_state["update_id"]

            patient = get_patient_by_id(pid)

            # ---- SAFETY: patient may no longer exist ---------
            if patient is None:
                st.error("⚠️ Patient no longer exists (possibly deleted).")
                st.session_state.pop("update_id", None)
                st.rerun()

            # -----------------------------------------------
            # SAFE ACCESS TO sqlite3.Row VALUES
            # -----------------------------------------------
            current_name = patient["name"] if patient["name"] is not None else ""
            current_contact = patient["contact"] if patient["contact"] is not None else ""

            enc_diag = patient["diagnosis"]
            current_diag = decrypt_data(enc_diag) if enc_diag else ""

            st.subheader(f"Update Patient #{pid}")

            with st.form("update_form"):
                new_name = st.text_input("Name", value=current_name)
                new_contact = st.text_input("Contact", value=current_contact)
                new_diagnosis = st.text_area("Diagnosis", value=current_diag)

                col1, col2 = st.columns(2)
                with col1:
                    save_update = st.form_submit_button("Save Changes")
                with col2:
                    cancel_update = st.form_submit_button("Cancel")

            if cancel_update:
                st.session_state.pop("update_id", None)
                st.info("Update cancelled.")
                st.rerun()

            if save_update:
                updated_fields = {}
                # -----------------------------
                # Validate Name if changed
                # -----------------------------
                if new_name != current_name:
                    errors = validate_name(new_name)
                    if errors:
                        for e in errors:
                            st.error("❌ " + e)
                        st.stop()
                    updated_fields["name"] = new_name

                # -----------------------------
                # Validate Contact if changed
                # -----------------------------
                if new_contact != current_contact:
                    errors = validate_contact(new_contact)
                    if errors:
                        for e in errors:
                            st.error("❌ " + e)
                        st.stop()
                    updated_fields["contact"] = new_contact

                # -----------------------------
                # Validate Diagnosis if changed
                # -----------------------------
                if new_diagnosis != current_diag:
                    errors = validate_diagnosis(new_diagnosis)
                    if errors:
                        for e in errors:
                            st.error("❌ " + e)
                        st.stop()
                    updated_fields["diagnosis"] = new_diagnosis

                if not updated_fields:
                    st.info("No changes detected.")
                    st.stop()

                # --- Anonymize & Encrypt only updated fields ---
                anon_input = {
                    "name": updated_fields.get("name", current_name),
                    "contact": updated_fields.get("contact", current_contact),
                    "diagnosis": updated_fields.get("diagnosis", current_diag)
                }
                anon = anonymize_patient_record(anon_input)

                # --- Update in DB ---
                update_patient(
                    pid,
                    updated_fields.get("name", current_name),
                    updated_fields.get("contact", current_contact),
                    anon["encrypted_diagnosis"],
                    anon["anonymized_name"],
                    anon["anonymized_contact"],
                )

                # --- Logging ---
                log_action(
                    st.session_state["user_id"],
                    "admin",
                    "update",
                    f"Updated patient {pid}"
                )

                st.success("Patient updated successfully.")

                # Clear update state
                st.session_state.pop("update_id", None)

                # Rerun UI
                st.rerun()





    # ==========================
    # TAB 2: MASS ANONYMIZATION
    # ==========================
    with tabs[1]:
        st.subheader("🛡 Mass Anonymization")
        st.write("Run mass anonymization (encrypt diagnoses & mask PII)")
        st.info("This operation will update all patient records with anonymized name/contact and re-encrypt diagnosis.")
        
        confirm_anon = st.checkbox("I confirm that I want to anonymize all patient records")
        
        if st.button("🔒 Mask All Names & Contacts", disabled=not confirm_anon, use_container_width=True):
            try:
                updated = anonymize_all_patients(user_id=st.session_state.get("user_id"), role="admin")
                st.success(f"✅ Mass anonymization completed — {updated} records updated.")
                st.balloons()
            except Exception as e:
                st.error(f"❌ Mass anonymization failed: {e}")

    # ==========================
    # TAB 3: AUDIT LOGS WITH VISUALIZATIONS
    # ==========================
    with tabs[2]:
        st.subheader("📜 Audit Logs & Activity Analytics")
        
        conn = get_connection()
        logs_df = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp DESC", conn)
        conn.close()

        if logs_df.empty:
            st.info("No audit logs available.")
        else:
            # =========================================================
            # REAL-TIME ACTIVITY GRAPHS
            # =========================================================
            st.markdown("### 📊 Activity Analytics")
            
            # Prepare data for visualization
            logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp'])
            logs_df['date'] = logs_df['timestamp'].dt.date
            logs_df['hour'] = logs_df['timestamp'].dt.hour
            
            # Row 1: Key Metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_actions = len(logs_df)
                st.metric("Total Actions", total_actions)
            
            with col2:
                unique_users = logs_df['user_id'].nunique()
                st.metric("Active Users", unique_users)
            
            with col3:
                # Actions today
                today = datetime.now().date()
                actions_today = len(logs_df[logs_df['date'] == today])
                st.metric("Actions Today", actions_today)
            
            with col4:
                # Most common action
                if len(logs_df) > 0:
                    most_common = logs_df['action'].mode()[0]
                    st.metric("Most Common Action", most_common)
            
            st.divider()
            
            # =========================================================
            # Chart 1: User Actions Per Day (Line Chart)
            # =========================================================
            st.markdown("#### 📈 User Actions Per Day")
            
            # Group by date and count actions
            actions_per_day = logs_df.groupby('date').size().reset_index(name='actions')
            actions_per_day['date'] = pd.to_datetime(actions_per_day['date'])
            
            # Fill missing dates with 0
            if len(actions_per_day) > 0:
                date_range = pd.date_range(
                    start=actions_per_day['date'].min(),
                    end=datetime.now().date(),
                    freq='D'
                )
                full_range = pd.DataFrame({'date': date_range})
                actions_per_day = full_range.merge(actions_per_day, on='date', how='left').fillna(0)
                
                st.line_chart(actions_per_day.set_index('date')['actions'])
            else:
                st.info("No data available for this chart.")
            
            # =========================================================
            # Chart 2: Actions by Type (Bar Chart)
            # =========================================================
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.markdown("#### 📊 Actions by Type")
                action_counts = logs_df['action'].value_counts().reset_index()
                action_counts.columns = ['action', 'count']
                st.bar_chart(action_counts.set_index('action')['count'])
            
            # =========================================================
            # Chart 3: Actions by Role (Bar Chart)
            # =========================================================
            with col_chart2:
                st.markdown("#### 👥 Actions by Role")
                role_counts = logs_df['role'].value_counts().reset_index()
                role_counts.columns = ['role', 'count']
                st.bar_chart(role_counts.set_index('role')['count'])
            
            # =========================================================
            # Chart 4: Hourly Activity Heatmap
            # =========================================================
            st.markdown("#### 🕐 Hourly Activity Distribution")
            
            hourly_activity = logs_df.groupby('hour').size().reset_index(name='actions')
            # Ensure all 24 hours are present
            all_hours = pd.DataFrame({'hour': range(24)})
            hourly_activity = all_hours.merge(hourly_activity, on='hour', how='left').fillna(0)
            
            st.bar_chart(hourly_activity.set_index('hour')['actions'])
            
            # =========================================================
            # Chart 5: Recent Activity Timeline (Last 7 Days)
            # =========================================================
            st.markdown("#### 📅 Recent Activity (Last 7 Days)")
            
            last_7_days = datetime.now().date() - timedelta(days=7)
            recent_logs = logs_df[logs_df['date'] >= last_7_days]
            
            if len(recent_logs) > 0:
                recent_activity = recent_logs.groupby(['date', 'action']).size().reset_index(name='count')
                recent_pivot = recent_activity.pivot(index='date', columns='action', values='count').fillna(0)
                st.bar_chart(recent_pivot)
            else:
                st.info("No activity in the last 7 days.")
            
            st.divider()
            
            # =========================================================
            # AUDIT LOGS TABLE
            # =========================================================
            st.markdown("### 📋 Detailed Audit Logs")
            
            # Filters
            col_filter1, col_filter2, col_filter3 = st.columns(3)
            
            with col_filter1:
                filter_action = st.multiselect(
                    "Filter by Action",
                    options=logs_df['action'].unique(),
                    default=None
                )
            
            with col_filter2:
                filter_role = st.multiselect(
                    "Filter by Role",
                    options=logs_df['role'].unique(),
                    default=None
                )
            
            with col_filter3:
                filter_days = st.selectbox(
                    "Show logs from",
                    options=["All Time", "Last 24 Hours", "Last 7 Days", "Last 30 Days"],
                    index=0
                )
            
            # Apply filters
            filtered_logs = logs_df.copy()
            
            if filter_action:
                filtered_logs = filtered_logs[filtered_logs['action'].isin(filter_action)]
            
            if filter_role:
                filtered_logs = filtered_logs[filtered_logs['role'].isin(filter_role)]
            
            if filter_days == "Last 24 Hours":
                cutoff = datetime.now() - timedelta(hours=24)
                filtered_logs = filtered_logs[filtered_logs['timestamp'] >= cutoff]
            elif filter_days == "Last 7 Days":
                cutoff = datetime.now() - timedelta(days=7)
                filtered_logs = filtered_logs[filtered_logs['timestamp'] >= cutoff]
            elif filter_days == "Last 30 Days":
                cutoff = datetime.now() - timedelta(days=30)
                filtered_logs = filtered_logs[filtered_logs['timestamp'] >= cutoff]
            
            # Display filtered logs
            st.dataframe(
                filtered_logs[['log_id', 'user_id', 'role', 'action', 'timestamp', 'details']],
                use_container_width=True
            )
            
            # Download button
            st.download_button(
                "⬇️ Download Logs as CSV",
                data=filtered_logs.to_csv(index=False),
                file_name=f"audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    # ==========================
    # TAB 4: DATA RETENTION
    # ==========================
    with tabs[3]:
        st.subheader("🕒 GDPR: Data Retention Policy")

        settings = load_gdpr_settings()
        retention_days = settings["retention_days"]
        last_run = settings.get("last_run", "Never")
        last_deleted = settings.get("last_deleted_count", 0)
        total_deleted = settings.get("total_deleted_count", 0)

        st.info(f"Current retention period: **{retention_days} days (~{retention_days//365} years)**")
        st.write(f"Last GDPR cleanup run: {last_run}")
        st.write(f"Deleted in last run: {last_deleted}")
        st.write(f"Total deleted records: {total_deleted}")

        # Allow admin to change retention period
        new_retention = st.number_input(
            "Change Retention Period (days)",
            min_value=30,
            max_value=3650,
            value=retention_days,
            step=30
        )
        if st.button("💾 Save Retention Policy"):
            settings["retention_days"] = new_retention
            save_gdpr_settings(settings)
            st.success(f"Retention period updated to {new_retention} days.")

        # Manual run of retention
        if st.button("🗑 Run Data Retention Now"):
            deleted_now, total_deleted, period = run_data_retention(user_id=st.session_state.get("user_id"), role="admin")
            st.success(f"✅ Data Retention executed: {deleted_now} records deleted now, total deleted: {total_deleted}")


    # ==========================
    # TAB 5: DATA BACKUP & EXPORT
    # ==========================
    with tabs[4]:
        st.subheader("💾 Data Backup & Export Options")

        BACKUP_FOLDER = Path(os.getenv("BACKUP_FOLDER", "data/backup"))
        DB_PATH = Path(os.getenv("DB_PATH", "data/hospital.db"))
        DB_BACKUP_FOLDER = BACKUP_FOLDER / "db"
        DB_BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)

        # ============================================================================
        # DATABASE BACKUP & RECOVERY SECTION
        # ============================================================================
        st.markdown("---")
        st.markdown("### 🗄️ Database Backup & Recovery")
        
        db_col1, db_col2 = st.columns(2)

        # ---------- BACKUP DATABASE ----------
        with db_col1:
            st.markdown("#### 🔒 Create Backup")
            if st.button("📦 Backup Database Now", use_container_width=True, type="primary"):
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = DB_BACKUP_FOLDER / f"hospital_backup_{timestamp}.db"
                    shutil.copy(DB_PATH, backup_path)
                    st.success(f"✅ Database backed up successfully!")
                    st.info(f"📍 Location: `{backup_path}`")
                except Exception as e:
                    st.error(f"❌ Backup failed: {e}")

        # ---------- RESTORE DATABASE ----------
        with db_col2:
            st.markdown("#### 🔄 Restore from Backup")
            
            # Get available backups
            backups = sorted(
                DB_BACKUP_FOLDER.glob("hospital_backup_*.db"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            if backups:
                backup_options = {b.name: b for b in backups}
                selected_backup_name = st.selectbox(
                    "Select backup to restore:",
                    list(backup_options.keys()),
                    help="Most recent backups appear first"
                )
                
                if st.button("⚠️ Restore Selected Backup", use_container_width=True, type="secondary"):
                    try:
                        selected_backup_path = backup_options[selected_backup_name]
                        
                        # Create pre-restore safety backup
                        pre_backup_path = DB_BACKUP_FOLDER / f"hospital_pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                        shutil.copy(DB_PATH, pre_backup_path)
                        
                        # Restore selected backup
                        shutil.copy(selected_backup_path, DB_PATH)
                        
                        st.success(f"✅ Database restored from: `{selected_backup_name}`")
                        st.info(f"🛡️ Safety backup created: `{pre_backup_path.name}`")
                        st.warning("⚠️ Please refresh the app to see restored data")
                    except Exception as e:
                        st.error(f"❌ Restore failed: {e}")
            else:
                st.info("📭 No backups available yet. Create your first backup above!")

        # ============================================================================
        # CSV EXPORT SECTION
        # ============================================================================
        st.markdown("---")
        st.markdown("### 📊 CSV Export Options")
        
        PATIENTS_CSV_FOLDER = BACKUP_FOLDER / "csv" / "patients"
        USERS_CSV_FOLDER = BACKUP_FOLDER / "csv" / "users"
        PATIENTS_CSV_FOLDER.mkdir(parents=True, exist_ok=True)
        USERS_CSV_FOLDER.mkdir(parents=True, exist_ok=True)

        csv_col1, csv_col2, csv_col3 = st.columns(3)

        # ---------- EXPORT PATIENTS ----------
        with csv_col1:
            if st.button("👥 Export Patients", use_container_width=True):
                try:
                    patients_df = load_patients()
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    csv_path = PATIENTS_CSV_FOLDER / f"patients_{timestamp}.csv"
                    patients_df.to_csv(csv_path, index=False)
                    st.success(f"✅ Exported {len(patients_df)} patients")
                    st.info(f"📍 `{csv_path.name}`")
                except Exception as e:
                    st.error(f"❌ Export failed: {e}")

        # ---------- EXPORT USERS ----------
        with csv_col2:
            if st.button("🔐 Export Users", use_container_width=True):
                try:
                    users_df = load_users()
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    csv_path = USERS_CSV_FOLDER / f"users_{timestamp}.csv"
                    users_df.to_csv(csv_path, index=False)
                    st.success(f"✅ Exported {len(users_df)} users")
                    st.info(f"📍 `{csv_path.name}`")
                except Exception as e:
                    st.error(f"❌ Export failed: {e}")

        # ---------- EXPORT ALL DATA ----------
        with csv_col3:
            if st.button("📦 Export All Data", use_container_width=True):
                try:
                    patients_df = load_patients()
                    users_df = load_users()
                    
                    # Combine into one CSV with headers
                    csv_data = (
                        "# PATIENTS DATA\n" + 
                        patients_df.to_csv(index=False) +
                        "\n\n# USERS DATA\n" + 
                        users_df.to_csv(index=False)
                    )
                    
                    st.download_button(
                        label="⬇️ Download Combined CSV",
                        data=csv_data,
                        file_name=f"all_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                    st.success("✅ Ready for download!")
                except Exception as e:
                    st.error(f"❌ Export failed: {e}")



    # Footer: show System Uptime + DB last-modified time
    try:
        db = Path(os.getenv("DB_PATH", "data/hospital.db"))  # load from env if available
        if db.exists():
            uptime = datetime.now() - st.session_state["app_start_time"]
            uptime_str = str(uptime).split(".")[0]  # remove microseconds
            db_last_mod = datetime.fromtimestamp(db.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            st.caption(f"🕒 System Uptime: {uptime_str} | 💾 DB Last Modified: {db_last_mod}")
    except Exception:
        pass



# Run the page function
admin_page()