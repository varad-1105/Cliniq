from datetime import datetime

from app.extensions import db
from app.models.clinic_status import ClinicStatus

STATUS_OPEN = "open"
STATUS_CLOSED = "closed"
STATUS_EMERGENCY = "emergency"

STATUS_MESSAGES = {
    STATUS_OPEN: "Clinic is open.",
    STATUS_CLOSED: "Clinic is currently closed.",
    STATUS_EMERGENCY: "Doctor is attending an emergency. Waiting time may increase.",
}


def ensure_default_clinic_status():
    if ClinicStatus.query.first() is None:
        status = ClinicStatus(
            status=STATUS_OPEN,
            message=STATUS_MESSAGES[STATUS_OPEN],
        )
        db.session.add(status)
        db.session.commit()


def get_current_clinic_status():
    status = ClinicStatus.query.order_by(ClinicStatus.id.asc()).first()

    if status is None:
        ensure_default_clinic_status()
        status = ClinicStatus.query.order_by(ClinicStatus.id.asc()).first()

    return status


def update_clinic_status(status_value, updated_by=None):
    if status_value not in STATUS_MESSAGES:
        raise ValueError("Invalid clinic status.")

    status = get_current_clinic_status()
    status.status = status_value
    status.message = STATUS_MESSAGES[status_value]
    status.updated_at = datetime.utcnow()
    status.updated_by = updated_by
    db.session.commit()
    return status


def is_clinic_closed():
    return get_current_clinic_status().status == STATUS_CLOSED
