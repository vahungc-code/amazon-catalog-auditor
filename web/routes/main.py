import os
import uuid
import hashlib
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app

main_bp = Blueprint('main', __name__)


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def compute_sha256(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


@main_bp.route('/')
def index():
    return render_template('index.html')


@main_bp.route('/upload', methods=['POST'])
def upload_file():
    file = request.files.get('clr_file')
    if not file or file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('main.index'))

    if not allowed_file(file.filename):
        flash('Only .xlsx and .xlsm files are supported.', 'error')
        return redirect(url_for('main.index'))

    upload_id = str(uuid.uuid4())
    ext = file.filename.rsplit('.', 1)[1].lower()
    safe_filename = f"{upload_id}.{ext}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], safe_filename)
    file.save(filepath)

    file_hash = compute_sha256(filepath)

    session['upload'] = {
        'upload_id': upload_id,
        'original_filename': file.filename,
        'filepath': filepath,
        'file_hash': file_hash
    }

    return redirect(url_for('scan.scan_options', upload_id=upload_id))
