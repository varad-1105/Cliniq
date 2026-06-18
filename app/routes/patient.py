import re
from datetime import datetime, time

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models.appointment import Appointment
from app.services.clinic_status_service import (
    get_current_clinic_status,
    is_clinic_closed,
)
from app.services.notification_service import get_notifications_for_phone
from app.services.queue_service import get_patient_queue_status

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
    }


@patient.route("/book", methods=["GET", "POST"])
def book_appointment():
    clinic_status = get_current_clinic_status()

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

        appointment = Appointment(**booking_data, status="pending")
        db.session.add(appointment)
        db.session.commit()

        return redirect(url_for("patient.booking_confirmation", appointment_id=appointment.id))

    return render_template("book_appointment.html", clinic_status=clinic_status)


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
        searched_phone = request.form.get("phone_number", "").strip()

        if not searched_phone:
            flash("Phone number is required.")
        elif not is_valid_phone_number(searched_phone):
            flash("Enter a valid phone number.")
        else:
            queue_status = get_patient_queue_status(searched_phone)
            notifications = get_notifications_for_phone(searched_phone)

            if queue_status is None:
                flash("No appointment found for that phone number.")

    return render_template(
        "queue_tracker.html",
        clinic_status=clinic_status,
        queue_status=queue_status,
        notifications=notifications,
        searched_phone=searched_phone,
    )
