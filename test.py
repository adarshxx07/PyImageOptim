import logging
import os
import requests
from flask import Flask, request, send_from_directory, render_template, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
from PIL import Image
import io
from bs4 import BeautifulSoup
import shutil
import re
import zipfile  # Import the zipfile module
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads'
OUTPUT_FOLDER = 'static/output'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key')  # Get from env var

# Ensure upload and output directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_and_compress_to_webp(image, output_path, quality=80):
    """Converts an image to WebP format and compresses it.

    Args:
        image: PIL Image object
        output_path: Path to save the WebP image.
        quality: Quality setting for WebP compression (0-100, default is 80).
    """
    try:
        logger.info(f"Converting image to WebP: {output_path}")  # Use logger
        if image.mode not in ("RGB", "RGBA"):
           image = image.convert("RGB")

        image.save(output_path, "webp", quality=quality, optimize=True)
        logger.info(f"Successfully saved image to WebP: {output_path}")  # Use logger
        return True
    except FileNotFoundError:
        logger.error(f"Error: File not found during conversion")  # Use logger
        return False
    except OSError as e:
        logger.error(f"Error: Cannot open or read file during conversion: {e}")  # Use logger
        return False
    except Exception as e:
        logger.error(f"Error converting image: {e}")  # Use logger
        return False


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
                from urllib.parse import urljoin
                absolute_image_urls.append(urljoin(url, image_url))

        driver.quit()

        return absolute_image_urls
    except Exception as e:
        logger.error(f"Error fetching URL with Selenium: {e}")  # Use logger
        return []

def is_valid_url(url):
    """Checks if a URL is valid using regex."""
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'url':
            url = request.form.get('url')

            if not url:
                flash("Please enter a URL.", 'error')
                return render_template('index.html')

            if not is_valid_url(url):
                flash("Please enter a valid URL.", 'error')
                return render_template('index.html')

            image_urls = extract_images_from_url_selenium(url)  # Use Selenium

            if not image_urls:
                flash("No images found at that URL, or an error occurred.", 'error')
                return render_template('index.html')

            return render_template('select_images.html', image_urls=image_urls)

    return render_template('index.html')  # Always render the index page for GET requests


@app.route('/upload_images', methods=['POST'])
def upload_images():
    if request.method == 'POST':
        if 'files[]' not in request.files:  # Changed 'file' to 'files[]' for multiple files
            flash("No file part", 'error')
            return render_template('index.html')

        files = request.files.getlist('files[]')  # Changed 'file' to 'files[]' to get a list

        if not files or all(file.filename == '' for file in files):
            flash("No file selected", 'error')
            return render_template('index.html')

        image_paths = []  # Store paths to uploaded files
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(upload_path)
                image_paths.append(upload_path)
            else:
                flash(f"Invalid file type: {file.filename}", 'error')

        if not image_paths:
            return render_template('index.html')

        return render_template('select_images.html', image_urls=image_paths, is_local_file=True) #Add is_local_file=True

    return redirect(url_for('index'))  # Should not normally reach here, but redirect if it does.


