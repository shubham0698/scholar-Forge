import os
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user

from extensions import db
from models import User, Paper, Certificate, Review
from utils import admin_required

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
@login_required
@admin_required
def admin_panel():
    total_users = User.query.count()
    total_papers = Paper.query.count()
    pending_papers = Paper.query.filter_by(status='pending').all()
    approved_papers = Paper.query.filter_by(status='approved').count()
    total_certs = Certificate.query.count()
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    reviewers = User.query.filter(User.role.in_(['reviewer', 'guide', 'admin'])).all()
    return render_template(
        'admin.html',
        total_users=total_users,
        total_papers=total_papers,
        pending_papers=pending_papers,
        approved_papers=approved_papers,
        total_certs=total_certs,
        recent_users=recent_users,
        reviewers=reviewers,
    )

@admin_bp.route('/admin/users')
@login_required
@admin_required
def admin_users():
    search_q = request.args.get('q', '')
    if search_q:
        users = User.query.filter(
            (User.username.ilike(f'%{search_q}%')) |
            (User.email.ilike(f'%{search_q}%')) |
            (User.institution.ilike(f'%{search_q}%'))
        ).order_by(User.created_at.desc()).all()
    else:
        users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users, search_q=search_q)

@admin_bp.route('/admin/papers')
@login_required
@admin_required
def admin_papers():
    search_q = request.args.get('q', '')
    status_filter = request.args.get('status', '')
    query = Paper.query
    if search_q:
        query = query.filter(
            (Paper.title.ilike(f'%{search_q}%')) |
            (Paper.keywords.ilike(f'%{search_q}%'))
        )
    if status_filter:
        query = query.filter_by(status=status_filter)
    papers = query.order_by(Paper.created_at.desc()).all()
    return render_template('admin_papers.html', papers=papers, search_q=search_q, status_filter=status_filter)

@admin_bp.route('/admin/approve/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_approve(id):
    paper = Paper.query.get_or_404(id)
    
    # Check plagiarism threshold policy
    if paper.plagiarism_score and paper.plagiarism_score > 20:
        # Check if it has completed reviews
        completed_reviews = [r for r in paper.reviews if r.status == 'completed']
        if not completed_reviews:
            flash(f'Cannot approve paper "{paper.title}". Plagiarism score is high ({paper.plagiarism_score}%) and it has no completed peer reviews.')
            return redirect(url_for('admin.admin_panel'))
            
    paper.status = 'approved'
    paper.rejection_reason = None
    db.session.commit()
    
    from utils import send_notification_email
    send_notification_email(
        "🎉 Paper Approved — ScholarForge Editorial Board",
        f"Hello {paper.author.username},\n\nGreat news! Your research paper titled \"{paper.title}\" (Publication ID: {paper.publication_id or 'SF-2026'}) has been officially APPROVED by the ScholarForge Editorial Board.\n\nNext Steps:\n1. Log into your Author Dashboard: http://localhost:5000/dashboard\n2. Complete processing fee payment to issue your official QR-verified PDF certificate.\n\nThank you for contributing to open-access research!\n\nScholarForge Editorial Board",
        paper.author.email
    )
    
    flash(f'Paper "{paper.title}" approved and notification email sent to {paper.author.email}.')
    next_url = request.form.get('next') or url_for('admin.admin_panel')
    return redirect(next_url)

@admin_bp.route('/admin/reject/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_reject(id):
    paper = Paper.query.get_or_404(id)
    reason = request.form.get('rejection_reason', '').strip()
    if not reason:
        reason = "Does not meet current editorial quality standards or formatting guidelines."
    
    paper.status = 'rejected'
    paper.rejection_reason = reason
    db.session.commit()
    
    from utils import send_notification_email
    send_notification_email(
        "Paper Review Update — ScholarForge Editorial Board",
        f"Hello {paper.author.username},\n\nYour research paper titled \"{paper.title}\" has been evaluated by the ScholarForge Editorial Board.\n\nStatus: REJECTED\n\nEditorial Feedback & Reason for Rejection:\n\"{reason}\"\n\nYou can log into your account at http://localhost:5000/my-publications to review this feedback or update your manuscript.\n\nSincerely,\nScholarForge Editorial Board",
        paper.author.email
    )
    
    flash(f'Paper "{paper.title}" rejected with reason and email sent to {paper.author.email}.')
    next_url = request.form.get('next') or url_for('admin.admin_panel')
    return redirect(next_url)

@admin_bp.route('/admin/make-admin/<int:id>', methods=['POST'])
@login_required
@admin_required
def make_admin(id):
    user = User.query.get_or_404(id)
    user.is_admin = True
    db.session.commit()
    flash(f'{user.username} is now an admin.')
    next_url = request.form.get('next') or url_for('admin.admin_panel')
    return redirect(next_url)

@admin_bp.route('/admin/change-role/<int:id>', methods=['POST'])
@login_required
@admin_required
def change_role(id):
    user = User.query.get_or_404(id)
    new_role = request.form.get('role')
    if new_role not in ['student', 'guide', 'reviewer']:
        flash('Invalid role selected.')
        return redirect(url_for('admin.admin_users'))
    user.role = new_role
    db.session.commit()
    flash(f'Role for {user.username} changed to {new_role|capitalize}.')
    return redirect(url_for('admin.admin_users'))

@admin_bp.route('/admin/delete-user/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(id):
    user = User.query.get_or_404(id)
    if user.is_admin:
        flash('Cannot delete an admin user.')
        return redirect(url_for('admin.admin_users'))
    for paper in user.papers:
        if paper.file_path and os.path.exists(paper.file_path):
            os.remove(paper.file_path)
    db.session.delete(user)
    db.session.commit()
    flash(f'User "{user.username}" and all their data have been deleted.')
    return redirect(url_for('admin.admin_users'))

@admin_bp.route('/admin/delete-paper/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_paper(id):
    paper = Paper.query.get_or_404(id)
    if paper.file_path and os.path.exists(paper.file_path):
        os.remove(paper.file_path)
    db.session.delete(paper)
    db.session.commit()
    flash(f'Paper "{paper.title}" deleted.')
    return redirect(url_for('admin.admin_papers'))

@admin_bp.route('/admin/assign-review/<int:paper_id>', methods=['POST'])
@login_required
@admin_required
def assign_review(paper_id):
    paper = Paper.query.get_or_404(paper_id)
    reviewer_id = request.form.get('reviewer_id', type=int)
    
    if not reviewer_id:
        flash('Please select a reviewer.')
        return redirect(url_for('admin.admin_panel'))
        
    reviewer = User.query.get(reviewer_id)
    if not reviewer or reviewer.role not in ['reviewer', 'guide', 'admin']:
        flash('Invalid reviewer selected.')
        return redirect(url_for('admin.admin_panel'))
        
    existing_review = Review.query.filter_by(paper_id=paper_id, reviewer_id=reviewer_id).first()
    if existing_review:
        flash('Reviewer is already assigned to this paper.')
        return redirect(url_for('admin.admin_panel'))
        
    new_review = Review(
        paper_id=paper_id,
        reviewer_id=reviewer_id,
        status='pending'
    )
    db.session.add(new_review)
    db.session.commit()
    
    from utils import send_notification_email
    send_notification_email(
        "New Review Assignment — ScholarForge",
        f"Hello {reviewer.username},\n\nYou have been assigned a new manuscript to evaluate: \"{paper.title}\". Please log into your Reviewer Panel to complete the review.\n\nThank you!",
        reviewer.email
    )
    
    flash(f'Paper assigned to reviewer "{reviewer.username}".')
    return redirect(url_for('admin.admin_panel'))
