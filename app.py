import os
import random
import string
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, redirect, url_for, flash, request, send_file, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Paper, Guide, Contributor, Certificate, Payment
from certificate_generator import (
    generate_certificate_id,
    generate_publication_id,
    generate_qr_code,
    generate_certificate_pdf,
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///scholarforge_v3.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@scholarforge.com')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join('static', 'certificates'), exist_ok=True)
os.makedirs(os.path.join('static', 'qrcodes'), exist_ok=True)

db.init_app(app)
mail = Mail(app)

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_required(f):
    """Decorator that restricts a route to admin users only."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# ──────────────────────────────────────────────
#  PUBLIC ROUTES
# ──────────────────────────────────────────────

@app.route('/')
def index():
    total_papers = Paper.query.filter_by(visibility='public', status='approved').count()
    total_users = User.query.count()
    total_certs = Certificate.query.count()
    return render_template(
        'index.html',
        total_papers=total_papers,
        total_users=total_users,
        total_certs=total_certs,
    )


@app.route('/explore')
def explore():
    """Browse all public, approved papers."""
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    query = Paper.query.filter_by(visibility='public', status='approved')
    if category:
        query = query.filter_by(category=category)
    papers = query.order_by(Paper.created_at.desc()).all()
    # Collect unique categories for the filter dropdown
    categories = db.session.query(Paper.category).filter_by(
        visibility='public', status='approved'
    ).distinct().all()
    categories = [c[0] for c in categories]
    return render_template('explore.html', papers=papers, categories=categories, selected_category=category)


@app.route('/paper/<int:id>')
def paper_detail(id):
    """Public paper detail view."""
    paper = Paper.query.get_or_404(id)
    # Only show public approved papers to non-owners
    if paper.visibility != 'public' or paper.status != 'approved':
        if not current_user.is_authenticated or (paper.user_id != current_user.id and not current_user.is_admin):
            abort(404)
    guide = paper.guides[0] if paper.guides else None
    contributors = paper.contributors
    return render_template('paper_detail.html', paper=paper, guide=guide, contributors=contributors)


@app.route('/search')
def search():
    query = request.args.get('q', '')
    if query:
        results = Paper.query.filter(
            (Paper.visibility == 'public'),
            (Paper.title.ilike(f'%{query}%')) |
            (Paper.abstract.ilike(f'%{query}%')) |
            (Paper.keywords.ilike(f'%{query}%'))
        ).all()
    else:
        results = []
    return render_template('search.html', query=query, results=results)


@app.route('/verify/<certificate_id>')
def verify_certificate(certificate_id):
    """Public certificate verification page."""
    cert = Certificate.query.filter_by(certificate_id=certificate_id).first_or_404()
    paper = cert.paper
    author = paper.author
    guide = paper.guides[0] if paper.guides else None
    return render_template(
        'verify.html',
        certificate=cert,
        paper=paper,
        author=author,
        guide=guide,
    )


@app.route('/verify', methods=['GET', 'POST'])
def verify_lookup():
    """Certificate verification lookup form."""
    if request.method == 'POST':
        cert_id = request.form.get('certificate_id', '').strip()
        if cert_id:
            cert = Certificate.query.filter_by(certificate_id=cert_id).first()
            if cert:
                return redirect(url_for('verify_certificate', certificate_id=cert_id))
            else:
                flash('No certificate found with that ID. Please check and try again.')
        else:
            flash('Please enter a certificate ID.')
    return render_template('verify_lookup.html')


@app.route('/about')
def about():
    """About ScholarForge page."""
    total_papers = Paper.query.filter_by(status='approved').count()
    total_users = User.query.count()
    total_certs = Certificate.query.count()
    return render_template(
        'about.html',
        total_papers=total_papers,
        total_users=total_users,
        total_certs=total_certs,
    )


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact page."""
    if request.method == 'POST':
        # In production, send email or store in DB
        flash('Thank you for your message! We\'ll get back to you within 24 hours.')
        return redirect(url_for('contact'))
    return render_template('contact.html')


# ──────────────────────────────────────────────
#  AUTH ROUTES
# ──────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'student')
        institution = request.form.get('institution')
        department = request.form.get('department')

        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email address already exists.')
            return redirect(url_for('register'))

        existing_username = User.query.filter_by(username=username).first()
        if existing_username:
            flash('Username already taken.')
            return redirect(url_for('register'))

        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password, method='pbkdf2:sha256'),
            role=role,
            institution=institution,
            department=department,
            otp=generate_otp(),
            otp_expiry=datetime.utcnow() + timedelta(minutes=10)
        )

        db.session.add(new_user)
        db.session.commit()

        # Send OTP email
        try:
            msg = Message("Verify Your Email - ScholarForge", recipients=[email])
            msg.body = f"Hello {username},\n\nYour verification code is: {new_user.otp}\nThis code will expire in 10 minutes.\n\nThank you!"
            mail.send(msg)
            flash('Registration successful! Please check your email for the verification code.')
        except Exception as e:
            print(f"Mail error: {e}")
            flash('Registration successful, but there was an error sending the verification email. Please try logging in and requesting a new code.')

        return redirect(url_for('verify_email', email=email))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            flash('Please check your login details and try again.')
            return redirect(url_for('login'))

        if not user.is_verified:
            if not user.otp_expiry or user.otp_expiry < datetime.utcnow():
                user.otp = generate_otp()
                user.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
                db.session.commit()
                try:
                    msg = Message("Verify Your Email - ScholarForge", recipients=[user.email])
                    msg.body = f"Hello {user.username},\n\nYour new verification code is: {user.otp}\nThis code will expire in 10 minutes.\n\nThank you!"
                    mail.send(msg)
                except Exception as e:
                    print(f"Mail resend error: {e}")
            flash('Please verify your email before logging in.')
            return redirect(url_for('verify_email', email=user.email))

        login_user(user, remember=remember)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('dashboard'))

    return render_template('login.html')

