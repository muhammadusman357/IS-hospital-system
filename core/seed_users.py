from core.auth import create_user

def seed_users():
    users = [
        ("admin", "admin123", "admin"),
        ("Dr. Bob", "doc123", "doctor"),
        ("Alice_recep", "rec123", "receptionist"),
    ]

    for username, password, role in users:
        try:
            user = create_user(username, password, role)
            print(f"✅ Created: {user}")
        except Exception as e:
            print(f"⚠️ Could not create {username}: {e}")

if __name__ == "__main__":
    seed_users()
