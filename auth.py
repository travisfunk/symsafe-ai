import json
from functools import wraps
from flask import session, redirect, url_for, flash

USER_FILE = "users.json"

def load_users():
    with open(USER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def authenticate_user(username, password):
    users = load_users()
    user = users.get(username)
    if user and user.get("password") == password:
        return {"username": username, "roles": user["roles"]}
    return None

def require_roles(*required_roles):
    def wrapper(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            user = session.get("user")
            if not user:
                flash("Please log in.")
                return redirect(url_for("login"))
            if not any(role in user["roles"] for role in required_roles):
                flash("Access denied.")
                return redirect(url_for("home"))
            return fn(*args, **kwargs)
        return decorated
    return wrapper

def current_user():
    return session.get("user")

def has_role(role):
    user = session.get("user")
    return user and role in user.get("roles", [])
