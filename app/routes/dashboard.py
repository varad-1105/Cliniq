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
from app.services.availability_service import (
    create_availability_window,
    update_availability_window,
    delete_availability_window,
    get_doctor_availabilities,
    AvailabilityError,
)
from app.models.slot import Slot
from app.models.doctor_availability import DoctorAvailability
from app.extensions import db

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

    # Prevent duplicate slots for the same doctor at the same time
    existing = (
        Slot.query
        .filter_by(doctor_id=current_user.id, slot_date=slot_date, slot_time=slot_time)
        .first()
    )
    if existing:
        flash("A slot at that date and time already exists.")
        return redirect(url_for("dashboard.doctor_dashboard"))

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
    from app.models.slot import Slot
    booked_slots = Slot.query.filter_by(status="booked").order_by(Slot.slot_date.asc(), Slot.slot_time.asc()).all()
    return render_template(
        "receptionist_dashboard.html",
        appointments=appointments,
        queue=queue,
        notifications=notifications,
        clinic_status=clinic_status,
        booked_slots=booked_slots,
    )


@dashboard.route("/receptionist/slots/<int:slot_id>/reassign", methods=["GET", "POST"])
@role_required("receptionist")
def reassign_slot(slot_id):
    slot = db.session.get(Slot, slot_id)
    if not slot or slot.status != "booked":
        flash("Slot not found or not booked.")
        return redirect(url_for("dashboard.receptionist_dashboard"))

    available_slots = Slot.query.filter_by(status="available").order_by(Slot.slot_date.asc(), Slot.slot_time.asc()).all()

    if request.method == "POST":
        target_slot_id = request.form.get("target_slot_id", "").strip()
        if not target_slot_id.isdigit():
            flash("Choose a valid target slot.")
            return redirect(url_for("dashboard.reassign_slot", slot_id=slot.id))

        target_slot = db.session.get(Slot, int(target_slot_id))
        if not target_slot or target_slot.status != "available":
            flash("Selected target slot is not available.")
            return redirect(url_for("dashboard.reassign_slot", slot_id=slot.id))

        try:
            appointment_id = slot.appointment_id
            slot.appointment_id = None
            slot.status = "available"
            target_slot.appointment_id = appointment_id
            target_slot.status = "booked"
            db.session.add(slot)
            db.session.add(target_slot)
            db.session.commit()
            flash("Appointment reassigned to the selected slot.")
            return redirect(url_for("dashboard.receptionist_dashboard"))
        except Exception:
            db.session.rollback()
            flash("Failed to reassign the slot. Please try again.")
            return redirect(url_for("dashboard.reassign_slot", slot_id=slot.id))

    return render_template(
        "reassign_slot.html",
        slot=slot,
        available_slots=available_slots,
    )


@dashboard.route("/receptionist/slots/<int:slot_id>/unbook", methods=["POST"])
@role_required("receptionist")
def unbook_slot(slot_id):
    slot = db.session.get(Slot, slot_id)
    if not slot:
        flash("Slot not found.")
        return redirect(url_for("dashboard.receptionist_dashboard"))

    if slot.status != "booked":
        flash("Slot is not currently booked.")
        return redirect(url_for("dashboard.receptionist_dashboard"))

    try:
        # detach appointment but keep appointment record intact
        slot.appointment_id = None
        slot.status = "available"
        db.session.add(slot)
        db.session.commit()
        flash("Slot has been unbooked.")
    except Exception:
        db.session.rollback()
        flash("Failed to unbook the slot. Try again.")

    return redirect(url_for("dashboard.receptionist_dashboard"))


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


# Doctor Availability Window Routes

