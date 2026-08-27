from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

from extensions import db, mail
from models import User
from utils import generate_otp

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'student')
        institution = request.form.get('institution')
        department = request.form.get('department')
        agree_terms = request.form.get('agree_terms')

        if not agree_terms:
            flash('You must agree to the Terms of Service & User Agreement and Privacy Policy before creating an account.')
            return redirect(url_for('auth.register'))

        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email address already exists.')
            return redirect(url_for('auth.register'))

        existing_username = User.query.filter_by(username=username).first()
        if existing_username:
            flash('Username already taken.')
            return redirect(url_for('auth.register'))

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

        try:
            msg = Message("Verify Your Email - ScholarForge", recipients=[email])
            msg.body = f"Hello {username},\n\nYour verification code is: {new_user.otp}\nThis code will expire in 10 minutes.\n\nThank you!"
            mail.send(msg)
            flash('Registration successful! Please check your email for the verification code.')
        except Exception as e:
            print(f"Mail error: {e}")
            flash('Registration successful, but there was an error sending the verification email. Please try logging in and requesting a new code.')

        return redirect(url_for('auth.verify_email', email=email))

    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            flash('Please check your login details and try again.')
            return redirect(url_for('auth.login'))

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
            return redirect(url_for('auth.verify_email', email=user.email))

        login_user(user, remember=remember)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('dashboard.dashboard'))

    return render_template('login.html')

@auth_bp.route('/verify-email/<email>', methods=['GET', 'POST'])
def verify_email(email):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    
    user = User.query.filter_by(email=email).first_or_404()
    
    if user.is_verified:
        flash('Email is already verified. Please log in.')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        otp = request.form.get('otp')
        
        if not user.otp or user.otp != otp:
            flash('Invalid OTP. Please try again.')
            return redirect(url_for('auth.verify_email', email=email))
            
        if user.otp_expiry and user.otp_expiry < datetime.utcnow():
            flash('OTP has expired. Please request a new one.')
            return redirect(url_for('auth.verify_email', email=email))
            
        user.is_verified = True
        user.otp = None
        user.otp_expiry = None
        db.session.commit()
        
        flash('Email verified successfully! You can now log in.')
        return redirect(url_for('auth.login'))

    return render_template('verify_email.html', email=email)

@auth_bp.route('/resend-otp/<email>')
def resend_otp(email):
    user = User.query.filter_by(email=email).first_or_404()
    
    if user.is_verified:
        flash('Email is already verified.')
        return redirect(url_for('auth.login'))
        
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
        
    return redirect(url_for('auth.verify_email', email=email))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

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
                return redirect(url_for('auth.forgot_password'))
                
        flash('If an account with that email exists, we have sent a password reset code.')
        return redirect(url_for('auth.reset_password', email=email))

    return render_template('forgot_password.html')

@auth_bp.route('/reset-password/<email>', methods=['GET', 'POST'])
def reset_password(email):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    user = User.query.filter_by(email=email).first()

    if request.method == 'POST':
        otp = request.form.get('otp')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not user:
            flash('Invalid request.')
            return redirect(url_for('auth.login'))
            
        if not user.otp or user.otp != otp:
            flash('Invalid OTP. Please try again.')
            return redirect(url_for('auth.reset_password', email=email))
            
        if user.otp_expiry and user.otp_expiry < datetime.utcnow():
            flash('OTP has expired. Please request a new one.')
            return redirect(url_for('auth.forgot_password'))
            
        if new_password != confirm_password:
            flash('Passwords do not match.')
            return redirect(url_for('auth.reset_password', email=email))
            
        if len(new_password) < 6:
            flash('Password must be at least 6 characters long.')
            return redirect(url_for('auth.reset_password', email=email))
            
        user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
        user.otp = None
        user.otp_expiry = None
        db.session.commit()
        
        flash('Your password has been reset successfully. You can now log in.')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', email=email)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('public.index'))
