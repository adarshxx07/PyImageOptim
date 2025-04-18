from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file  # Add this import for file downloads
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import bcrypt
from PIL import Image  # Add this import for image processing
import os
import io

app = Flask(__name__)
app.secret_key = 'supersecretmre'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'

UPLOAD_FOLDER = 'uploads'
CONVERTED_FOLDER = 'converted'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CONVERTED_FOLDER'] = CONVERTED_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"
    
    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def check_password(self, password):
        return bcrypt.checkpw(self.password.encode("utf-8"), password.encode("utf-8"))
    
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first()
        if user:
                flash('Username or email already exists', 'danger')
                return render_template('login.html')

        else:
            new_user = User(username=username, email=email, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash('Signup successful', 'success')
            return redirect(url_for('login'))
    return render_template('login.html')
    

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first() or User.query.filter_by(email=username).first()
        if user and user.check_password(password):
            flash('Login successful', 'success')
            session['user'] = user.username
            return redirect(url_for('index'))
        else:
            flash('Login failed', 'danger')
    return render_template('login.html')

@app.route('/image-converter', methods=['GET', 'POST'])
def image_converter():
    if request.method == 'POST':
        # Handle file uploads
        if 'images' in request.files:
            files = request.files.getlist('images')
            converted_files = []
            for file in files:
                if file.filename == '':
                    continue
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                # Convert to WebP
                img = Image.open(filepath)
                webp_filename = os.path.splitext(filename)[0] + '.webp'
                webp_filepath = os.path.join(app.config['CONVERTED_FOLDER'], webp_filename)
                img.save(webp_filepath, 'webp')

                converted_files.append(webp_filepath)

            # Provide download links for converted files
            return render_template('image_converter.html', converted_files=converted_files)

        # Handle URL fetching (to be implemented)
        # Handle compression and enhancement (to be implemented)

    return render_template('image_converter.html')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)