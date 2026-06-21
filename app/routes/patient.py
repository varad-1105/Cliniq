import re
import secrets
from datetime import datetime, time

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for

from app.extensions import db
from app.models.appointment import Appointment
from app.models.prescription import Prescription
from app.services.clinic_status_service import (
    get_current_clinic_status,
    is_clinic_closed,
)
from app.services.notification_service import get_notifications_for_phone
from app.services.prescription_service import (
    generate_prescription_pdf,
    generate_prescription_qr,
    get_prescription_file_path,
    get_qr_file_path,
)
from app.services.queue_service import get_patient_queue_status, generate_tracking_code

patient = Blueprint("patient", __name__)


def is_valid_phone_number(phone_number):
    cleaned_phone = re.sub(r"[\s\-()]", "", phone_number)
    return re.fullmatch(r"\+?\d{10,15}", cleaned_phone) is not None


def parse_preferred_time(form):
    preferred_time_raw = form.get("preferred_time", "").strip()

    if preferred_time_raw:
        return datetime.strptime(preferred_time_raw, "%H:%M").time()

    hour_raw = form.get("preferred_hour", "").strip()
    minute_raw = form.get("preferred_minute", "").strip()
    period = form.get("preferred_period", "").strip().upper()

    if not hour_raw or not minute_raw or not period:
        raise ValueError("missing time")

    hour = int(hour_raw)
    minute = int(minute_raw)

    if hour < 1 or hour > 12 or minute < 0 or minute > 59 or period not in {"AM", "PM"}:
        raise ValueError("invalid time")

    if period == "AM" and hour == 12:
        hour = 0
    elif period == "PM" and hour != 12:
        hour += 12

    return time(hour, minute)


def parse_booking_form(form):
    errors = []
    patient_name = form.get("patient_name", "").strip()
    phone_number = form.get("phone_number", "").strip()
    slot_id_raw = form.get("slot_id", "").strip()
    reason_for_visit = form.get("reason_for_visit", "").strip()
    preferred_date_raw = form.get("preferred_date", "").strip()

    if not patient_name:
        errors.append("Patient name is required.")

    if not phone_number:
        errors.append("Phone number is required.")
    elif not is_valid_phone_number(phone_number):
        errors.append("Enter a valid phone number.")

    if not reason_for_visit:
        errors.append("Reason for visit is required.")

    preferred_date = None
    if slot_id_raw:
        # Slot selection overrides preferred_date/time
        from app.models.slot import Slot

        slot = db.session.get(Slot, int(slot_id_raw)) if slot_id_raw.isdigit() else None
        if not slot or slot.status != "available":
            errors.append("Selected slot is not available.")
        else:
            preferred_date = slot.slot_date
            # preferred_time will be set later from parse_preferred_time fallback
            # We'll return slot selection to caller via form handling.
    else:
        if not preferred_date_raw:
            errors.append("Preferred date is required.")
        else:
            try:
                preferred_date = datetime.strptime(preferred_date_raw, "%Y-%m-%d").date()
            except ValueError:
                errors.append("Enter a valid preferred date.")

    preferred_time = None
    try:
        preferred_time = parse_preferred_time(form)
    except ValueError:
        errors.append("Enter a valid preferred time.")

    return errors, {
        "patient_name": patient_name,
        "phone_number": phone_number,
        "reason_for_visit": reason_for_visit,
        "preferred_date": preferred_date,
        "preferred_time": preferred_time,
        "slot_id": slot_id_raw,
    }


