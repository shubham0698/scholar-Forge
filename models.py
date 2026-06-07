from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), default='student') # student, guide, admin
    institution = db.Column(db.String(150), nullable=True)
    department = db.Column(db.String(100), nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    otp = db.Column(db.String(6), nullable=True)
    otp_expiry = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    papers = db.relationship('Paper', backref='author', lazy=True)
    payments = db.relationship('Payment', backref='user', lazy=True)

class Paper(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    publication_id = db.Column(db.String(50), unique=True, nullable=True) # SF-2026-0001
    title = db.Column(db.String(250), nullable=False)
    abstract = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    keywords = db.Column(db.String(250), nullable=False)
    status = db.Column(db.String(50), default='draft') # draft, pending, approved, rejected
    visibility = db.Column(db.String(50), default='public') # public, private
    file_path = db.Column(db.String(250), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    guides = db.relationship('Guide', backref='paper', lazy=True, cascade='all, delete-orphan')
    contributors = db.relationship('Contributor', backref='paper', lazy=True, cascade='all, delete-orphan')
    certificate = db.relationship('Certificate', backref='paper', uselist=False, cascade='all, delete-orphan')
    payment = db.relationship('Payment', backref='paper', uselist=False, cascade='all, delete-orphan')

class Guide(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    designation = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    institution = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=True)
    paper_id = db.Column(db.Integer, db.ForeignKey('paper.id'), nullable=False)

class Contributor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(100), nullable=False) # e.g., Research, UI Design
    affiliation = db.Column(db.String(150), nullable=True)
    paper_id = db.Column(db.Integer, db.ForeignKey('paper.id'), nullable=False)

class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    certificate_id = db.Column(db.String(100), unique=True, nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    qr_code_path = db.Column(db.String(250), nullable=True)
    file_path = db.Column(db.String(250), nullable=True)
    paper_id = db.Column(db.Integer, db.ForeignKey('paper.id'), nullable=False)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False, default=25.00)
    currency = db.Column(db.String(10), default='USD')
    status = db.Column(db.String(50), default='pending') # pending, completed, failed
    transaction_ref = db.Column(db.String(100), nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    paper_id = db.Column(db.Integer, db.ForeignKey('paper.id'), nullable=False)
