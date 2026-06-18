import re
from datetime import datetime

from app.extensions import db
from app.models.appointment import Appointment
from app.services.notification_service import (
    notify_appointment_approved,
    notify_appointment_rejected,
)
from app.services.queue_service import approve_with_token, reject_without_token


def is_valid_phone_number(phone_number):
    cleaned_phone = re.sub(r"[\s\-()]", "", phone_number)
    return re.fullmatch(r"\+?\d{10,15}", cleaned_phone) is not None


def get_appointments_by_status():
    appointments = (
        Appointment.query
        .order_by(Appointment.preferred_date.asc(), Appointment.preferred_time.asc())
        .all()
    )

    return {
        "pending": [appointment for appointment in appointments if appointment.status == "pending"],
        "approved": [appointment for appointment in appointments if appointment.status == "approved"],
        "rejected": [appointment for appointment in appointments if appointment.status == "rejected"],
        "in_consultation": [
            appointment for appointment in appointments if appointment.status == "in_consultation"
        ],
        "completed": [appointment for appointment in appointments if appointment.status == "completed"],
    }


def update_appointment_status(appointment_id, status):
    appointment = db.get_or_404(Appointment, appointment_id)

    if status == "approved":
        approve_with_token(appointment)
        notify_appointment_approved(appointment)
    elif status == "rejected":
        reject_without_token(appointment)
        notify_appointment_rejected(appointment)
    else:
        appointment.status = status

    db.session.commit()
    return appointment


def validate_walk_in_form(form):
    errors = []
    patient_name = form.get("patient_name", "").strip()
    phone_number = form.get("phone_number", "").strip()
    reason_for_visit = form.get("reason_for_visit", "").strip()

    if not patient_name:
        errors.append("Patient name is required.")

    if not phone_number:
        errors.append("Phone number is required.")
    elif not is_valid_phone_number(phone_number):
        errors.append("Enter a valid phone number.")

    if not reason_for_visit:
        errors.append("Reason for visit is required.")

    return errors, {
        "patient_name": patient_name,
        "phone_number": phone_number,
        "reason_for_visit": reason_for_visit,
    }


def create_walk_in_appointment(form):
    errors, walk_in_data = validate_walk_in_form(form)

    if errors:
        return errors, None

    now = datetime.now()
    appointment = Appointment(
        **walk_in_data,
        preferred_date=now.date(),
        preferred_time=now.time().replace(second=0, microsecond=0),
        status="approved",
    )
    approve_with_token(appointment)
    db.session.add(appointment)
    db.session.flush()
    notify_appointment_approved(appointment)
    db.session.commit()
    return [], appointment
