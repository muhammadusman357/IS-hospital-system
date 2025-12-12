# core/auth.py
"""
Authentication + basic RBAC helpers for the Hospital System.

Uses:
- get_connection() from core.database
- log_action(...) from core.logger

Password storage format:
    iterations$salt_hex$hash_hex
(uses PBKDF2-HMAC-SHA256)
"""

import os
import hashlib
import binascii
import hmac
from typing import Optional, Dict
from core.database import get_connection
from core.logger import log_action
from datetime import datetime

# Hashing params
PBKDF2_ITERATIONS = 200_000
SALT_BYTES = 16

# Allowed roles for validation (project-defined)
ALLOWED_ROLES = {"admin", "doctor", "receptionist"}

# -------------------------
# Password helpers
# -------------------------
def _hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    """Return password storage string iterations$salt_hex$hash_hex."""
    salt = os.urandom(SALT_BYTES)
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return f"{iterations}${binascii.hexlify(salt).decode()}${binascii.hexlify(hash_bytes).decode()}"


def _verify_password(stored: str, provided_password: str) -> bool:
    """Verify a provided password against stored format iterations$salt$hash."""
    try:
        iterations_s, salt_hex, hash_hex = stored.split("$")
        iterations = int(iterations_s)
        salt = binascii.unhexlify(salt_hex)
        expected_hash = binascii.unhexlify(hash_hex)

        new_hash = hashlib.pbkdf2_hmac(
            "sha256", provided_password.encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(new_hash, expected_hash)
    except Exception:
        return False


# -------------------------
# DB user helpers
# -------------------------
def create_user(username: str, password: str, role: str) -> Dict:
    """
    Create a new user. Returns created user dict.
    Raises ValueError if role invalid or username exists.
    """
    role = role.lower().strip()
    if role not in ALLOWED_ROLES:
        raise ValueError(f"Invalid role '{role}'. Allowed roles: {ALLOWED_ROLES}")

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # check if username exists
        cur.execute("SELECT user_id FROM users WHERE username = ?;", (username,))
        if cur.fetchone():
            raise ValueError("Username already exists.")

        pwd_stored = _hash_password(password)

        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?);",
            (username, pwd_stored, role),
        )
        conn.commit()

        user_id = cur.lastrowid
        return {"user_id": user_id, "username": username, "role": role}

    finally:
        if conn:
            conn.close()


def get_user_by_username(username: str) -> Optional[Dict]:
    """Return user dict or None. user dict includes user_id, username, password (stored), role."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, username, password, role FROM users WHERE username = ?;",
            (username,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "user_id": row["user_id"],
            "username": row["username"],
            "password": row["password"],
            "role": row["role"],
        }
    finally:
        if conn:
            conn.close()


# -------------------------
# Authentication
# -------------------------
def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    Authenticate credentials.
    On success: logs login success and returns user dict (without removing password field).
    On failure: logs login failure and returns None.
    """
    user = get_user_by_username(username)
    if user and _verify_password(user["password"], password):
        # log success
        try:
            log_action(user["user_id"], user["role"], "login", f"{username} logged in")
        except Exception:
            # do not break authentication flow if logging fails
            pass
        return user
    else:
        # unknown user or wrong password: log failed attempt (user_id may be None)
        try:
            uid = user["user_id"] if user else None
            role = user["role"] if user else "unknown"
            log_action(uid, role, "login", f"LOGIN_FAILED username={username}")
        except Exception:
            pass
        return None


def change_password(user_id: int, new_password: str) -> bool:
    """Change password for a user_id. Returns True on success."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        pwd_stored = _hash_password(new_password)
        cur.execute("UPDATE users SET password = ? WHERE user_id = ?;", (pwd_stored, user_id))
        conn.commit()
        return cur.rowcount == 1
    except Exception:
        return False
    finally:
        if conn:
            conn.close()


# -------------------------
# RBAC helpers
# -------------------------
def has_role(user: Dict, required_role: str) -> bool:
    """Check if user (dict with 'role') has exact required_role."""
    if not user:
        return False
    return user.get("role", "").lower() == required_role.lower()


# -------------------------
# Streamlit decorator helper
# -------------------------
def require_role_streamlit(required_roles):
    """
    Streamlit decorator to guard functions/pages.
    Usage (in a Streamlit page):
        @require_role_streamlit(['admin'])
        def page_content():
            st.write("secret admin content")

    This decorator assumes Streamlit session_state has:
        - 'user_id'
        - 'username'
        - 'role'
    If not present or role not allowed, it will raise PermissionError.
    """
    if isinstance(required_roles, str):
        roles_set = {required_roles.lower()}
    else:
        roles_set = {r.lower() for r in required_roles}

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                import streamlit as st
            except Exception:
                raise RuntimeError("Streamlit is required for require_role_streamlit decorator")

            user = {
                "user_id": st.session_state.get("user_id"),
                "username": st.session_state.get("username"),
                "role": st.session_state.get("role"),
            }

            if not user["user_id"] or not user["role"]:
                # not logged in
                # log the unauthorized access attempt
                try:
                    log_action(None, "unknown", "login", "ACCESS_DENIED: not logged in")
                except Exception:
                    pass
                st.error("Not authenticated. Please log in.")
                st.stop()

            if user["role"].lower() not in roles_set:
                # log the unauthorized access attempt
                try:
                    log_action(user["user_id"], user["role"], "view", "ACCESS_DENIED: insufficient role")
                except Exception:
                    pass
                st.error("You do not have permission to view this page.")
                st.stop()

            return func(*args, **kwargs)

        return wrapper

    return decorator
