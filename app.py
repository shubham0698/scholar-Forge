import os
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Paper, Guide, Contributor, Certificate

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scholarforge_v3.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

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
            flash('Email address already exists')
            return redirect(url_for('register'))
            
        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password, method='pbkdf2:sha256'),
            role=role,
            institution=institution,
            department=department
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # In a real app, send email verification here
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
        
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
            
        login_user(user, remember=remember)
        return redirect(url_for('dashboard'))
        
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', name=current_user.username)

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/payment')
@login_required
def payment():
    return render_template('payment.html')

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
            
        new_paper = Paper(
            title=title, abstract=abstract, category=category, 
            keywords=keywords, visibility=visibility, file_path=file_path, 
            user_id=current_user.id
        )
        db.session.add(new_paper)
        db.session.commit()
        
        if guide_name:
            new_guide = Guide(
                name=guide_name, designation=guide_designation,
                department=guide_department, institution=guide_institution,
                paper_id=new_paper.id
            )
            db.session.add(new_guide)
            db.session.commit()
            
        flash('Paper uploaded successfully!')
        return redirect(url_for('my_publications'))
        
    return render_template('upload.html')

@app.route('/my-publications')
@login_required
def my_publications():
    papers = Paper.query.filter_by(user_id=current_user.id).all()
    return render_template('my_publications.html', papers=papers)

@app.route('/edit-paper/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_paper(id):
    paper = Paper.query.get_or_404(id)
    if paper.user_id != current_user.id:
        flash('Unauthorized access')
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
        flash('Unauthorized access')
        return redirect(url_for('my_publications'))
        
    db.session.delete(paper)
    db.session.commit()
    flash('Paper deleted successfully!')
    return redirect(url_for('my_publications'))

@app.route('/search')
def search():
    query = request.args.get('q', '')
    if query:
        # Search papers by title or abstract
        results = Paper.query.filter(
            (Paper.title.ilike(f'%{query}%')) | 
            (Paper.abstract.ilike(f'%{query}%'))
        ).all()
    else:
        results = []
    return render_template('search.html', query=query, results=results)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