@app.route('/verify-email/<email>', methods=['GET', 'POST'])
def verify_email(email):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    user = User.query.filter_by(email=email).first_or_404()
    
    if user.is_verified:
        flash('Email is already verified. Please log in.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        otp = request.form.get('otp')
        
        if not user.otp or user.otp != otp:
            flash('Invalid OTP. Please try again.')
            return redirect(url_for('verify_email', email=email))
            
        if user.otp_expiry and user.otp_expiry < datetime.utcnow():
            flash('OTP has expired. Please request a new one.')
            return redirect(url_for('verify_email', email=email))
            
        user.is_verified = True
        user.otp = None
        user.otp_expiry = None
        db.session.commit()
        
        flash('Email verified successfully! You can now log in.')
        return redirect(url_for('login'))

    return render_template('verify_email.html', email=email)

@app.route('/resend-otp/<email>')
def resend_otp(email):
    user = User.query.filter_by(email=email).first_or_404()
    
    if user.is_verified:
        flash('Email is already verified.')
        return redirect(url_for('login'))
        
    user.otp = generate_otp()
    user.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
    db.session.commit()
    
    try:
        msg = Message("Verify Your Email - ScholarForge", recipients=[user.email])
        msg.body = f"Hello {user.username},\n\nYour new verification code is: {user.otp}\nThis code will expire in 10 minutes.\n\nThank you!"
        mail.send(msg)
        flash('A new OTP has been sent to your email.')
    except Exception as e:
        print(f"Mail resend error: {e}")
        flash('Error sending the verification email. Please try again later.')
        
    return redirect(url_for('verify_email', email=email))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            user.otp = generate_otp()
            user.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
            db.session.commit()
            
            try:
                msg = Message("Password Reset Request - ScholarForge", recipients=[user.email])
                msg.body = f"Hello {user.username},\n\nYour password reset code is: {user.otp}\nThis code will expire in 10 minutes.\n\nIf you did not request a password reset, please ignore this email."
                mail.send(msg)
            except Exception as e:
                print(f"Mail error: {e}")
                flash('There was an error sending the password reset email.')
                return redirect(url_for('forgot_password'))
                
        # Always show same message to prevent email enumeration
        flash('If an account with that email exists, we have sent a password reset code.')
        return redirect(url_for('reset_password', email=email))

    return render_template('forgot_password.html')

@app.route('/reset-password/<email>', methods=['GET', 'POST'])
def reset_password(email):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    user = User.query.filter_by(email=email).first()

    if request.method == 'POST':
        otp = request.form.get('otp')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not user:
            flash('Invalid request.')
            return redirect(url_for('login'))
            
        if not user.otp or user.otp != otp:
            flash('Invalid OTP. Please try again.')
            return redirect(url_for('reset_password', email=email))
            
        if user.otp_expiry and user.otp_expiry < datetime.utcnow():
            flash('OTP has expired. Please request a new one.')
            return redirect(url_for('forgot_password'))
            
        if new_password != confirm_password:
            flash('Passwords do not match.')
            return redirect(url_for('reset_password', email=email))
            
        if len(new_password) < 6:
            flash('Password must be at least 6 characters long.')
            return redirect(url_for('reset_password', email=email))
            
        user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
        user.otp = None
        user.otp_expiry = None
        db.session.commit()
        
        flash('Your password has been reset successfully. You can now log in.')
        return redirect(url_for('login'))

    return render_template('reset_password.html', email=email)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# ──────────────────────────────────────────────
#  DASHBOARD & PROFILE
# ──────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    paper_count = Paper.query.filter_by(user_id=current_user.id).count()
    approved_count = Paper.query.filter_by(user_id=current_user.id, status='approved').count()
    cert_count = Certificate.query.join(Paper).filter(Paper.user_id == current_user.id).count()
    return render_template(
        'dashboard.html',
        name=current_user.username,
        paper_count=paper_count,
        approved_count=approved_count,
        cert_count=cert_count,
    )


@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)


