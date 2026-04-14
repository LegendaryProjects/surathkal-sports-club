from flask import redirect, render_template, session
from functools import wraps


def apology(message, code=400):
    return render_template("apology.html", code=code, message=message), code


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function
