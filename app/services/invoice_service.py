import os
import secrets
from datetime import datetime
from pathlib import Path

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
    PageTemplate,
    BaseDocTemplate,
    Frame,
    PageBreak,
)
from reportlab.pdfgen import canvas

from app.extensions import db
from app.models.appointment import Appointment


def get_invoice_directory():
    """Get or create the invoices directory."""
    invoice_dir = Path("instance") / "invoices"
    invoice_dir.mkdir(parents=True, exist_ok=True)
    return invoice_dir


def get_invoice_file_path(appointment):
    """Get the file path for an appointment's invoice PDF."""
    if not appointment.invoice_path:
        return None
    
    return Path("instance") / appointment.invoice_path


def get_invoice_access_token(appointment):
    """Generate a secure token for accessing an invoice."""
    if not appointment.invoice_path:
        return None
    
    # Extract the token from the filename
    # Format: invoices/appointment_{id}_{token}.pdf
    filename = Path(appointment.invoice_path).name
    parts = filename.replace("appointment_", "").replace(".pdf", "").split("_")
    if len(parts) >= 2:
        return parts[-1]
    return None


def generate_appointment_invoice_pdf(appointment, clinic_info=None):
    """
    Generate a professional appointment invoice PDF.
    
    Args:
        appointment: Appointment object
        clinic_info: Dictionary with clinic information
        
    Returns:
        Path object pointing to the generated PDF
    """
    if not clinic_info:
        clinic_info = {
            "name": "ClinIQ - Smart Clinic Management",
            "address": "123 Medical Street, Healthcare City",
            "phone": "+1 (555) 123-4567",
            "email": "info@cliniq.health",
            "website": "www.cliniq.health",
        }
    
    invoice_dir = get_invoice_directory()
    
    # Generate unique token
    token = secrets.token_hex(8)
    filename = f"appointment_{appointment.id}_{token}.pdf"
    file_path = invoice_dir / filename
    
    # Create PDF with custom page template for watermark
    doc = InvoiceDocTemplate(
        str(file_path),
        pagesize=letter,
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )
    
    # Build the document content
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=6,
        alignment=1,  # Center
        fontName='Helvetica-Bold',
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=8,
        spaceBefore=12,
        fontName='Helvetica-Bold',
        borderPadding=4,
        borderColor=colors.HexColor('#e0e0e0'),
        borderWidth=1,
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
    )
    
    label_style = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#666666'),
        fontName='Helvetica-Bold',
    )
    
    # Header with clinic info
    story.append(Paragraph("ClinIQ", title_style))
    story.append(Paragraph("Smart Clinic Management Platform", normal_style))
    story.append(Spacer(1, 0.15 * inch))
    
    # Clinic information
    clinic_details = f"""
    <b>{clinic_info['name']}</b><br/>
    {clinic_info['address']}<br/>
    Phone: {clinic_info['phone']}<br/>
    Email: {clinic_info['email']}<br/>
    Website: {clinic_info['website']}
    """
    story.append(Paragraph(clinic_details, normal_style))
    story.append(Spacer(1, 0.25 * inch))
    
    # Invoice title and details
    invoice_num = f"INV-APT-{appointment.id:06d}"
    invoice_date = datetime.utcnow().strftime("%B %d, %Y")
    
    header_data = [
        ["APPOINTMENT INVOICE", f"Invoice #: {invoice_num}"],
        ["", f"Generated: {invoice_date}"],
        ["", f"Appointment ID: APT-{appointment.id:06d}"],
    ]
    
    header_table = Table(header_data, colWidths=[4 * inch, 2 * inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 2), colors.HexColor('#f5f5f5')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, 2), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (0, 2), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    
    story.append(header_table)
    story.append(Spacer(1, 0.2 * inch))
    
    # Patient details
    story.append(Paragraph("PATIENT DETAILS", heading_style))
    
    patient_data = [
        ["Name:", appointment.patient_name, "Age:", "N/A"],
        ["Phone:", appointment.phone_number, "Gender:", "N/A"],
        ["Reason for Visit:", appointment.reason_for_visit, "", ""],
    ]
    
    patient_table = Table(patient_data, colWidths=[1 * inch, 2.5 * inch, 0.8 * inch, 1.7 * inch])
    patient_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    story.append(patient_table)
    story.append(Spacer(1, 0.15 * inch))
    
    # Doctor details (if assigned)
    if appointment.doctor:
        story.append(Paragraph("DOCTOR DETAILS", heading_style))
        
        doctor_data = [
            ["Doctor Name:", appointment.doctor.name],
            ["Specialization:", "General Practitioner"],
            ["Registration #:", "N/A"],
        ]
        
        doctor_table = Table(doctor_data, colWidths=[2 * inch, 4 * inch])
        doctor_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        
        story.append(doctor_table)
        story.append(Spacer(1, 0.15 * inch))
    
    # Appointment details
    story.append(Paragraph("APPOINTMENT DETAILS", heading_style))
    
    appointment_date = appointment.preferred_date.strftime("%B %d, %Y")
    appointment_time = appointment.preferred_time.strftime("%I:%M %p")
    status = appointment.status.upper()
    queue_num = appointment.queue_number or "N/A"
    
    appt_data = [
        ["Appointment Date:", appointment_date, "Appointment Time:", appointment_time],
        ["Status:", status, "Queue Number:", str(queue_num)],
        ["Token Number:", appointment.token_number or "N/A", "Tracking ID:", appointment.tracking_id or "N/A"],
    ]
    
    appt_table = Table(appt_data, colWidths=[1.5 * inch, 2 * inch, 1.5 * inch, 2 * inch])
    appt_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    
    story.append(appt_table)
    story.append(Spacer(1, 0.2 * inch))
    
    # Queue tracking section
    story.append(Paragraph("QUEUE TRACKING", heading_style))
    
    tracking_url = f"www.cliniq.health/track?id={appointment.tracking_id}"
    tracking_text = f"""
    <b>Scan QR Code or visit:</b><br/>
    {tracking_url}<br/><br/>
    <b>Tracking ID:</b> {appointment.tracking_id}
    """
    
    story.append(Paragraph(tracking_text, normal_style))
    story.append(Spacer(1, 0.15 * inch))
    
    # Add QR code if it exists
    qr_path = get_appointment_qr_path(appointment)
    if qr_path and qr_path.exists():
        qr_image = Image(str(qr_path), width=1.5 * inch, height=1.5 * inch)
        story.append(qr_image)
    
    story.append(Spacer(1, 0.2 * inch))
    
    # Payment section
    story.append(Paragraph("PAYMENT DETAILS", heading_style))
    
    payment_data = [
        ["Description", "Amount"],
        ["Consultation Fee", "$50.00"],
        ["Taxes (10%)", "$5.00"],
        ["Total Amount Due", "$55.00"],
    ]
    
    payment_table = Table(payment_data, colWidths=[4 * inch, 2 * inch])
    payment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5490')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, -1), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
    ]))
    
    story.append(payment_table)
    story.append(Spacer(1, 0.25 * inch))
    
    # Important notes
    story.append(Paragraph("IMPORTANT NOTES", heading_style))
    
    notes = """
    • Arrive 15 minutes before your appointment<br/>
    • Bring a valid ID and insurance card (if applicable)<br/>
    • Carry any previous prescriptions or medical records<br/>
    • For rescheduling, contact the clinic at least 24 hours in advance<br/>
    • In case of emergency, please call immediately
    """
    
    story.append(Paragraph(notes, normal_style))
    story.append(Spacer(1, 0.2 * inch))
    
    # Footer
    footer_text = f"""
    <b>Generated by ClinIQ Smart Clinic Management Platform</b><br/>
    Digital Verification ID: {token}<br/>
    Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
    """
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#999999'),
        alignment=1,  # Center
    )
    
    story.append(Paragraph(footer_text, footer_style))
    
    # Build the PDF
    doc.build(story)
    
    # Update appointment with invoice path
    appointment.invoice_path = str(Path(filename).relative_to("instance"))
    db.session.commit()
    
    return file_path


