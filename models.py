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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    papers = db.relationship('Paper', backref='author', lazy=True)

class Paper(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    publication_id = db.Column(db.String(50), unique=True, nullable=True) # RN-2026-CS-0001
    title = db.Column(db.String(250), nullable=False)
    abstract = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    keywords = db.Column(db.String(250), nullable=False)
    status = db.Column(db.String(50), default='draft') # draft, pending, approved, rejected
    visibility = db.Column(db.String(50), default='public') # public, private
    file_path = db.Column(db.String(250), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    guides = db.relationship('Guide', backref='paper', lazy=True)
    contributors = db.relationship('Contributor', backref='paper', lazy=True)
    certificate = db.relationship('Certificate', backref='paper', uselist=False)

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
