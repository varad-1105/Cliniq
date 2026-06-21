from datetime import date, time

from app import create_app
from app.extensions import db
from app.models.appointment import Appointment
from app.models.notification import Notification
from app.models.user import User
from app.services.clinic_status_service import update_clinic_status
from app.services.queue_service import approve_with_token

app = create_app()


def upsert_user(name, email, password, role):
    user = User.query.filter_by(email=email).first()

    if user is None:
        user = User(name=name, email=email, role=role)
        db.session.add(user)
    else:
        user.name = name
        user.role = role

    user.set_password(password)
    return user


def clear_demo_appointments(phone_numbers):
    for phone_number in phone_numbers:
        Notification.query.filter_by(phone_number=phone_number).delete()
        Appointment.query.filter_by(phone_number=phone_number).delete()


def create_demo_appointment(name, phone, reason, visit_time, status):
    appointment = Appointment(
        patient_name=name,
        phone_number=phone,
        reason_for_visit=reason,
        preferred_date=date.today(),
        preferred_time=visit_time,
        status="pending",
    )
    db.session.add(appointment)
    db.session.flush()

    if status == "approved":
        approve_with_token(appointment)
    elif status == "rejected":
        appointment.status = "rejected"
    elif status == "completed":
        approve_with_token(appointment)
        appointment.status = "completed"
        appointment.consultation_notes = "Demo consultation completed."

    return appointment


with app.app_context():
    # Demo users (kept here for local testing only):
    # Doctor: doctor@cliniq.com / 123456
    # Receptionist: receptionist@cliniq.com / 123456
    upsert_user("Admin Doctor", "doctor@cliniq.com", "123456", "doctor")
    upsert_user("Front Desk", "receptionist@cliniq.com", "123456", "receptionist")

    demo_phones = [
        "7000000001",
        "7000000002",
        "7000000003",
        "7000000004",
    ]
    clear_demo_appointments(demo_phones)

    create_demo_appointment(
        "Aarav Sharma",
        "7000000001",
        "Fever and body ache",
        time(10, 0),
        "approved",
    )
    create_demo_appointment(
        "Meera Patel",
        "7000000002",
        "Follow-up visit",
        time(10, 15),
        "approved",
    )
    create_demo_appointment(
        "Rohan Gupta",
        "7000000003",
        "Cough and cold",
        time(10, 30),
        "pending",
    )
    create_demo_appointment(
        "Sana Khan",
        "7000000004",
        "General consultation",
        time(10, 45),
        "rejected",
    )

    update_clinic_status("open", None)
    db.session.commit()

    print("Demo users and appointments created successfully!")
