from datetime import datetime, time

from app.extensions import db
from app.models.doctor_availability import DoctorAvailability, GeneratedSlot


class AvailabilityError(Exception):
    """Custom exception for availability-related errors."""
    pass


def create_availability_window(doctor_id, availability_date, start_time, end_time, duration_minutes):
    """
    Create a new availability window for a doctor.
    
    Args:
        doctor_id: The doctor's user ID
        availability_date: Date of availability
        start_time: Start time as time object or string "HH:MM"
        end_time: End time as time object or string "HH:MM"
        duration_minutes: Consultation duration in minutes (10, 15, 20, or 30)
    
    Returns:
        DoctorAvailability object
        
    Raises:
        AvailabilityError: If validation fails
    """
    # Validate duration
    if duration_minutes not in [10, 15, 20, 30]:
        raise AvailabilityError("Consultation duration must be 10, 15, 20, or 30 minutes.")
    
    # Convert string times to time objects if needed
    if isinstance(start_time, str):
        start_time = datetime.strptime(start_time, "%H:%M").time()
    if isinstance(end_time, str):
        end_time = datetime.strptime(end_time, "%H:%M").time()
    
    # Validate time range
    if start_time >= end_time:
        raise AvailabilityError("Start time must be before end time.")
    
    # Check for overlapping availability windows on the same date
    existing = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == doctor_id,
        DoctorAvailability.availability_date == availability_date,
        DoctorAvailability.is_active == True,
    ).all()
    
    for avail in existing:
        if avail.overlaps_with(start_time, end_time):
            raise AvailabilityError(
                f"This time window overlaps with an existing availability window "
                f"({avail.start_time.strftime('%H:%M')} - {avail.end_time.strftime('%H:%M')})."
            )
    
    # Create the availability window
    availability = DoctorAvailability(
        doctor_id=doctor_id,
        availability_date=availability_date,
        start_time=start_time,
        end_time=end_time,
        consultation_duration_minutes=duration_minutes,
        is_active=True,
    )
    
    db.session.add(availability)
    db.session.flush()
    
    # Generate slots for this availability window
    slots = availability.generate_slots()
    for slot in slots:
        db.session.add(slot)
    
    db.session.commit()
    return availability


def update_availability_window(availability_id, start_time, end_time, duration_minutes, is_active):
    """Update an existing availability window."""
    availability = db.get_or_404(DoctorAvailability, availability_id)
    
    # Validate duration
    if duration_minutes not in [10, 15, 20, 30]:
        raise AvailabilityError("Consultation duration must be 10, 15, 20, or 30 minutes.")
    
    # Convert string times if needed
    if isinstance(start_time, str):
        start_time = datetime.strptime(start_time, "%H:%M").time()
    if isinstance(end_time, str):
        end_time = datetime.strptime(end_time, "%H:%M").time()
    
    # Validate time range
    if start_time >= end_time:
        raise AvailabilityError("Start time must be before end time.")
    
    # Check for overlapping windows (excluding self)
    existing = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == availability.doctor_id,
        DoctorAvailability.availability_date == availability.availability_date,
        DoctorAvailability.id != availability_id,
        DoctorAvailability.is_active == True,
    ).all()
    
    for avail in existing:
        if avail.overlaps_with(start_time, end_time):
            raise AvailabilityError(
                f"This time window overlaps with an existing availability window "
                f"({avail.start_time.strftime('%H:%M')} - {avail.end_time.strftime('%H:%M')})."
            )
    
    # Update the availability
    availability.start_time = start_time
    availability.end_time = end_time
    availability.consultation_duration_minutes = duration_minutes
    availability.is_active = is_active
    availability.updated_at = datetime.utcnow()
    
    # Regenerate slots
    slots = availability.generate_slots()
    for slot in slots:
        db.session.add(slot)
    
    db.session.commit()
    return availability


def delete_availability_window(availability_id):
    """Delete an availability window and its generated slots."""
    availability = db.get_or_404(DoctorAvailability, availability_id)
    
    # Check if any slots have been booked
    booked_slots = GeneratedSlot.query.filter(
        GeneratedSlot.availability_id == availability_id,
        GeneratedSlot.appointment_id.isnot(None),
    ).first()
    
    if booked_slots:
        raise AvailabilityError(
            "Cannot delete availability window because slots have already been booked. "
            "Please mark it as inactive instead."
        )
    
    db.session.delete(availability)
    db.session.commit()


def get_doctor_availabilities(doctor_id, from_date=None):
    """Get all active availability windows for a doctor."""
    query = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == doctor_id,
        DoctorAvailability.is_active == True,
    )
    
    if from_date:
        query = query.filter(DoctorAvailability.availability_date >= from_date)
    
    return query.order_by(
        DoctorAvailability.availability_date.asc(),
        DoctorAvailability.start_time.asc(),
    ).all()


def get_available_slots(doctor_id, from_date=None, to_date=None):
    """Get all available (not booked) slots for a doctor within a date range."""
    query = GeneratedSlot.query.join(DoctorAvailability).filter(
        DoctorAvailability.doctor_id == doctor_id,
        GeneratedSlot.status == "available",
        DoctorAvailability.is_active == True,
    )
    
    if from_date:
        query = query.filter(GeneratedSlot.slot_date >= from_date)
    
    if to_date:
        query = query.filter(GeneratedSlot.slot_date <= to_date)
    
    return query.order_by(
        GeneratedSlot.slot_date.asc(),
        GeneratedSlot.slot_time.asc(),
    ).all()


def get_earliest_available_slot(doctor_id, from_date=None):
    """Get the earliest available slot for a doctor."""
    query = GeneratedSlot.query.join(DoctorAvailability).filter(
        DoctorAvailability.doctor_id == doctor_id,
        GeneratedSlot.status == "available",
        DoctorAvailability.is_active == True,
    )
    
    if from_date:
        query = query.filter(GeneratedSlot.slot_date >= from_date)
    
    return query.order_by(
        GeneratedSlot.slot_date.asc(),
        GeneratedSlot.slot_time.asc(),
    ).first()
