from functools import wraps

from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required

dashboard = Blueprint("dashboard", __name__)


def role_required(role):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped_view(*args, **kwargs):
            if current_user.role != role:
                abort(403)

            return view(*args, **kwargs)

        return wrapped_view

    return decorator


@dashboard.route("/doctor/dashboard")
@role_required("doctor")
def doctor_dashboard():
    return render_template("doctor_dashboard.html")


@dashboard.route("/receptionist/dashboard")
@role_required("receptionist")
def receptionist_dashboard():
    return render_template("receptionist_dashboard.html")
