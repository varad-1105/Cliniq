from datetime import date, datetime

from app.extensions import db
from app.models.appointment import Appointment
from app.services.notification_service import (
    notify_consultation_started,
    notify_turn_reminder,
)

AVERAGE_CONSULTATION_MINUTES = 10


def _today():
    return date.today()


def _token_value(token_number):
    if not token_number:
        return 0

    try:
        return int(token_number.split("-")[1])
    except (IndexError, ValueError):
        return 0


def generate_next_token(token_date=None):
    token_date = token_date or _today()
    today_tokens = (
        Appointment.query
        .filter(Appointment.token_date == token_date)
        .filter(Appointment.token_number.isnot(None))
        .all()
    )
    next_number = max((_token_value(appointment.token_number) for appointment in today_tokens), default=0) + 1
    return f"T-{next_number:03d}"


def assign_token(appointment):
    if appointment.token_number:
        return appointment

    appointment.token_date = _today()
    appointment.token_number = generate_next_token(appointment.token_date)
    return appointment


def approve_with_token(appointment):
    appointment.status = "approved"
    appointment.consultation_started_at = None
    appointment.completed_at = None
    assign_token(appointment)
    return appointment


def reject_without_token(appointment):
    appointment.status = "rejected"
    appointment.token_number = None
    appointment.token_date = None
    appointment.consultation_started_at = None
    appointment.completed_at = None
    return appointment


def get_today_queue(include_completed=False):
    statuses = ["approved", "in_consultation"]

    if include_completed:
        statuses.append("completed")

    return (
        Appointment.query
        .filter(Appointment.token_date == _today())
        .filter(Appointment.token_number.isnot(None))
        .filter(Appointment.status.in_(statuses))
        .order_by(Appointment.token_number.asc())
        .all()
    )


def get_current_patient():
    return (
        Appointment.query
        .filter(Appointment.token_date == _today())
        .filter(Appointment.status == "in_consultation")
        .order_by(Appointment.token_number.asc())
        .first()
    )


def get_next_patient():
    return (
        Appointment.query
        .filter(Appointment.token_date == _today())
        .filter(Appointment.status == "approved")
        .filter(Appointment.token_number.isnot(None))
        .order_by(Appointment.token_number.asc())
        .first()
    )


def get_current_serving_token():
    current_patient = get_current_patient()

    if current_patient:
        return current_patient.token_number

    next_patient = get_next_patient()
    return next_patient.token_number if next_patient else "Not started"


def get_people_ahead(appointment):
    if not appointment or not appointment.token_number or appointment.status != "approved":
        return 0

    return (
        Appointment.query
        .filter(Appointment.token_date == appointment.token_date)
        .filter(Appointment.token_number.isnot(None))
        .filter(Appointment.status.in_(["approved", "in_consultation"]))
        .filter(Appointment.token_number < appointment.token_number)
        .count()
    )


def get_estimated_wait_minutes(appointment):
    return get_people_ahead(appointment) * AVERAGE_CONSULTATION_MINUTES


def get_queue_summary():
    current_patient = get_current_patient()
    next_patient = get_next_patient()
    active_queue = get_today_queue()
    completed_today = get_today_queue(include_completed=True)
    send_turn_reminders(active_queue)

    return {
        "current_patient": current_patient,
        "next_patient": next_patient,
        "current_serving_token": get_current_serving_token(),
        "active_queue": active_queue,
        "completed_today": [
            appointment for appointment in completed_today if appointment.status == "completed"
        ],
        "waiting_count": len([appointment for appointment in active_queue if appointment.status == "approved"]),
    }


def start_next_consultation():
    current_patient = get_current_patient()

    if current_patient:
        return current_patient, "A consultation is already in progress."

    next_patient = get_next_patient()

    if not next_patient:
        return None, "No approved patients are waiting."

    next_patient.status = "in_consultation"
    next_patient.consultation_started_at = datetime.now()
    notify_consultation_started(next_patient)
    db.session.commit()
    return next_patient, f"Started consultation for {next_patient.patient_name}."


def complete_current_consultation(notes=None):
    current_patient = get_current_patient()

    if not current_patient:
        return None, "No consultation is currently in progress."

    if notes is not None:
        current_patient.consultation_notes = notes.strip()

    current_patient.status = "completed"
    current_patient.completed_at = datetime.now()
    db.session.commit()
    return current_patient, f"Completed consultation for {current_patient.patient_name}."


def find_latest_appointment_by_phone(phone_number):
    cleaned_phone = _clean_phone(phone_number)

    appointments = (
        Appointment.query
        .order_by(Appointment.created_at.desc())
        .all()
    )

    for appointment in appointments:
        if _clean_phone(appointment.phone_number) == cleaned_phone:
            return appointment

    return None


def get_patient_queue_status(phone_number):
    appointment = find_latest_appointment_by_phone(phone_number)

    if not appointment:
        return None

    if get_people_ahead(appointment) == 2:
        notify_turn_reminder(appointment)
        db.session.commit()

    return {
        "appointment": appointment,
        "current_serving_token": get_current_serving_token(),
        "people_ahead": get_people_ahead(appointment),
        "eta_minutes": get_estimated_wait_minutes(appointment),
    }


def send_turn_reminders(queue=None):
    queue = queue or get_today_queue()

    for appointment in queue:
        if get_people_ahead(appointment) == 2:
            notify_turn_reminder(appointment)

    db.session.commit()


def _clean_phone(phone_number):
    return "".join(character for character in phone_number if character.isdigit())
