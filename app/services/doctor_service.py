from datetime import date

from app.extensions import db
from app.models.appointment import Appointment
from app.services.queue_service import (
    AVERAGE_CONSULTATION_MINUTES,
    get_estimated_wait_minutes,
    get_people_ahead,
)


def get_today_stats():
    today = date.today()

    total_today = (
        Appointment.query
        .filter(
            (Appointment.preferred_date == today)
            | (Appointment.token_date == today)
        )
        .count()
    )

    return {
        "total_today": total_today,
        "pending": Appointment.query.filter_by(preferred_date=today, status="pending").count(),
        "in_consultation": Appointment.query.filter_by(token_date=today, status="in_consultation").count(),
        "completed": Appointment.query.filter_by(token_date=today, status="completed").count(),
    }


def get_upcoming_queue(limit=5):
    appointments = (
        Appointment.query
        .filter_by(token_date=date.today(), status="approved")
        .filter(Appointment.token_number.isnot(None))
        .order_by(Appointment.token_number.asc())
        .limit(limit)
        .all()
    )

    return [
        {
            "appointment": appointment,
            "eta_minutes": get_estimated_wait_minutes(appointment),
        }
        for appointment in appointments
    ]


def get_search_results(search="", status_filter=""):
    if not search and not status_filter:
        return []

    query = Appointment.query

    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            (Appointment.patient_name.ilike(search_term))
            | (Appointment.phone_number.ilike(search_term))
        )

    if status_filter:
        query = query.filter(Appointment.status == status_filter)

    return (
        query
        .order_by(Appointment.created_at.desc())
        .limit(20)
        .all()
    )


def save_consultation_notes(appointment_id, notes):
    appointment = db.get_or_404(Appointment, appointment_id)
    appointment.consultation_notes = notes.strip()
    db.session.commit()
    return appointment


def get_queue_position(appointment):
    if not appointment:
        return None

    if appointment.status == "approved":
        return get_people_ahead(appointment) + 1

    if appointment.status == "in_consultation":
        return 0

    return None


def get_current_patient_details(current_patient):
    if not current_patient:
        return None

    return {
        "appointment": current_patient,
        "queue_position": get_queue_position(current_patient),
        "eta_minutes": (
            get_queue_position(current_patient) or 0
        ) * AVERAGE_CONSULTATION_MINUTES,
    }
