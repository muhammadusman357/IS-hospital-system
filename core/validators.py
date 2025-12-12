# core/validators.py

def validate_name(name):
    errors = []
    if not name or name.strip() == "":
        errors.append("Name cannot be empty.")
    elif len(name) < 3:
        errors.append("Name must be at least 3 characters.")
    elif any(char.isdigit() for char in name):
        errors.append("Name cannot contain numbers.")
    return errors


def validate_contact(contact):
    errors = []

    if not contact or contact.strip() == "":
        errors.append("Contact number cannot be empty.")
        return errors

    # Optional leading +
    digits = contact[1:] if contact.startswith("+") else contact

    if not digits.isdigit():
        errors.append("Contact number must contain digits only (0–9).")

    if len(digits) < 7 or len(digits) > 15:
        errors.append("Contact number must be between 7 and 15 digits.")

    return errors


def validate_diagnosis(diagnosis):
    errors = []
    if not diagnosis or diagnosis.strip() == "":
        errors.append("Diagnosis cannot be empty.")
    elif len(diagnosis) < 5:
        errors.append("Diagnosis must be at least 5 characters long.")
    return errors


def validate_patient_input(name, contact, diagnosis):
    """
    Combines all validation functions
    Returns a single list of errors
    """
    errors = []
    errors += validate_name(name)
    errors += validate_contact(contact)
    errors += validate_diagnosis(diagnosis)
    return errors
