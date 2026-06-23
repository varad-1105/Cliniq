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

        updated_slot = db.session.get(Slot, slot.id)
        assert updated_slot.status == "booked"
        assert updated_slot.appointment_id == appointment.id

        updated_slot.appointment_id = None
        updated_slot.status = "available"
        db.session.commit()

        unbooked_slot = db.session.get(Slot, slot.id)
        assert unbooked_slot.status == "available"
        assert unbooked_slot.appointment_id is None


def test_patient_can_book_available_slot(client, app):
    with app.app_context():
        doctor = User.query.filter_by(email="doctor@test.com").first()
        slot = Slot(
            slot_date=date(2026, 12, 2),
            slot_time=time(9, 30),
            status="available",
            doctor_id=doctor.id,
        )
        db.session.add(slot)
        db.session.commit()
        slot_id = slot.id

    response = client.post(
        "/book",
        data={
            "patient_name": "Alice Patient",
            "phone_number": "+12345678903",
            "reason_for_visit": "Routine checkup",
            "slot_id": str(slot_id),
            "preferred_hour": "09",
            "preferred_minute": "30",
            "preferred_period": "AM",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"booking request received" in response.data.lower()

    with app.app_context():
        booked_slot = db.session.get(Slot, slot_id)
        assert booked_slot.status == "booked"
        assert booked_slot.appointment_id is not None
