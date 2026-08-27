import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, flash, redirect, url_for
from werkzeug.security import generate_password_hash

from extensions import db, login_manager, mail
from models import User

from routes.public import public_bp
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.papers import papers_bp
from routes.payments import payments_bp
from routes.admin import admin_bp
from routes.reviews import reviews_bp

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///scholarforge_v3.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

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
mail.init_app(app)

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

app.register_blueprint(public_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(papers_bp)
app.register_blueprint(payments_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(reviews_bp)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(413)
def file_too_large(e):
    flash('File is too large. Maximum upload size is 16 MB.')
    return redirect(request.referrer or url_for('dashboard.dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
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
