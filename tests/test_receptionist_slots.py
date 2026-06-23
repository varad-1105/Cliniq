from datetime import date, time

from app.extensions import db
from app.models.appointment import Appointment
from app.models.slot import Slot
from app.models.user import User


def login(client, email, password="password"):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def test_receptionist_can_unbook_slot_via_endpoint(client, app):
    with app.app_context():
        receptionist = User.query.filter_by(email="receptionist@test.com").first()
        doctor = User.query.filter_by(email="doctor@test.com").first()
        assert receptionist is not None
        assert doctor is not None

        slot = Slot(
            slot_date=date(2026, 12, 1),
            slot_time=time(11, 0),
            status="booked",
            doctor_id=doctor.id,
        )
        db.session.add(slot)
        db.session.commit()

        appointment = Appointment(
            patient_name="Jane Doe",
            phone_number="+12345678902",
            reason_for_visit="Consultation",
            preferred_date=date(2026, 12, 1),
            preferred_time=time(11, 0),
            status="approved",
            tracking_id="CLQ-TEST002",
        )
        db.session.add(appointment)
        db.session.commit()

        slot.appointment_id = appointment.id
        db.session.commit()
        slot_id = slot.id

    login_response = login(client, "receptionist@test.com")
    assert b"Receptionist Dashboard" in login_response.data

    response = client.post(f"/receptionist/slots/{slot_id}/unbook", follow_redirects=True)
    assert response.status_code == 200
    assert b"Slot has been unbooked." in response.data
    assert b"Receptionist Dashboard" in response.data

    with app.app_context():
        updated_slot = db.session.get(Slot, slot_id)
        assert updated_slot.status == "available"
        assert updated_slot.appointment_id is None


def test_receptionist_can_reassign_booked_slot(client, app):
    with app.app_context():
        doctor = User.query.filter_by(email="doctor@test.com").first()
        slot = Slot(
            slot_date=date(2026, 12, 3),
            slot_time=time(10, 0),
            status="booked",
            doctor_id=doctor.id,
        )
        target_slot = Slot(
            slot_date=date(2026, 12, 3),
            slot_time=time(11, 0),
            status="available",
            doctor_id=doctor.id,
        )
        db.session.add_all([slot, target_slot])
        db.session.commit()
        slot_id = slot.id
        target_slot_id = target_slot.id

        appointment = Appointment(
            patient_name="Bob Patient",
            phone_number="+12345678904",
            reason_for_visit="Follow-up",
            preferred_date=date(2026, 12, 3),
            preferred_time=time(10, 0),
            status="approved",
            tracking_id="CLQ-TEST003",
        )
        db.session.add(appointment)
        db.session.commit()
        slot.appointment_id = appointment.id
        db.session.commit()
        appointment_id = appointment.id

    response = client.post(
        "/login",
        data={"email": "receptionist@test.com", "password": "password"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    response = client.post(
        f"/receptionist/slots/{slot_id}/reassign",
        data={"target_slot_id": str(target_slot_id)},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Appointment reassigned to the selected slot." in response.data

    with app.app_context():
        original_slot = db.session.get(Slot, slot_id)
        reassigned_slot = db.session.get(Slot, target_slot_id)
        assert original_slot.status == "available"
        assert original_slot.appointment_id is None
        assert reassigned_slot.status == "booked"
        assert reassigned_slot.appointment_id == appointment_id
