from datetime import datetime
import os
from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file
from flask_login import login_required, current_user

from extensions import db
from models import Paper, Payment, Certificate
from certificate_generator import generate_certificate_id, generate_publication_id, generate_qr_code, generate_certificate_pdf

payments_bp = Blueprint('payments', __name__)

@payments_bp.route('/payment/<int:paper_id>', methods=['GET', 'POST'])
@login_required
def payment(paper_id):
    paper = Paper.query.get_or_404(paper_id)
    if paper.user_id != current_user.id:
        flash('Unauthorized access.')
        return redirect(url_for('papers.my_publications'))

    if paper.payment and paper.payment.status == 'completed':
        flash('Payment already completed for this paper.')
        return redirect(url_for('papers.my_publications'))

    if request.method == 'POST':
        cert_type = request.form.get('cert_type', 'publication')
        if cert_type not in ['publication', 'presentation']:
            cert_type = 'publication'

        new_payment = Payment(
            amount=25.00,
            currency='USD',
            status='completed',
            transaction_ref=f"TXN-{generate_publication_id()}",
            paid_at=datetime.utcnow(),
            user_id=current_user.id,
            paper_id=paper.id,
        )
        db.session.add(new_payment)

        from utils import generate_doi
        paper.doi = generate_doi(paper.id)
        paper.status = 'approved'
        db.session.commit()

        cert_id = generate_certificate_id()
        verify_url = url_for('public.verify_certificate', certificate_id=cert_id, _external=True)
        paper_url = url_for('public.paper_detail', id=paper.id, _external=True)

        qr_filename = f"{cert_id}.png"
        qr_path = generate_qr_code(verify_url, qr_filename)

        guide = paper.guides[0] if paper.guides else None
        
        new_cert = Certificate(
            certificate_id=cert_id,
            qr_code_path=qr_path,
            file_path=None,
            cert_type=cert_type,
            paper_id=paper.id,
        )
        db.session.add(new_cert)
        db.session.commit()

        from utils import send_notification_email
        send_notification_email(
            "Certificate Issued — ScholarForge",
            f"Hello {current_user.username},\n\nPayment successful! Your certificate of publication for \"{paper.title}\" has been officially generated.\n\nCertificate ID: {cert_id}\nDOI: {paper.doi}\n\nYou can view and download it at: {verify_url}\n\nThank you for publishing with ScholarForge!",
            current_user.email
        )

        flash('Payment successful! Your certificate has been generated.')
        return redirect(url_for('payments.certificate_view', certificate_id=cert_id))

    return render_template('payment.html', paper=paper)

@payments_bp.route('/certificate/<certificate_id>')
@login_required
def certificate_view(certificate_id):
    cert = Certificate.query.filter_by(certificate_id=certificate_id).first_or_404()
    paper = cert.paper
    if paper.user_id != current_user.id and not current_user.is_admin:
        flash('Unauthorized access.')
        return redirect(url_for('dashboard.dashboard'))
    return render_template('certificate_view.html', certificate=cert, paper=paper)

@payments_bp.route('/download-certificate/<certificate_id>')
@login_required
def download_certificate(certificate_id):
    cert = Certificate.query.filter_by(certificate_id=certificate_id).first_or_404()
    paper = cert.paper
    if paper.user_id != current_user.id and not current_user.is_admin:
        flash('Unauthorized access.')
        return redirect(url_for('dashboard.dashboard'))

    verify_url = url_for('public.verify_certificate', certificate_id=cert.certificate_id, _external=True)
    paper_url = url_for('public.paper_detail', id=paper.id, _external=True)
    guide = paper.guides[0] if paper.guides else None

    # Dynamically generate PDF certificate in-memory without storing files on disk
    pdf_stream = generate_certificate_pdf(
        certificate_id=cert.certificate_id,
        paper_title=paper.title,
        author_name=paper.author.username,
        publication_id=paper.publication_id,
        category=paper.category,
        institution=paper.author.institution or '',
        guide_name=guide.name if guide else '',
        issue_date=cert.issue_date or datetime.utcnow(),
        verify_url=verify_url,
        qr_code_path=cert.qr_code_path,
        cert_type=getattr(cert, 'cert_type', 'publication') or 'publication',
        doi=paper.doi,
        paper_url=paper_url
    )

    return send_file(
        pdf_stream,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"ScholarForge_Certificate_{certificate_id}.pdf",
    )
