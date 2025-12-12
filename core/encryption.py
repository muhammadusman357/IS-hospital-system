# core/encryption.py

from cryptography.fernet import Fernet
import re
import hashlib
import os
from pathlib import Path
from dotenv import load_dotenv, set_key, dotenv_values

# --------------------------
# Load .env
# --------------------------
ENV_FILE = Path(".env")
load_dotenv(dotenv_path=ENV_FILE)

def load_or_create_fernet_key():
    """Load FERNET_KEY from .env or create one if it doesn't exist."""
    env_key = os.getenv("FERNET_KEY")
    if env_key:
        return env_key.encode() if isinstance(env_key, str) else env_key

    # Generate a new key
    key = Fernet.generate_key()

    # Save to .env file
    try:
        if not ENV_FILE.exists():
            ENV_FILE.touch()
        env_content = dotenv_values(ENV_FILE)
        if "FERNET_KEY" not in env_content:
            set_key(str(ENV_FILE), "FERNET_KEY", key.decode())
    except Exception as e:
        print(f"⚠️ Failed to save FERNET_KEY to .env: {e}")

    return key

# --------------------------
# Fernet setup
# --------------------------
FERNET_KEY = load_or_create_fernet_key()
fernet = Fernet(FERNET_KEY)


# -------------- Encryption / Decryption --------------

def encrypt_data(plaintext: str) -> str:
    """Encrypt plaintext string and return base64 encoded ciphertext."""
    if plaintext is None:
        return None
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_data(ciphertext: str) -> str:
    """Decrypt base64 encoded ciphertext to plaintext."""
    if ciphertext is None:
        return None
    return fernet.decrypt(ciphertext.encode()).decode()


# -------------- Masking / Anonymization --------------

def mask_name(name: str) -> str:
    """
    Masks name by replacing it with a pseudo id like 'ANON_1021'.
    Here we hash the name and take last 4 hex digits as an ID.
    """
    if not name:
        return ""
    h = hashlib.sha256(name.encode()).hexdigest()
    anon_id = h[-4:]
    return f"ANON_{anon_id}"


def mask_contact(contact: str) -> str:
    """
    Masks contact by replacing digits except the last 4 with 'X'.
    Example: '0321-1234567' -> 'XXX-XXX-4567'
    """
    if not contact:
        return ""
    # Extract last 4 digits
    digits = re.findall(r"\d", contact)
    last4 = "".join(digits[-4:]) if len(digits) >= 4 else "".join(digits)
    # Replace digits except last 4 with X
    # We do this by replacing digits in the string except last 4 positions
    # A simple way is to mask all digits except the last 4 digits (from right)
    
    masked_chars = []
    digit_count = 0
    for ch in reversed(contact):
        if ch.isdigit():
            digit_count += 1
            if digit_count <= 4:
                masked_chars.append(ch)
            else:
                masked_chars.append('X')
        else:
            masked_chars.append(ch)
    masked = ''.join(reversed(masked_chars))
    return masked


# -------------- Anonymize full patient record --------------

def anonymize_patient_record(patient_record: dict) -> dict:
    """
    Given a patient record dict with keys: 'name', 'contact', 'diagnosis',
    returns a dict with anonymized_name, anonymized_contact, and encrypted_diagnosis.
    """
    name = patient_record.get("name", "")
    contact = patient_record.get("contact", "")
    diagnosis = patient_record.get("diagnosis", "")

    anonymized_name = mask_name(name)
    anonymized_contact = mask_contact(contact)

    # Encrypt diagnosis for reversible anonymization bonus
    encrypted_diagnosis = encrypt_data(diagnosis) if diagnosis else ""

    return {
        "anonymized_name": anonymized_name,
        "anonymized_contact": anonymized_contact,
        "encrypted_diagnosis": encrypted_diagnosis,
    }
