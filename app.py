from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, send_from_directory  # Add this import for file downloads
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import bcrypt
from PIL import Image  # Add this import for image processing
import os
import io

app = Flask(__name__)
app.secret_key = 'supersecretmre'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'

UPLOAD_FOLDER = 'static/uploads'
CONVERTED_FOLDER = 'converted'
COMPRESSED_FOLDER = 'static/compressed'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CONVERTED_FOLDER'] = CONVERTED_FOLDER
app.config['COMPRESSED_FOLDER'] = COMPRESSED_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)
os.makedirs(COMPRESSED_FOLDER, exist_ok=True)

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
        user = User.query.filter_by(username=username).first()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/converted/<filename>')
def converted_file(filename):
    return send_from_directory(app.config['CONVERTED_FOLDER'], filename)

@app.route('/image_converter', methods=['GET', 'POST'])
def image_converter():
    if request.method == 'POST':
        if 'image' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['image']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)

        if file:
            filename = secure_filename(file.filename)
            # Save original file
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Convert to WebP
            output_filename = os.path.splitext(filename)[0] + '.webp'
            output_path = os.path.join(app.config['CONVERTED_FOLDER'], output_filename)
            
            with Image.open(file_path) as img:
                img.save(output_path, 'WEBP')
            
            flash('Image successfully converted to WebP!', 'success')
            return render_template('image_converter.html', 
                                original=filename,
                                converted=output_filename)
    
    return render_template('image_converter.html')

@app.route('/image_compression', methods=['GET'])
def image_compression_get():
    return render_template('image_compression.html')

@app.route('/image_compression', methods=['POST'])
def image_compression():
    if 'image' not in request.files:
        return redirect(request.url)

    file = request.files['image']
    if file.filename == '':
        return redirect(request.url)

    if file:
        original_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        compressed_path = os.path.join(app.config['COMPRESSED_FOLDER'], file.filename)

        file.save(original_path)

        # Get quality from form, default to 60 if not provided
        quality = request.form.get('quality', 60, type=int)

        # Compress the image
        compress_image(original_path, compressed_path, quality=quality)

        original_size = round(os.path.getsize(original_path) / 1024, 2)
        compressed_size = round(os.path.getsize(compressed_path) / 1024, 2)

        return render_template('image_compression.html',
                               original=file.filename,
                               compressed=file.filename,
                               original_size=original_size,
                               compressed_size=compressed_size)
def compress_image(input_path, output_path, quality=60):
    from PIL import Image
    with Image.open(input_path) as img:
        img.save(output_path, optimize=True, quality=quality)
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)