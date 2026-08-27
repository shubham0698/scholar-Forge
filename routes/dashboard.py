from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db
from models import Paper, Certificate

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    from models import Contributor, Paper, Certificate
    import json

    user_papers = Paper.query.filter_by(user_id=current_user.id).order_by(Paper.created_at.desc()).all()
    paper_count = len(user_papers)
    approved_count = sum(1 for p in user_papers if p.status == 'approved')
    pending_count = sum(1 for p in user_papers if p.status == 'pending')
    rejected_count = sum(1 for p in user_papers if p.status == 'rejected')
    draft_count = sum(1 for p in user_papers if p.status == 'draft')
    
    cert_count = Certificate.query.join(Paper).filter(Paper.user_id == current_user.id).count()
    total_views = sum(p.views_count or 0 for p in user_papers)
    total_downloads = sum(p.downloads_count or 0 for p in user_papers)
    
    # Calculate categories distribution
    categories_dict = {}
    for p in user_papers:
        cat = p.category or 'General'
        categories_dict[cat] = categories_dict.get(cat, 0) + 1
        
    # Top 5 papers for Engagement Chart
    chart_paper_titles = [p.title[:25] + ('...' if len(p.title) > 25 else '') for p in user_papers[:5]]
    chart_views = [p.views_count or 0 for p in user_papers[:5]]
    chart_downloads = [p.downloads_count or 0 for p in user_papers[:5]]

    # Find contributors matching username
    co_authored_papers = Contributor.query.filter(
        (Contributor.name.ilike(f'%{current_user.username}%')) & 
        (Contributor.linked_user_id.is_(None))
    ).all()
    
    # Find top performing paper
    top_paper = max(user_papers, key=lambda p: (p.views_count or 0) + (p.downloads_count or 0)) if user_papers else None
    
    return render_template(
        'dashboard.html',
        name=current_user.username,
        paper_count=paper_count,
        approved_count=approved_count,
        pending_count=pending_count,
        rejected_count=rejected_count,
        draft_count=draft_count,
        cert_count=cert_count,
        total_views=total_views,
        total_downloads=total_downloads,
        user_papers=user_papers,
        top_paper=top_paper,
        co_authored_papers=co_authored_papers,
        chart_paper_titles=json.dumps(chart_paper_titles),
        chart_views=json.dumps(chart_views),
        chart_downloads=json.dumps(chart_downloads),
        categories_labels=json.dumps(list(categories_dict.keys())),
        categories_counts=json.dumps(list(categories_dict.values())),
        status_counts=json.dumps([approved_count, pending_count, draft_count + rejected_count])
    )

@dashboard_bp.route('/claim-coauthorship/<int:contributor_id>', methods=['POST'])
@login_required
def claim_coauthorship(contributor_id):
    from models import Contributor
    contributor = Contributor.query.get_or_404(contributor_id)
    if current_user.username.lower() in contributor.name.lower():
        contributor.linked_user_id = current_user.id
        db.session.commit()
        flash(f'Successfully claimed co-authorship for "{contributor.paper.title}"!')
    else:
        flash('Could not verify co-authorship name matching.')
    return redirect(url_for('dashboard.dashboard'))

@dashboard_bp.route('/profile')
@login_required
def profile():
    from models import Paper, Certificate
    user_papers = Paper.query.filter_by(user_id=current_user.id).order_by(Paper.created_at.desc()).all()
    approved_count = sum(1 for p in user_papers if p.status == 'approved')
    cert_count = Certificate.query.join(Paper).filter(Paper.user_id == current_user.id).count()
    total_views = sum(p.views_count or 0 for p in user_papers)
    total_downloads = sum(p.downloads_count or 0 for p in user_papers)
    
    return render_template(
        'profile.html',
        user=current_user,
        papers=user_papers,
        approved_count=approved_count,
        cert_count=cert_count,
        total_views=total_views,
        total_downloads=total_downloads
    )

@dashboard_bp.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.username = request.form.get('username', current_user.username)
        current_user.institution = request.form.get('institution', current_user.institution)
        current_user.department = request.form.get('department', current_user.department)
        db.session.commit()
        flash('Profile updated successfully!')
        return redirect(url_for('dashboard.profile'))
    return render_template('edit_profile.html', user=current_user)

@dashboard_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pw = request.form.get('current_password')
        new_pw = request.form.get('new_password')
        confirm_pw = request.form.get('confirm_password')

        if not check_password_hash(current_user.password, current_pw):
            flash('Current password is incorrect.')
            return redirect(url_for('dashboard.change_password'))

        if new_pw != confirm_pw:
            flash('New passwords do not match.')
            return redirect(url_for('dashboard.change_password'))

        if len(new_pw) < 6:
            flash('Password must be at least 6 characters long.')
            return redirect(url_for('dashboard.change_password'))

        current_user.password = generate_password_hash(new_pw, method='pbkdf2:sha256')
        db.session.commit()
        flash('Password changed successfully!')
        return redirect(url_for('dashboard.profile'))
    return render_template('change_password.html')
