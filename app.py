from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, send_from_directory
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import bcrypt
from PIL import Image, ImageEnhance
import os
import io
import requests
import logging
import zipfile
from datetime import datetime
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'supersecretmre'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'

UPLOAD_FOLDER = 'static/uploads'
CONVERTED_FOLDER = 'converted'
COMPRESSED_FOLDER = 'static/compressed'
ENHANCED_FOLDER = 'static/enhanced'  # Add enhanced folder
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CONVERTED_FOLDER'] = CONVERTED_FOLDER
app.config['COMPRESSED_FOLDER'] = COMPRESSED_FOLDER
app.config['ENHANCED_FOLDER'] = ENHANCED_FOLDER  # Configure enhanced folder

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)
os.makedirs(COMPRESSED_FOLDER, exist_ok=True)
os.makedirs(ENHANCED_FOLDER, exist_ok=True)  # Create enhanced directory

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

def enhance_image(input_path, output_path, brightness=1.0, contrast=1.0, sharpness=1.0):
    with Image.open(input_path) as img:
        # Apply brightness enhancement
        if brightness != 1.0:
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(brightness)
        
        # Apply contrast enhancement
        if contrast != 1.0:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(contrast)
        
        # Apply sharpness enhancement
        if sharpness != 1.0:
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(sharpness)
        
        img.save(output_path)

@app.route('/image_enhancement', methods=['GET'])
def image_enhancement_get():
    return render_template('image_enhancement.html')

@app.route('/image_enhancement', methods=['POST'])
def image_enhancement():
    if 'image' not in request.files:
        return redirect(request.url)

    file = request.files['image']
    if file.filename == '':
        return redirect(request.url)

    if file:
        filename = secure_filename(file.filename)
        original_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        enhanced_path = os.path.join(app.config['ENHANCED_FOLDER'], filename)

        file.save(original_path)

        # Get enhancement parameters from form
        brightness = float(request.form.get('brightness', 100)) / 100.0
        contrast = float(request.form.get('contrast', 100)) / 100.0
        sharpness = float(request.form.get('sharpness', 100)) / 100.0

        # Enhance the image
        enhance_image(original_path, enhanced_path, brightness, contrast, sharpness)

        original_size = round(os.path.getsize(original_path) / 1024, 2)
        enhanced_size = round(os.path.getsize(enhanced_path) / 1024, 2)

        return render_template('image_enhancement.html',
                            original=filename,
                            enhanced=filename,
                            original_size=original_size,
                            enhanced_size=enhanced_size)

@app.route('/web_url')
def web_url():
    return render_template('web_url.html')

@app.route('/convert_url_image', methods=['POST'])
def convert_url_image():
    if 'image_url' not in request.form:
        flash('No URL provided', 'error')
        return redirect(url_for('web_url'))
    
    image_url = request.form['image_url']
    try:
        # Download image from URL
        response = requests.get(image_url)
        if response.status_code != 200:
            flash('Failed to fetch image from URL', 'error')
            return redirect(url_for('web_url'))

        # Get original filename from URL
        url_path = urlparse(image_url).path
        original_filename = os.path.basename(url_path)
        if not original_filename:
            original_filename = 'image.jpg'

        # Convert to WebP
        output_filename = os.path.splitext(original_filename)[0] + '.webp'
        output_path = os.path.join(app.config['CONVERTED_FOLDER'], output_filename)
        
        # Open image from bytes and convert
        image = Image.open(io.BytesIO(response.content))
        image.save(output_path, 'WEBP')
        
        flash('Image successfully converted!', 'success')
        return render_template('web_url.html', converted_image=output_filename)

    except Exception as e:
        flash(f'Error processing image: {str(e)}', 'error')
        return redirect(url_for('web_url'))

def is_valid_url(url):
    """Checks if a URL is valid using regex."""
    import re
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None

def extract_images_from_url_selenium(url):
    """Extracts image URLs from a webpage using Selenium with Edge."""
    try:
        edge_options = Options()
        edge_options.add_argument("--headless")
        edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("--no-sandbox")

        service = Service(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=edge_options)

        driver.get(url)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        img_tags = soup.find_all('img')
        image_urls = [img['src'] for img in img_tags if img.get('src')]

        absolute_image_urls = []
        for image_url in image_urls:
            if image_url.startswith('http://') or image_url.startswith('https://'):
                absolute_image_urls.append(image_url)
            else:
                absolute_image_urls.append(urljoin(url, image_url))

        driver.quit()
        return absolute_image_urls
    except Exception as e:
        logger.error(f"Error fetching URL with Selenium: {e}")
        return []

@app.route('/extract-images', methods=['POST'])
def extract_images():
    url = request.form.get('url')
    if not url or not is_valid_url(url):
        flash('Please enter a valid URL', 'error')
        return redirect(url_for('web_url'))

    image_urls = extract_images_from_url_selenium(url)
    if not image_urls:
        flash('No images found on the webpage', 'error')
        return redirect(url_for('web_url'))

    return render_template('select_images.html', image_urls=image_urls)

@app.route('/convert-selected', methods=['POST'])
def convert_selected():
    selected_urls = request.form.getlist('selected_images')
    if not selected_urls:
        flash('Please select at least one image', 'error')
        return redirect(url_for('web_url'))

    # Create a zip file in memory
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for url in selected_urls:
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    # Get original filename from URL
                    url_path = urlparse(url).path
                    original_filename = os.path.basename(url_path)
                    if not original_filename:
                        original_filename = 'image.jpg'

                    # Convert to WebP
                    output_filename = os.path.splitext(original_filename)[0] + '.webp'
                    
                    # Open image from bytes and convert
                    image = Image.open(io.BytesIO(response.content))
                    
                    # Save as WebP in memory
                    img_byte_arr = io.BytesIO()
                    image.save(img_byte_arr, format='WEBP')
                    img_byte_arr = img_byte_arr.getvalue()
                    
                    # Add to zip
                    zipf.writestr(output_filename, img_byte_arr)
            except Exception as e:
                logger.error(f"Error converting image {url}: {e}")
                continue

    memory_file.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'converted_images_{timestamp}.zip'
    )

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)