def get_appointment_qr_path(appointment):
    """Get the QR code image path for an appointment."""
    qr_dir = Path("instance") / "appointment_qr"
    qr_file = qr_dir / f"appointment_{appointment.id}.png"
    
    if qr_file.exists():
        return qr_file
    return None


def generate_appointment_qr(appointment):
    """Generate a QR code for appointment tracking."""
    qr_dir = Path("instance") / "appointment_qr"
    qr_dir.mkdir(parents=True, exist_ok=True)
    
    tracking_url = f"https://cliniq.health/track?id={appointment.tracking_id}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(tracking_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    qr_path = qr_dir / f"appointment_{appointment.id}.png"
    img.save(qr_path)
    
    return qr_path


class InvoiceDocTemplate(BaseDocTemplate):
    """Custom document template with watermark support."""
    
    def __init__(self, *args, **kwargs):
        BaseDocTemplate.__init__(self, *args, **kwargs)
        
        # Add a frame for the main content
        self.addPageTemplates([PageTemplate(
            id='normal',
            frames=[
                Frame(
                    self.leftMargin,
                    self.bottomMargin,
                    self.width,
                    self.height,
                    id='F1'
                )
            ],
            onPage=self._add_watermark,
        )])
    
    def _add_watermark(self, canvas, doc):
        """Add watermark to the page."""
        canvas.setFont("Helvetica", 60)
        canvas.setFillAlpha(0.1)
        canvas.rotate(45)
        canvas.drawString(2 * inch, 5 * inch, "ClinIQ")
        canvas.setFillAlpha(1)
