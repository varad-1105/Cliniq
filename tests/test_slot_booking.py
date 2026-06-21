from datetime import date, time

from app.extensions import db
from app.models.appointment import Appointment
from app.models.slot import Slot
from app.models.user import User


def test_slot_booking_and_unbooking(client, app):
    with app.app_context():
        doctor = User.query.filter_by(email="doctor@test.com").first()
        assert doctor is not None

        slot = Slot(
            slot_date=date(2026, 12, 1),
            slot_time=time(10, 0),
            status="available",
            doctor_id=doctor.id,
        )
        db.session.add(slot)
        db.session.commit()

        appointment = Appointment(
            patient_name="John Doe",
            phone_number="+12345678901",
            reason_for_visit="Checkup",
            preferred_date=date(2026, 12, 1),
            preferred_time=time(10, 0),
            status="pending",
            tracking_id="CLQ-TEST001",
        )
        db.session.add(appointment)
        db.session.commit()

        assert slot.status == "available"

        slot.appointment_id = appointment.id
        slot.status = "booked"
        db.session.commit()

        updated_slot = Slot.query.get(slot.id)
        assert updated_slot.status == "booked"
        assert updated_slot.appointment_id == appointment.id

        updated_slot.appointment_id = None
        updated_slot.status = "available"
        db.session.commit()

        unbooked_slot = Slot.query.get(slot.id)
        assert unbooked_slot.status == "available"
        assert unbooked_slot.appointment_id is None
