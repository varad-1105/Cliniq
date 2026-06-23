from datetime import datetime

from app.extensions import db
from app.models.appointment import Appointment
from app.models.doctor_availability import GeneratedSlot
from app.services.queue_service import approve_with_token


def allocate_appointment_to_slot(appointment_id, slot_id):
    """
    Allocate an appointment to a specific generated slot.
    
    Args:
        appointment_id: The appointment ID
        slot_id: The GeneratedSlot ID
        
    Returns:
        The updated appointment
    """
    appointment = db.get_or_404(Appointment, appointment_id)
    slot = db.get_or_404(GeneratedSlot, slot_id)
    
    if slot.status != "available":
        raise ValueError("Slot is not available for booking.")
    
    # Update appointment with slot information
    appointment.preferred_date = slot.slot_date
    appointment.preferred_time = slot.slot_time
    appointment.doctor_id = slot.availability.doctor_id
    appointment.appointment_source = "manual"
    
    # Update slot status
    slot.appointment_id = appointment.id
    slot.status = "booked"
    
    db.session.commit()
    return appointment


def auto_allocate_appointment(appointment_id, doctor_id, preferred_date=None):
    """
    Automatically allocate an appointment to the earliest available slot.
    
    Args:
        appointment_id: The appointment ID
        doctor_id: The doctor ID to allocate from
        preferred_date: Optional preferred date (must be on or after this date)
        
    Returns:
        The updated appointment with auto-allocated slot
        
    Raises:
        ValueError: If no slots are available
    """
    appointment = db.get_or_404(Appointment, appointment_id)
    
    # Find earliest available slot
    query = GeneratedSlot.query.join(
        GeneratedSlot.availability
    ).filter(
        GeneratedSlot.status == "available",
        GeneratedSlot.availability.has(
            (GeneratedSlot.availability.doctor_id == doctor_id)
            & (GeneratedSlot.availability.is_active == True)
        ),
    )
    
    if preferred_date:
        query = query.filter(GeneratedSlot.slot_date >= preferred_date)
    
    earliest_slot = query.order_by(
        GeneratedSlot.slot_date.asc(),
        GeneratedSlot.slot_time.asc(),
    ).first()
    
    if not earliest_slot:
        raise ValueError(f"No available slots for doctor ID {doctor_id}.")
    
    # Update appointment
    appointment.preferred_date = earliest_slot.slot_date
    appointment.preferred_time = earliest_slot.slot_time
    appointment.doctor_id = doctor_id
    appointment.appointment_source = "auto_allocated"
    
    # Update slot
    earliest_slot.appointment_id = appointment.id
    earliest_slot.status = "booked"
    
    # Approve the appointment with token
    approve_with_token(appointment)
    
    db.session.commit()
    return appointment


def get_appointment_queue_number(appointment_id):
    """
    Calculate the queue number for an appointment based on its slot time.
    
    Args:
        appointment_id: The appointment ID
        
    Returns:
        Queue number (integer) or None if appointment not found
    """
    appointment = db.session.get(Appointment, appointment_id)
    if not appointment:
        return None
    
    if not appointment.preferred_date or not appointment.preferred_time:
        return None
    
    # Count how many appointments are scheduled before this one
    earlier_appointments = Appointment.query.filter(
        Appointment.doctor_id == appointment.doctor_id,
        Appointment.preferred_date == appointment.preferred_date,
        Appointment.status.in_(["pending", "approved", "in_consultation"]),
        (Appointment.preferred_time < appointment.preferred_time)
        | ((Appointment.preferred_time == appointment.preferred_time) & (Appointment.id < appointment.id)),
    ).count()
    
    return earlier_appointments + 1


def get_appointments_by_source(source=None):
    """
    Get appointments filtered by source (manual, auto_allocated, walk_in).
    
    Args:
        source: 'manual', 'auto_allocated', 'walk_in', or None for all
        
    Returns:
        List of appointments
    """
    query = Appointment.query
    
    if source:
        query = query.filter(Appointment.appointment_source == source)
    
    return query.order_by(
        Appointment.preferred_date.asc(),
        Appointment.preferred_time.asc(),
    ).all()