@app.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.username = request.form.get('username', current_user.username)
        current_user.institution = request.form.get('institution', current_user.institution)
        current_user.department = request.form.get('department', current_user.department)
        db.session.commit()
        flash('Profile updated successfully!')
        return redirect(url_for('profile'))
    return render_template('edit_profile.html', user=current_user)


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Allow user to change their password."""
    if request.method == 'POST':
        current_pw = request.form.get('current_password')
        new_pw = request.form.get('new_password')
        confirm_pw = request.form.get('confirm_password')

        if not check_password_hash(current_user.password, current_pw):
            flash('Current password is incorrect.')
            return redirect(url_for('change_password'))

        if new_pw != confirm_pw:
            flash('New passwords do not match.')
            return redirect(url_for('change_password'))

        if len(new_pw) < 6:
            flash('Password must be at least 6 characters long.')
            return redirect(url_for('change_password'))

        current_user.password = generate_password_hash(new_pw, method='pbkdf2:sha256')
        db.session.commit()
        flash('Password changed successfully!')
        return redirect(url_for('profile'))
    return render_template('change_password.html')


# ──────────────────────────────────────────────
#  PAPER MANAGEMENT
# ──────────────────────────────────────────────

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        title = request.form.get('title')
        abstract = request.form.get('abstract')
        category = request.form.get('category')
        keywords = request.form.get('keywords')
        visibility = request.form.get('visibility', 'public')

        # Guide details
        guide_name = request.form.get('guide_name')
        guide_designation = request.form.get('guide_designation')
        guide_department = request.form.get('guide_department')
        guide_institution = request.form.get('guide_institution')

        # File upload
        file = request.files.get('file')
        file_path = None
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{current_user.id}_{filename}")
            file.save(file_path)

        # Generate publication ID
        pub_id = generate_publication_id()

        new_paper = Paper(
            title=title, abstract=abstract, category=category,
            keywords=keywords, visibility=visibility, file_path=file_path,
            user_id=current_user.id, publication_id=pub_id, status='pending',
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

        # Handle contributors
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
        return redirect(url_for('my_publications'))

    return render_template('upload.html')


@app.route('/my-publications')
@login_required
def my_publications():
    papers = Paper.query.filter_by(user_id=current_user.id).order_by(Paper.created_at.desc()).all()
    return render_template('my_publications.html', papers=papers)


@app.route('/my-certificates')
@login_required
def my_certificates():
    """View all certificates owned by current user."""
    certs = Certificate.query.join(Paper).filter(Paper.user_id == current_user.id).order_by(Certificate.issue_date.desc()).all()
    return render_template('my_certificates.html', certificates=certs)


@app.route('/edit-paper/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_paper(id):
    paper = Paper.query.get_or_404(id)
    if paper.user_id != current_user.id:
        flash('Unauthorized access.')
        return redirect(url_for('my_publications'))

    if request.method == 'POST':
        paper.title = request.form.get('title')
        paper.abstract = request.form.get('abstract')
        paper.category = request.form.get('category')
        paper.keywords = request.form.get('keywords')
        paper.visibility = request.form.get('visibility')
        db.session.commit()
        flash('Paper updated successfully!')
        return redirect(url_for('my_publications'))

    return render_template('edit_paper.html', paper=paper)


@app.route('/delete-paper/<int:id>', methods=['POST'])
@login_required
def delete_paper(id):
    paper = Paper.query.get_or_404(id)
    if paper.user_id != current_user.id:
        flash('Unauthorized access.')
        return redirect(url_for('my_publications'))

    # Delete uploaded file if exists
    if paper.file_path and os.path.exists(paper.file_path):
        os.remove(paper.file_path)

    db.session.delete(paper)
    db.session.commit()
    flash('Paper deleted successfully!')
    return redirect(url_for('my_publications'))


@app.route('/view-pdf/<int:id>')
@login_required
def view_pdf(id):
    """Serve the uploaded paper PDF for in-browser viewing."""
    paper = Paper.query.get_or_404(id)
    # Allow owner or admin
    if paper.user_id != current_user.id and not current_user.is_admin:
        flash('Unauthorized access.')
        return redirect(url_for('my_publications'))
    if not paper.file_path or not os.path.exists(paper.file_path):
        flash('PDF file not found.')
        return redirect(url_for('my_publications'))
    return send_file(paper.file_path, mimetype='application/pdf')


# ──────────────────────────────────────────────
#  PAYMENT & CERTIFICATE
# ──────────────────────────────────────────────

@app.route('/payment/<int:paper_id>', methods=['GET', 'POST'])
@login_required
def payment(paper_id):
    paper = Paper.query.get_or_404(paper_id)
    if paper.user_id != current_user.id:
        flash('Unauthorized access.')
        return redirect(url_for('my_publications'))

    # Check if already paid
    if paper.payment and paper.payment.status == 'completed':
        flash('Payment already completed for this paper.')
        return redirect(url_for('my_publications'))

    if request.method == 'POST':
        # In a real app, integrate Stripe/Razorpay here.
        # For now, simulate a successful payment.
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

        # Auto-approve paper on payment
        paper.status = 'approved'
        db.session.commit()

        # Auto-generate certificate
        cert_id = generate_certificate_id()
        verify_url = url_for('verify_certificate', certificate_id=cert_id, _external=True)

        qr_filename = f"{cert_id}.png"
        qr_path = generate_qr_code(verify_url, qr_filename)

        guide = paper.guides[0] if paper.guides else None
        cert_pdf_path = generate_certificate_pdf(
            certificate_id=cert_id,
            paper_title=paper.title,
            author_name=current_user.username,
            publication_id=paper.publication_id,
            category=paper.category,
            institution=current_user.institution or '',
            guide_name=guide.name if guide else '',
            issue_date=datetime.utcnow(),
            verify_url=verify_url,
            qr_code_path=qr_path,
        )

        new_cert = Certificate(
            certificate_id=cert_id,
            qr_code_path=qr_path,
            file_path=cert_pdf_path,
            paper_id=paper.id,
        )
        db.session.add(new_cert)
        db.session.commit()

        flash('Payment successful! Your certificate has been generated.')
        return redirect(url_for('certificate_view', certificate_id=cert_id))

    return render_template('payment.html', paper=paper)


@app.route('/certificate/<certificate_id>')
@login_required
def certificate_view(certificate_id):
    """View certificate details and download link."""
    cert = Certificate.query.filter_by(certificate_id=certificate_id).first_or_404()
    paper = cert.paper
    if paper.user_id != current_user.id and not current_user.is_admin:
        flash('Unauthorized access.')
        return redirect(url_for('dashboard'))
    return render_template('certificate_view.html', certificate=cert, paper=paper)


@app.route('/download-certificate/<certificate_id>')
@login_required
def download_certificate(certificate_id):
    """Download the certificate PDF file."""
    cert = Certificate.query.filter_by(certificate_id=certificate_id).first_or_404()
    paper = cert.paper
    if paper.user_id != current_user.id and not current_user.is_admin:
        flash('Unauthorized access.')
        return redirect(url_for('dashboard'))
    if not cert.file_path or not os.path.exists(cert.file_path):
        flash('Certificate file not found.')
        return redirect(url_for('dashboard'))
    return send_file(
        cert.file_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"ScholarForge_Certificate_{certificate_id}.pdf",
    )


# ──────────────────────────────────────────────
#  ADMIN PANEL
# ──────────────────────────────────────────────

@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    total_users = User.query.count()
    total_papers = Paper.query.count()
    pending_papers = Paper.query.filter_by(status='pending').all()
    approved_papers = Paper.query.filter_by(status='approved').count()
    total_certs = Certificate.query.count()
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    return render_template(
        'admin.html',
        total_users=total_users,
        total_papers=total_papers,
        pending_papers=pending_papers,
        approved_papers=approved_papers,
        total_certs=total_certs,
        recent_users=recent_users,
    )


@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """Full user management page."""
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


@app.route('/admin/papers')
@login_required
@admin_required
def admin_papers():
    """Full paper management page."""
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


@app.route('/admin/approve/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_approve(id):
    paper = Paper.query.get_or_404(id)
    paper.status = 'approved'
    db.session.commit()
    flash(f'Paper "{paper.title}" approved.')
    next_url = request.form.get('next') or url_for('admin_panel')
    return redirect(next_url)


@app.route('/admin/reject/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_reject(id):
    paper = Paper.query.get_or_404(id)
    paper.status = 'rejected'
    db.session.commit()
    flash(f'Paper "{paper.title}" rejected.')
    next_url = request.form.get('next') or url_for('admin_panel')
    return redirect(next_url)


@app.route('/admin/make-admin/<int:id>', methods=['POST'])
@login_required
@admin_required
def make_admin(id):
    user = User.query.get_or_404(id)
    user.is_admin = True
    db.session.commit()
    flash(f'{user.username} is now an admin.')
    next_url = request.form.get('next') or url_for('admin_panel')
    return redirect(next_url)


@app.route('/admin/delete-user/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(id):
    """Delete a user and all their papers."""
    user = User.query.get_or_404(id)
    if user.is_admin:
        flash('Cannot delete an admin user.')
        return redirect(url_for('admin_users'))
    # Delete all user's paper files
    for paper in user.papers:
        if paper.file_path and os.path.exists(paper.file_path):
            os.remove(paper.file_path)
    db.session.delete(user)
    db.session.commit()
    flash(f'User "{user.username}" and all their data have been deleted.')
    return redirect(url_for('admin_users'))


@app.route('/admin/delete-paper/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_paper(id):
    """Admin can delete any paper."""
    paper = Paper.query.get_or_404(id)
    if paper.file_path and os.path.exists(paper.file_path):
        os.remove(paper.file_path)
    db.session.delete(paper)
    db.session.commit()
    flash(f'Paper "{paper.title}" deleted.')
    return redirect(url_for('admin_papers'))


# ──────────────────────────────────────────────
#  ERROR HANDLERS
# ──────────────────────────────────────────────

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(413)
def file_too_large(e):
    flash('File is too large. Maximum upload size is 16 MB.')
    return redirect(request.referrer or url_for('dashboard'))


# ──────────────────────────────────────────────
#  APP STARTUP
# ──────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create a default admin if none exists
        admin = User.query.filter_by(is_admin=True).first()
        if not admin:
            admin_user = User(
                username='admin',
                email='admin@scholarforge.com',
                password=generate_password_hash('admin123', method='pbkdf2:sha256'),
                role='admin',
                is_admin=True,
                is_verified=True,
            )
            db.session.add(admin_user)
            db.session.commit()
            print(" * Default admin created: admin@scholarforge.com / admin123")
    app.run(debug=True)
