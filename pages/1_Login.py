import streamlit as st
from core.auth import authenticate_user
from core.logger import log_action


# Initialize attempt counter
if "login_attempts" not in st.session_state:
    st.session_state["login_attempts"] = 0

# --------------------------
# GDPR Consent Banner
# --------------------------
if "gdpr_consent" not in st.session_state:
    st.session_state["gdpr_consent"] = False

# Show banner if consent not given
if not st.session_state["gdpr_consent"]:
    st.warning(
        "⚠️ This system handles patient data. You must consent to continue using the system in compliance with GDPR."
    )
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("I Consent"):
            st.session_state["gdpr_consent"] = True
            st.success("Thank you! You may continue.")
            # Clear query params and reload the page
            st.query_params = {}  # resets any query parameters
            st.stop()             # stop execution to refresh the page
    with col2:
        if st.button("Exit"):
            st.stop()
# Stop the login logic until consent is given
if not st.session_state["gdpr_consent"]:
    st.stop()


# Utility: perform logout (clear session and log)
def _perform_logout():
    user_info = st.session_state.get("user") or {
        "user_id": st.session_state.get("user_id"),
        "username": st.session_state.get("username"),
        "role": st.session_state.get("role"),
    }

    user_id = user_info.get("user_id")
    role = user_info.get("role")
    username = user_info.get("username")

    # Log logout (best-effort even if some fields are missing)
    log_action(
        user_id=user_id,
        role=role,
        action="logout",
        details=f"{username or 'Unknown'} logged out."
    )

    # Clear known session keys (support both `user` dict and flat keys)
    for k in ["user", "user_id", "username", "role"]:
        if k in st.session_state:
            del st.session_state[k]
    if "logged_in" in st.session_state:
        del st.session_state["logged_in"]

    # Remove query params and rerun to reflect logged-out state
    # Use the stable query-params API to avoid mixing experimental/prod APIs
        st.set_query_params()
    st.success("You have been logged out.")
    st.experimental_rerun()

# Support logout via `?action=logout` query parameter
# Use the stable query-params API to avoid mixing experimental/prod APIs
params = st.query_params
if params.get("action") == ["logout"]:
    _perform_logout()

# If user is already logged in → redirect directly (offer logout in sidebar)
if "user" in st.session_state or "username" in st.session_state:
    # Show logout affordance in sidebar for quick sign-out
    if st.sidebar.button("Logout"):
        _perform_logout()

    # determine role from either session layout
    if "user" in st.session_state:
        role = st.session_state["user"].get("role")
    else:
        role = st.session_state.get("role")

    if role == "admin":
        st.switch_page("pages/2_Dashboard_Admin.py")
    elif role == "doctor":
        st.switch_page("pages/3_Dashboard_Doctor.py")
    elif role == "receptionist":
        st.switch_page("pages/4_Dashboard_Receptionist.py")

st.title("🏥 Hospital Privacy & Access System — Login")

# --- Login Form ---
with st.form("login_form"):
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    submit = st.form_submit_button("Login")

if submit:
    user = authenticate_user(username, password)

    if user:
        # Reset attempts on successful login
        st.session_state["login_attempts"] = 0
        # Save login session (keep existing flat keys for compatibility)
        st.session_state["logged_in"] = True
        st.session_state["user_id"] = user["user_id"]
        st.session_state["username"] = user["username"]
        st.session_state["role"] = user["role"]
        # also set `user` dict for pages that expect it
        st.session_state["user"] = user

        # Log login event
        log_action(
            user_id=user["user_id"],
            role=user["role"],
            action="login",
            details=f"{user['username']} logged in."
        )

        # Redirect based on role
        if user["role"] == "admin":
            st.success("Logged in as Admin!")
            st.switch_page("pages/2_Dashboard_Admin.py")
        elif user["role"] == "doctor":
            st.success("Logged in as Doctor!")
            st.switch_page("pages/3_Dashboard_Doctor.py")
        elif user["role"] == "receptionist":
            st.success("Logged in as Receptionist!")
            st.switch_page("pages/4_Dashboard_Receptionist.py")

    else:
        # Increment attempts
        st.session_state["login_attempts"] += 1
        remaining = 3 - st.session_state["login_attempts"]
        if remaining > 0:
            st.error(f"Invalid username or password. Attempts left: {remaining}")
        else:
            st.error("Maximum login attempts reached! Redirecting...")
            st.session_state["login_attempts"] = 0  # reset counter
            st.switch_page("app.py")  # redirect to main app after 3 failed attempts
