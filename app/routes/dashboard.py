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
from app.services.prescription_service import create_or_update_prescription
from app.services.queue_service import (
    complete_current_consultation,
    get_queue_summary,
    start_next_consultation,
)
from app.models.slot import Slot

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
    from flask_login import current_user
    slots = (
        Slot.query
        .filter((Slot.doctor_id == current_user.id))
        .order_by(Slot.slot_date.asc(), Slot.slot_time.asc())
        .limit(50)
        .all()
    )
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
        slots=slots,
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


@dashboard.route("/doctor/slots", methods=["POST"])
@role_required("doctor")
def add_slot():
    from datetime import datetime

    date_raw = request.form.get("slot_date", "").strip()
    time_raw = request.form.get("slot_time", "").strip()

    if not date_raw or not time_raw:
        flash("Date and time are required to create a slot.")
        return redirect(url_for("dashboard.doctor_dashboard"))

    try:
        slot_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
        slot_time = datetime.strptime(time_raw, "%H:%M").time()
    except ValueError:
        flash("Invalid date or time format.")
        return redirect(url_for("dashboard.doctor_dashboard"))

    from flask_login import current_user

    slot = Slot(slot_date=slot_date, slot_time=slot_time, status="available", doctor_id=current_user.id)
    db.session.add(slot)
    db.session.commit()
    flash("Slot created")
    return redirect(url_for("dashboard.doctor_dashboard"))


@dashboard.route("/doctor/slots/<int:slot_id>/toggle", methods=["POST"])
@role_required("doctor")
def toggle_slot(slot_id):
    slot = db.session.get(Slot, slot_id)
    if not slot:
        flash("Slot not found")
        return redirect(url_for("dashboard.doctor_dashboard"))

    slot.status = "disabled" if slot.status == "available" else "available"
    db.session.commit()
    flash("Slot updated")
    return redirect(url_for("dashboard.doctor_dashboard"))


@dashboard.route("/doctor/slots/<int:slot_id>/delete", methods=["POST"])
@role_required("doctor")
def delete_slot(slot_id):
    slot = db.session.get(Slot, slot_id)
    if not slot:
        flash("Slot not found")
        return redirect(url_for("dashboard.doctor_dashboard"))

    db.session.delete(slot)
    db.session.commit()
    flash("Slot deleted")
    return redirect(url_for("dashboard.doctor_dashboard"))


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


@dashboard.route("/doctor/appointments/<int:appointment_id>/prescription", methods=["POST"])
@role_required("doctor")
def generate_prescription(appointment_id):
    try:
        errors, prescription = create_or_update_prescription(
            appointment_id,
            request.form,
            current_user.name,
        )
    except ValueError as error:
        flash(str(error))
        return redirect(url_for("dashboard.doctor_dashboard"))

    if errors:
        for error in errors:
            flash(error)
        return redirect(url_for("dashboard.doctor_dashboard"))

    flash(f"Prescription generated for {prescription.patient_name}.")
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
