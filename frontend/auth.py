import bcrypt

# PRE-GENERATED HASHES (DO NOT CHANGE EACH RUN)
USERS = {
    "admin": {
        "password_hash": bcrypt.hashpw(b"admin123", bcrypt.gensalt()),
        "role": "admin",
        "display_name": "Admin",
    },
    "reviewer": {
        "password_hash": bcrypt.hashpw(b"review123", bcrypt.gensalt()),
        "role": "reviewer",
        "display_name": "Data Reviewer",
    },
}


def verify_login(username: str, password: str):
    user = USERS.get(username.lower().strip())

    if not user:
        return False, None, None

    if bcrypt.checkpw(password.encode(), user["password_hash"]):
        return True, user["role"], user["display_name"]

    return False, None, None