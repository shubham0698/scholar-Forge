import os
import random
import string
from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def admin_required(f):
    """Decorator that restricts a route to admin users only."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            #flash('Admin access required.')
            return redirect(url_for('public.index'))
        return f(*args, **kwargs)
    return decorated_function

def check_plagiarism(file_path):
    """
    Simulates a plagiarism scanner.
    Returns a score percentage (integer between 1 and 25).
    """
    if not file_path:
        return 0
    # Deterministic-like score based on file name length, or random
    random.seed(os.path.basename(file_path)) if 'os' in globals() else None
    return random.randint(1, 25)

def generate_doi(paper_id):
    """
    Generates a mock Digital Object Identifier (DOI) for a paper.
    Format: 10.5555/SF.2026.XXXXX
    """
    from datetime import datetime
    year = datetime.utcnow().year
    return f"10.5555/SF.{year}.{paper_id:05d}"

def send_notification_email(subject, body, recipient_email):
    """
    Sends a transactional notification email.
    Fails silently in case of SMTP configuration/connection errors.
    """
    from extensions import mail
    from flask_mail import Message
    try:
        msg = Message(subject, recipients=[recipient_email])
        msg.body = body
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Mail notification skipped/failed: {e}")
        return False

def add_watermark_to_pdf(input_pdf_path, author_name, publication_id=None):
    """
    Stamps an official ScholarForge platform watermark and author copyright header/footer onto a PDF document.
    Returns a BytesIO stream containing the watermarked PDF.
    """
    import io
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import Color

    if not input_pdf_path or not os.path.exists(input_pdf_path):
        return None

    try:
        reader = PdfReader(input_pdf_path)
        writer = PdfWriter()

        pub_id_str = f" • ID: {publication_id}" if publication_id else ""
        header_text = f"SCHOLARFORGE OPEN ACCESS REPOSITORY • AUTHOR: {author_name.upper()}{pub_id_str}"
        footer_text = f"Copyright © 2026 Author: {author_name}. All Rights Reserved. Published via ScholarForge Academic Platform."
        diagonal_text = f"SCHOLARFORGE • COPYRIGHT © {author_name.upper()}"

        for page in reader.pages:
            box = page.mediabox
            width = float(box.width)
            height = float(box.height)

            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=(width, height))

            # 1. Top Header Banner
            can.setFillColor(Color(0.38, 0.4, 0.94, alpha=0.85)) # Indigo theme color
            can.setFont("Helvetica-Bold", 8)
            can.drawString(20, height - 16, header_text)
            can.setStrokeColor(Color(0.38, 0.4, 0.94, alpha=0.35))
            can.setLineWidth(0.75)
            can.line(20, height - 20, width - 20, height - 20)

            # 2. Bottom Footer Copyright Band
            can.setFillColor(Color(0.2, 0.25, 0.35, alpha=0.85))
            can.setFont("Helvetica", 8)
            can.drawString(20, 14, footer_text)
            can.setStrokeColor(Color(0.2, 0.25, 0.35, alpha=0.35))
            can.setLineWidth(0.75)
            can.line(20, 24, width - 20, 24)

            # 3. Diagonal Watermark Text Across Center Page
            can.saveState()
            can.translate(width / 2.0, height / 2.0)
            can.rotate(45)
            can.setFillColor(Color(0.38, 0.4, 0.94, alpha=0.12)) # Soft translucent watermark opacity
            font_size = max(16, min(width, height) * 0.045)
            can.setFont("Helvetica-Bold", font_size)
            can.drawCentredString(0, 0, diagonal_text)
            can.restoreState()

            can.save()
            packet.seek(0)

            watermark_pdf = PdfReader(packet)
            watermark_page = watermark_pdf.pages[0]
            page.merge_page(watermark_page)
            writer.add_page(page)

        output_stream = io.BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)
        return output_stream
    except Exception as e:
        print(f"Watermark error: {e}")
        return None
