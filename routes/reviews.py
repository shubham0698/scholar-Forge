from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from datetime import datetime

from extensions import db
from models import Review, Paper

reviews_bp = Blueprint('reviews', __name__)

def reviewer_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['reviewer', 'guide', 'admin']:
            flash('Reviewer access required.')
            return redirect(url_for('public.index'))
        return f(*args, **kwargs)
    return decorated_function

@reviews_bp.route('/reviewer/dashboard')
@login_required
@reviewer_required
def reviewer_dashboard():
    assigned_reviews = Review.query.filter_by(
        reviewer_id=current_user.id, status='pending'
    ).all()
    completed_reviews = Review.query.filter_by(
        reviewer_id=current_user.id, status='completed'
    ).all()
    return render_template(
        'reviewer_dashboard.html',
        assigned_reviews=assigned_reviews,
        completed_reviews=completed_reviews
    )

@reviews_bp.route('/reviewer/submit-review/<int:review_id>', methods=['POST'])
@login_required
@reviewer_required
def submit_review(review_id):
    review = Review.query.get_or_404(review_id)
    if review.reviewer_id != current_user.id and not current_user.is_admin:
        abort(403)
        
    score = request.form.get('score', type=int)
    comments = request.form.get('comments', '')
    
    if not score or score < 1 or score > 5:
        flash('Please select a valid score between 1 and 5.')
        return redirect(url_for('reviews.reviewer_dashboard'))
        
    review.score = score
    review.comments = comments
    review.status = 'completed'
    review.created_at = datetime.utcnow()
    
    db.session.commit()
    flash('Review submitted successfully!')
    return redirect(url_for('reviews.reviewer_dashboard'))