@patient.route("/book", methods=["GET", "POST"])
def book_appointment():
    clinic_status = get_current_clinic_status()

    # Provide available slots for the booking form
    from app.models.slot import Slot
    available_slots = Slot.query.filter_by(status="available").order_by(Slot.slot_date.asc(), Slot.slot_time.asc()).limit(50).all()

    if request.method == "POST":
        if is_clinic_closed():
            flash("Clinic is currently closed.")
            return render_template(
                "book_appointment.html",
                clinic_status=clinic_status,
                form=request.form,
            )

        errors, booking_data = parse_booking_form(request.form)

        if errors:
            for error in errors:
                flash(error)
            return render_template(
                "book_appointment.html",
                clinic_status=clinic_status,
                form=request.form,
            )

        # Generate a unique tracking ID for secure lookup
        tracking_id = generate_tracking_code()
        appointment = Appointment(**booking_data, status="pending", tracking_id=tracking_id)
        db.session.add(appointment)
        db.session.commit()

        # If a slot was selected, attach it to the appointment and mark booked
        slot_id = booking_data.get("slot_id")
        if slot_id:
            try:
                from app.models.slot import Slot

                slot = db.session.get(Slot, int(slot_id))
                if slot and slot.status == "available":
                    slot.appointment_id = appointment.id
                    slot.status = "booked"
                    db.session.commit()
            except Exception:
                pass

        return redirect(url_for("patient.booking_confirmation", appointment_id=appointment.id))

    return render_template("book_appointment.html", clinic_status=clinic_status, available_slots=available_slots)


@patient.route("/booking/<int:appointment_id>/confirmation")
def booking_confirmation(appointment_id):
    appointment = db.get_or_404(Appointment, appointment_id)
    return render_template("booking_confirmation.html", appointment=appointment)


@patient.route("/queue", methods=["GET", "POST"])
def queue_tracker():
    clinic_status = get_current_clinic_status()
    queue_status = None
    notifications = []
    searched_phone = ""

    if request.method == "POST":
        identifier = request.form.get("tracking_id", "").strip() or request.form.get("phone_number", "").strip()

        if not identifier:
            flash("Tracking ID or phone number is required.")
        else:
            queue_status = get_patient_queue_status(identifier)
            # For notifications, prefer appointment phone if identifier is a tracking id
            if identifier and identifier.upper().startswith("CLQ-") and queue_status and queue_status.get("appointment"):
                appt_phone = queue_status.get("appointment").phone_number
                notifications = get_notifications_for_phone(appt_phone)
            else:
                notifications = get_notifications_for_phone(identifier)

            if queue_status is None:
                flash("No appointment found for that identifier.")
        searched_phone = identifier

    return render_template(
        "queue_tracker.html",
        clinic_status=clinic_status,
        queue_status=queue_status,
        notifications=notifications,
        searched_phone=searched_phone,
    )


@patient.route("/prescription/")
@patient.route("/prescription/<int:prescription_id>")
def download_prescription(prescription_id=None):
    token = request.args.get("token", "").strip()
    prescription = None

    if prescription_id is not None:
        prescription = db.session.get(Prescription, prescription_id)
    elif token:
        prescription = Prescription.query.filter_by(access_token=token).first()

    if not prescription:
        abort(404)

    if not token or token != prescription.access_token:
        abort(403)

    # Ensure PDF and QR exist
    file_path = get_prescription_file_path(prescription)
    if not file_path or not file_path.exists():
        generate_prescription_pdf(prescription)
        generate_prescription_qr(prescription)
        db.session.commit()

    file_path = get_prescription_file_path(prescription)

    if not file_path or not file_path.exists():
        abort(404)

    return send_file(
        file_path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=f"cliniq-prescription-{prescription.id}.pdf",
    )


@patient.route("/prescription/qr/<int:prescription_id>")
def prescription_qr(prescription_id):
    token = request.args.get("token", "").strip()
    prescription = db.session.get(Prescription, prescription_id)

    if not prescription or not token or token != prescription.access_token:
        abort(403)

    # Ensure QR exists
    file_path = get_qr_file_path(prescription)
    if not file_path or not file_path.exists():
        generate_prescription_qr(prescription)
        db.session.commit()

    file_path = get_qr_file_path(prescription)

    if not file_path or not file_path.exists():
        abort(404)

    return send_file(file_path, mimetype="image/png")


@patient.route("/appointments/<int:appointment_id>/history")
def appointment_history(appointment_id):
    appointment = db.session.get(Appointment, appointment_id)
    if not appointment:
        abort(404)

    phone = appointment.phone_number
    # Find previous appointments for same phone
    previous = (
        Appointment.query
        .filter(Appointment.phone_number == phone)
        .order_by(Appointment.created_at.desc())
        .limit(50)
        .all()
    )

    return render_template("patient_history.html", appointment=appointment, previous=previous)
