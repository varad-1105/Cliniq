from app.extensions import db
from app.models.notification import Notification

STATUS_SIMULATED = "simulated"


def create_notification(appointment, notification_type, message, prevent_duplicate=False):
    if prevent_duplicate and has_notification(appointment, notification_type):
        return None

    notification = Notification(
        appointment_id=appointment.id,
        patient_name=appointment.patient_name,
        phone_number=appointment.phone_number,
        notification_type=notification_type,
        message=message,
        status=STATUS_SIMULATED,
    )
    db.session.add(notification)
    return notification


def has_notification(appointment, notification_type):
    return (
        Notification.query
        .filter_by(appointment_id=appointment.id, notification_type=notification_type)
        .first()
        is not None
    )


def notify_appointment_approved(appointment):
    message = f"Your appointment is confirmed.\nToken: {appointment.token_number}"
    return create_notification(appointment, "appointment_approved", message)


def notify_appointment_rejected(appointment):
    message = "Your appointment request was not approved."
    return create_notification(appointment, "appointment_rejected", message)


def notify_turn_reminder(appointment):
    message = "Your turn is coming soon.\nPlease arrive at clinic."
    return create_notification(
        appointment,
        "turn_reminder",
        message,
        prevent_duplicate=True,
    )


def notify_consultation_started(appointment):
    message = "Doctor is ready for your consultation."
    return create_notification(
        appointment,
        "consultation_started",
        message,
        prevent_duplicate=True,
    )


def get_recent_notifications(limit=8):
    return (
        Notification.query
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )


def get_notification_stats():
    total = Notification.query.count()
    recent = get_recent_notifications()

    return {
        "total": total,
        "recent": recent,
    }


def get_notifications_for_phone(phone_number, limit=5):
    cleaned_phone = _clean_phone(phone_number)
    notifications = (
        Notification.query
        .order_by(Notification.created_at.desc())
        .all()
    )

    return [
        notification
        for notification in notifications
        if _clean_phone(notification.phone_number) == cleaned_phone
    ][:limit]


def _clean_phone(phone_number):
    return "".join(character for character in phone_number if character.isdigit())