@dashboard.route("/doctor/availability", methods=["GET", "POST"])
@role_required("doctor")
def doctor_availability():
    """Manage doctor's availability windows."""
    from datetime import datetime, date
    
    if request.method == "POST":
        try:
            availability_date_raw = request.form.get("availability_date", "").strip()
            start_time_raw = request.form.get("start_time", "").strip()
            end_time_raw = request.form.get("end_time", "").strip()
            duration_raw = request.form.get("consultation_duration", "").strip()
            
            if not all([availability_date_raw, start_time_raw, end_time_raw, duration_raw]):
                flash("All fields are required.")
                return redirect(url_for("dashboard.doctor_availability"))
            
            availability_date = datetime.strptime(availability_date_raw, "%Y-%m-%d").date()
            duration_minutes = int(duration_raw)
            
            create_availability_window(
                doctor_id=current_user.id,
                availability_date=availability_date,
                start_time=start_time_raw,
                end_time=end_time_raw,
                duration_minutes=duration_minutes,
            )
            
            flash(f"Availability window created for {availability_date.strftime('%B %d, %Y')}.")
            return redirect(url_for("dashboard.doctor_availability"))
            
        except AvailabilityError as e:
            flash(f"Error: {str(e)}")
            return redirect(url_for("dashboard.doctor_availability"))
        except (ValueError, TypeError) as e:
            flash("Invalid input. Please check your entries.")
            return redirect(url_for("dashboard.doctor_availability"))
    
    availabilities = get_doctor_availabilities(current_user.id)
    today = date.today()
    
    return render_template(
        "doctor_availability.html",
        availabilities=availabilities,
        today=today,
    )


@dashboard.route("/doctor/availability/<int:availability_id>/edit", methods=["GET", "POST"])
@role_required("doctor")
def edit_availability(availability_id):
    """Edit an availability window."""
    from datetime import datetime
    
    availability = db.get_or_404(DoctorAvailability, availability_id)
    
    if availability.doctor_id != current_user.id:
        abort(403)
    
    if request.method == "POST":
        try:
            start_time_raw = request.form.get("start_time", "").strip()
            end_time_raw = request.form.get("end_time", "").strip()
            duration_raw = request.form.get("consultation_duration", "").strip()
            is_active = request.form.get("is_active") == "on"
            
            if not all([start_time_raw, end_time_raw, duration_raw]):
                flash("All fields are required.")
                return redirect(url_for("dashboard.edit_availability", availability_id=availability_id))
            
            duration_minutes = int(duration_raw)
            
            update_availability_window(
                availability_id=availability_id,
                start_time=start_time_raw,
                end_time=end_time_raw,
                duration_minutes=duration_minutes,
                is_active=is_active,
            )
            
            flash("Availability window updated.")
            return redirect(url_for("dashboard.doctor_availability"))
            
        except AvailabilityError as e:
            flash(f"Error: {str(e)}")
            return redirect(url_for("dashboard.edit_availability", availability_id=availability_id))
        except (ValueError, TypeError) as e:
            flash("Invalid input. Please check your entries.")
            return redirect(url_for("dashboard.edit_availability", availability_id=availability_id))
    
    return render_template("edit_availability.html", availability=availability)


@dashboard.route("/doctor/availability/<int:availability_id>/delete", methods=["POST"])
@role_required("doctor")
def delete_availability(availability_id):
    """Delete an availability window."""
    availability = db.get_or_404(DoctorAvailability, availability_id)
    
    if availability.doctor_id != current_user.id:
        abort(403)
    
    try:
        delete_availability_window(availability_id)
        flash("Availability window deleted.")
    except AvailabilityError as e:
        flash(f"Error: {str(e)}")
    
    return redirect(url_for("dashboard.doctor_availability"))


@dashboard.route("/doctor/availability/<int:availability_id>/toggle", methods=["POST"])
@role_required("doctor")
def toggle_availability(availability_id):
    """Toggle availability window active/inactive status."""
    availability = db.get_or_404(DoctorAvailability, availability_id)
    
    if availability.doctor_id != current_user.id:
        abort(403)
    
    try:
        availability.is_active = not availability.is_active
        db.session.commit()
        status = "activated" if availability.is_active else "deactivated"
        flash(f"Availability window {status}.")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}")
    
    return redirect(url_for("dashboard.doctor_availability"))
