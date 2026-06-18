from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.services.appointment_service import (
    create_walk_in_appointment,
    get_appointments_by_status,
    update_appointment_status,
)
from app.services.clinic_status_service import (
    get_current_clinic_status,
    update_clinic_status,
)
from app.services.doctor_service import (
    get_current_patient_details,
    get_search_results,
    get_today_stats,
    get_upcoming_queue,
    save_consultation_notes,
)
from app.services.notification_service import get_notification_stats
from app.services.queue_service import (
    complete_current_consultation,
    get_queue_summary,
    start_next_consultation,
)

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
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    queue = get_queue_summary()
    clinic_status = get_current_clinic_status()
    return render_template(
        "doctor_dashboard.html",
        queue=queue,
        clinic_status=clinic_status,
        current_patient_details=get_current_patient_details(queue["current_patient"]),
        stats=get_today_stats(),
        upcoming_queue=get_upcoming_queue(),
        search=search,
        status_filter=status_filter,
        search_results=get_search_results(search, status_filter),
    )


@dashboard.route("/doctor/clinic-status/<status_value>", methods=["POST"])
@role_required("doctor")
def set_clinic_status(status_value):
    try:
        clinic_status = update_clinic_status(status_value, current_user.id)
    except ValueError:
        abort(400)

    flash(f"Clinic status updated to {clinic_status.status}.")
    return redirect(url_for("dashboard.doctor_dashboard"))


@dashboard.route("/doctor/queue")
@role_required("doctor")
def doctor_queue():
    queue = get_queue_summary()
    return render_template("doctor_queue.html", queue=queue)


@dashboard.route("/doctor/queue/start", methods=["POST"])
@role_required("doctor")
def start_consultation():
    patient, message = start_next_consultation()
    flash(message)
    return redirect(url_for("dashboard.doctor_dashboard"))


@dashboard.route("/doctor/queue/complete", methods=["POST"])
@role_required("doctor")
def complete_consultation():
    notes = request.form.get("consultation_notes")
    patient, message = complete_current_consultation(notes)
    flash(message)
    return redirect(url_for("dashboard.doctor_dashboard"))


@dashboard.route("/doctor/appointments/<int:appointment_id>/notes", methods=["POST"])
@role_required("doctor")
def save_notes(appointment_id):
    appointment = save_consultation_notes(
        appointment_id,
        request.form.get("consultation_notes", ""),
    )
    flash(f"Notes saved for {appointment.patient_name}.")
    return redirect(url_for("dashboard.doctor_dashboard"))


@dashboard.route("/receptionist/dashboard")
@role_required("receptionist")
def receptionist_dashboard():
    appointments = get_appointments_by_status()
    queue = get_queue_summary()
    notifications = get_notification_stats()
    clinic_status = get_current_clinic_status()
    return render_template(
        "receptionist_dashboard.html",
        appointments=appointments,
        queue=queue,
        notifications=notifications,
        clinic_status=clinic_status,
    )


@dashboard.route("/receptionist/appointments")
@role_required("receptionist")
def manage_appointments():
    appointments = get_appointments_by_status()
    return render_template("manage_appointments.html", appointments=appointments)


@dashboard.route("/receptionist/queue")
@role_required("receptionist")
def receptionist_queue():
    queue = get_queue_summary()
    return render_template("receptionist_queue.html", queue=queue)


@dashboard.route("/receptionist/appointments/<int:appointment_id>/approve", methods=["POST"])
@role_required("receptionist")
def approve_appointment(appointment_id):
    appointment = update_appointment_status(appointment_id, "approved")
    flash(f"{appointment.patient_name}'s appointment has been approved.")
    return redirect(url_for("dashboard.manage_appointments"))


@dashboard.route("/receptionist/appointments/<int:appointment_id>/reject", methods=["POST"])
@role_required("receptionist")
def reject_appointment(appointment_id):
    appointment = update_appointment_status(appointment_id, "rejected")
    flash(f"{appointment.patient_name}'s appointment has been rejected.")
    return redirect(url_for("dashboard.manage_appointments"))


@dashboard.route("/receptionist/walk-in", methods=["GET", "POST"])
@role_required("receptionist")
def add_walk_in():
    if request.method == "POST":
        errors, appointment = create_walk_in_appointment(request.form)

        if errors:
            for error in errors:
                flash(error)
            return render_template("add_walk_in.html", form=request.form)

        flash(f"Walk-in patient {appointment.patient_name} has been added and approved.")
        return redirect(url_for("dashboard.manage_appointments"))

    return render_template("add_walk_in.html")