@app.route('/compress', methods=['POST'])
def compress_images():
    selected_images = request.form.getlist('selected_images')
    is_local_file = request.form.get('is_local_file') == 'True'

    if not selected_images:
        flash("No images selected for compression.", 'error')
        return redirect(url_for('index'))  # Redirect back to the URL input page

    success_count = 0
    for image_url in selected_images:
        logger.info(f"Attempting to convert image: {image_url}")
        logger.info(f"is_local_file: {is_local_file}")

        try:
            # Check if it's a local file or URL
            if is_local_file:
                if not os.path.exists(image_url):
                    logger.error(f"Error: File does not exist at {image_url}")
                    flash(f"File does not exist: {image_url}", 'error')
                    continue  # Go to the next image, if applicable
                image = Image.open(image_url)  # Open directly from file path
                logger.info(f"Successfully opened image: {image_url}")  # Use logger
                logger.info(f"Image format: {image.format}") # Use logger
                logger.info(f"Image size: {image.size}")     # Use logger
                logger.info(f"Image mode: {image.mode}")     # Use logger
            else:
                # Download the image
                response = requests.get(image_url, stream=True, timeout=10)  #Add timeout
                response.raise_for_status() #Check status code, e.g. 200 OK
                image = Image.open(io.BytesIO(response.content))

            # Generate output filename and path
            filename = os.path.basename(image_url)
            name, ext = os.path.splitext(filename)
            output_filename = secure_filename(name) + ".webp"
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
            logger.info(f"Image will be saved to: {output_path}")  # Use logger

            # Convert and compress
            if convert_and_compress_to_webp(image, output_path):  # Pass the PIL image object
                success_count += 1
                logger.info(f"Successfully converted image: {image_url}") # Use logger
            else:
                logger.warning(f"Conversion failed for {image_url}")  # Use logger
                flash(f"Conversion failed for {os.path.basename(image_url)}", 'error')

            # Remove the original uploaded file after successful conversion (if it was uploaded)
            if is_local_file:
                try:
                    os.remove(image_url)
                except OSError as e:
                    logger.error(f"Error deleting uploaded file {image_url}: {e}")  # Use logger
                    flash(f"Error deleting original file: {os.path.basename(image_url)}", 'error')

        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading image {image_url}: {e}")  # Use logger
            flash(f"Error downloading {os.path.basename(image_url)}", 'error')
        except FileNotFoundError:
            logger.error(f"Error: File not found {image_url}")  # Use logger
            flash(f"Error: File not found {os.path.basename(image_url)}", 'error')
        except OSError as e:
            logger.error(f"Error:  Cannot open or read file {image_url}: {e}")  # Use logger
            flash(f"Error: Cannot open {os.path.basename(image_url)}", 'error')
        except Exception as e:
            logger.error(f"Error processing image {image_url}: {e}")  # Use logger
            flash(f"Error processing {os.path.basename(image_url)}", 'error')


    if success_count > 0:
        flash(f"{success_count} images successfully converted!", 'success')
        return redirect(url_for('download_files'))
    else:
        flash("No images were successfully converted.", 'error')
        return redirect(url_for('index'))  # Redirect back to URL input


@app.route('/downloads')
def download_files():
    output_files = os.listdir(app.config['OUTPUT_FOLDER'])
    return render_template('downloads.html', files=output_files)


@app.route('/downloads/<filename>')
def download_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)

@app.route('/download_all_zip', methods=['POST'])
def download_all_zip():
    """Downloads all files in the output directory as a zip file."""
    output_dir = app.config['OUTPUT_FOLDER']
    output_files = os.listdir(output_dir)

    if not output_files:
        flash("No files available for download.", 'error')
        return redirect(url_for('download_files'))

    # Create a zip file in memory
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in output_files:
            file_path = os.path.join(output_dir, file)
            zipf.write(file_path, file)  # Add file to zip with its original name

    memory_file.seek(0)  # Reset the file pointer to the beginning

    # Generate a filename for the zip file (using timestamp)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"compressed_images_{timestamp}.zip"

    # Return the zip file as a response
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=zip_filename
    )


@app.route('/resize_image', methods=['POST'])
def resize_image():
    """Resizes an uploaded image to a selected resolution."""
    if request.method == 'POST':
        if 'resize_file' not in request.files:
            flash("No file part", 'error')
            return redirect(url_for('index'))

        file = request.files['resize_file']

        if file.filename == '':
            flash("No file selected", 'error')
            return redirect(url_for('index'))

        if file and allowed_file(file.filename):
            try:
                filename = secure_filename(file.filename)
                image = Image.open(io.BytesIO(file.read())) # Read image into memory

                resolution = request.form['resolution']

                if resolution == 'custom':
                    try:
                        width = int(request.form['custom_width'])
                        height = int(request.form['custom_height'])
                        if width <= 0 or height <= 0:
                             raise ValueError("Width and height must be positive integers.")

                    except ValueError as e:
                        flash(f"Invalid custom size: {e}", 'error')
                        return redirect(url_for('index'))
                else:
                    width, height = map(int, resolution.split('x'))

                # Resize the image
                resized_image = image.resize((width, height), Image.LANCZOS)  # Use LANCZOS for good quality

                # Save the resized image to the output folder
                output_filename = f"resized_{width}x{height}_{filename}"
                output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)

                resized_image.save(output_path)

                flash("Image resized successfully!", 'success')
                return redirect(url_for('download_files'))

            except Exception as e:
                logger.error(f"Error resizing image: {e}")
                flash(f"Error resizing image: {e}", 'error')
                return redirect(url_for('index'))
        else:
            flash("Invalid file type", 'error')
            return redirect(url_for('index'))


@app.route('/clear_output')
def clear_output():
    """Clears the output directory."""
    for filename in os.listdir(app.config['OUTPUT_FOLDER']):
        file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)  # Remove the file
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)  # Remove the directory if necessary
        except Exception as e:
            logger.error(f'Failed to delete {file_path}. Reason: {e}')

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)