import os
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from models import Paper, Guide, Contributor, Certificate
from certificate_generator import generate_publication_id
from utils import check_plagiarism

papers_bp = Blueprint('papers', __name__)

@papers_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        title = request.form.get('title')
        abstract = request.form.get('abstract')
        category = request.form.get('category')
        keywords = request.form.get('keywords')
        visibility = request.form.get('visibility', 'public')

        guide_name = request.form.get('guide_name')
        guide_designation = request.form.get('guide_designation')
        guide_department = request.form.get('guide_department')
        guide_institution = request.form.get('guide_institution')

        file = request.files.get('file')
        file_path = None
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{current_user.id}_{filename}")
            file.save(file_path)

        pub_id = generate_publication_id()
        score = check_plagiarism(file_path)

        new_paper = Paper(
            title=title, abstract=abstract, category=category,
            keywords=keywords, visibility=visibility, file_path=file_path,
            user_id=current_user.id, publication_id=pub_id, status='pending',
            plagiarism_score=score
        )
        db.session.add(new_paper)
        db.session.commit()

        if guide_name:
            new_guide = Guide(
                name=guide_name,
                designation=guide_designation or '',
                department=guide_department or '',
                institution=guide_institution or '',
                paper_id=new_paper.id,
            )
            db.session.add(new_guide)
            db.session.commit()

        contributor_names = request.form.getlist('contributor_name[]')
        contributor_roles = request.form.getlist('contributor_role[]')
        contributor_affiliations = request.form.getlist('contributor_affiliation[]')
        for i, cname in enumerate(contributor_names):
            if cname.strip():
                new_contributor = Contributor(
                    name=cname.strip(),
                    role=contributor_roles[i].strip() if i < len(contributor_roles) else '',
                    affiliation=contributor_affiliations[i].strip() if i < len(contributor_affiliations) else '',
                    paper_id=new_paper.id,
                )
                db.session.add(new_contributor)
        db.session.commit()

        flash('Paper uploaded successfully! It is now pending review.')
        return redirect(url_for('papers.my_publications'))

    return render_template('upload.html')

@papers_bp.route('/my-publications')
@login_required
def my_publications():
    papers = Paper.query.filter_by(user_id=current_user.id).order_by(Paper.created_at.desc()).all()
    return render_template('my_publications.html', papers=papers)

@papers_bp.route('/my-certificates')
@login_required
def my_certificates():
    certs = Certificate.query.join(Paper).filter(Paper.user_id == current_user.id).order_by(Certificate.issue_date.desc()).all()
    return render_template('my_certificates.html', certificates=certs)

@papers_bp.route('/edit-paper/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_paper(id):
    paper = Paper.query.get_or_404(id)
    if paper.user_id != current_user.id:
        flash('Unauthorized access.')
        return redirect(url_for('papers.my_publications'))

    if request.method == 'POST':
        paper.title = request.form.get('title')
        paper.abstract = request.form.get('abstract')
        paper.category = request.form.get('category')
        paper.keywords = request.form.get('keywords')
        paper.visibility = request.form.get('visibility')
        
        file = request.files.get('file')
        if file and file.filename != '':
            # Delete old file
            if paper.file_path and os.path.exists(paper.file_path):
                try:
                    os.remove(paper.file_path)
                except Exception as e:
                    print(f"Error removing old manuscript: {e}")
                    
            filename = secure_filename(file.filename)
            new_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{current_user.id}_{filename}")
            file.save(new_file_path)
            paper.file_path = new_file_path
            
            # Recheck plagiarism
            paper.plagiarism_score = check_plagiarism(new_file_path)
            
        db.session.commit()
        flash('Paper updated successfully!')
        return redirect(url_for('papers.my_publications'))

    return render_template('edit_paper.html', paper=paper)

@papers_bp.route('/delete-paper/<int:id>', methods=['POST'])
@login_required
def delete_paper(id):
    paper = Paper.query.get_or_404(id)
    if paper.user_id != current_user.id:
        flash('Unauthorized access.')
        return redirect(url_for('papers.my_publications'))

    if paper.file_path and os.path.exists(paper.file_path):
        os.remove(paper.file_path)

    db.session.delete(paper)
    db.session.commit()
    flash('Paper deleted successfully!')
    return redirect(url_for('papers.my_publications'))

@papers_bp.route('/view-pdf/<int:id>')
def view_pdf(id):
    paper = Paper.query.get_or_404(id)
    # Allow view if paper is public OR if logged-in user is the author or admin
    is_authorized = False
    if paper.visibility == 'public':
        is_authorized = True
    elif current_user.is_authenticated and (paper.user_id == current_user.id or current_user.is_admin):
        is_authorized = True

    if not is_authorized:
        flash('Unauthorized access to paper PDF.')
        return redirect(url_for('public.index'))

    if not paper.file_path or not os.path.exists(paper.file_path):
        flash('PDF manuscript file not found.')
        return redirect(request.referrer or url_for('public.index'))
    
    from utils import add_watermark_to_pdf
    watermarked_stream = add_watermark_to_pdf(
        paper.file_path,
        author_name=paper.author.username,
        publication_id=paper.publication_id or f"SF-2026-{paper.id:04d}"
    )
    if watermarked_stream:
        return send_file(watermarked_stream, mimetype='application/pdf')
    return send_file(paper.file_path, mimetype='application/pdf')

@papers_bp.route('/download-pdf/<int:id>')
def download_pdf(id):
    paper = Paper.query.get_or_404(id)
    is_authorized = False
    if paper.visibility == 'public':
        is_authorized = True
    elif current_user.is_authenticated and (paper.user_id == current_user.id or current_user.is_admin):
        is_authorized = True

    if not is_authorized:
        flash('Unauthorized access to download paper PDF.')
        return redirect(url_for('public.index'))

    if not paper.file_path or not os.path.exists(paper.file_path):
        flash('PDF manuscript file not found.')
        return redirect(request.referrer or url_for('public.index'))
    
    paper.downloads_count = (paper.downloads_count or 0) + 1
    db.session.commit()
    
    clean_title = secure_filename(paper.title) or f"paper_{paper.id}"
    download_filename = f"{clean_title}_ScholarForge.pdf"

    from utils import add_watermark_to_pdf
    watermarked_stream = add_watermark_to_pdf(
        paper.file_path,
        author_name=paper.author.username,
        publication_id=paper.publication_id or f"SF-2026-{paper.id:04d}"
    )
    if watermarked_stream:
        return send_file(watermarked_stream, mimetype='application/pdf', as_attachment=True, download_name=download_filename)
    return send_file(paper.file_path, mimetype='application/pdf', as_attachment=True, download_name=download_filename)
