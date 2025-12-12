import streamlit as st
from core.gdpr import run_data_retention

from datetime import datetime

if "app_start_time" not in st.session_state:
    st.session_state["app_start_time"] = datetime.now()


# ---------------------------
# Automatic GDPR Data Retention
# ---------------------------
deleted_now, total_deleted, retention_days = run_data_retention(user_id=None, role="system")

if deleted_now > 0:
    st.warning(f"⚠️ GDPR: {deleted_now} old patient records older than {retention_days} days were automatically deleted. Total deleted: {total_deleted}")

# Configure the app with the requested title/icon
st.set_page_config(
    page_title="🏥 Hospital Privacy & Access System",
    page_icon="🏥",
    layout="wide"
)

# Landing page: show a simple intro and a button to go to Login.
st.title("🏥 Hospital Privacy & Access System")
st.write("Welcome — please sign in to continue.")

# Center the button using columns
col1, col2, col3 = st.columns([1, 3, 1])
with col1:
    if st.button("🔐 Login"):
        st.switch_page("pages/1_Login.py")

st.markdown("---")
