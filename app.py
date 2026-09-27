import os
import secrets
import sqlite3

from flask import (Flask, flash, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Paths: always absolute. Under Apache the working directory is NOT this
# folder, so a relative path like 'users.db' would land somewhere else.
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'users.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
# Signs the session cookie so users cannot forge "I am logged in as X".
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(16)
# Reject uploads larger than 1 MB before they ever reach our code.
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row      # rows behave like dicts: user['email']
    return conn


def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                username          TEXT NOT NULL UNIQUE,
                password_hash     TEXT NOT NULL,
                firstname         TEXT NOT NULL,
                lastname          TEXT NOT NULL,
                email             TEXT NOT NULL,
                address           TEXT NOT NULL,
                filename          TEXT,
                original_filename TEXT,
                word_count        INTEGER
            )
        ''')


init_db()


def save_upload(file_storage, username):
    """Save an uploaded .txt file. Returns (stored_name, original_name, word_count)."""
    original = secure_filename(file_storage.filename)
    if not original.lower().endswith('.txt'):
        raise ValueError('Please upload a .txt file.')
    stored = f'{username}_{original}'          # one file per user, no collisions
    path = os.path.join(UPLOAD_DIR, stored)
    file_storage.save(path)
    with open(path, encoding='utf-8', errors='replace') as f:
        word_count = len(f.read().split())     # split() = split on any whitespace
    return stored, original, word_count


def current_user():
    username = session.get('username')
    if not username:
        return None
    with get_db() as conn:
        return conn.execute('SELECT * FROM users WHERE username = ?',
                            (username,)).fetchone()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    if session.get('username'):
        return redirect(url_for('profile'))
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html', form={})

    form = request.form
    fields = ['username', 'password', 'firstname', 'lastname', 'email', 'address']
    values = {f: form.get(f, '').strip() for f in fields}

    missing = [f for f in fields if not values[f]]
    if missing:
        flash('Please fill in every field.', 'error')
        return render_template('register.html', form=values), 400

    stored = original = word_count = None
    upload = request.files.get('file')
    if upload and upload.filename:
        try:
            stored, original, word_count = save_upload(upload, values['username'])
        except ValueError as e:
            flash(str(e), 'error')
            return render_template('register.html', form=values), 400

    try:
        with get_db() as conn:
            conn.execute(
                '''INSERT INTO users (username, password_hash, firstname, lastname,
                                      email, address, filename, original_filename,
                                      word_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (values['username'], generate_password_hash(values['password']),
                 values['firstname'], values['lastname'], values['email'],
                 values['address'], stored, original, word_count))
    except sqlite3.IntegrityError:               # UNIQUE(username) violated
        flash('That username is taken. Pick another.', 'error')
        return render_template('register.html', form=values), 400

    session['username'] = values['username']
    flash('Registration successful.', 'success')
    return redirect(url_for('profile'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    with get_db() as conn:
        user = conn.execute('SELECT * FROM users WHERE username = ?',
                            (username,)).fetchone()

    if user is None or not check_password_hash(user['password_hash'], password):
        flash('Invalid username or password.', 'error')
        return render_template('login.html'), 401

    session['username'] = username
    return redirect(url_for('profile'))


@app.route('/profile')
def profile():
    user = current_user()
    if user is None:
        flash('Please log in first.', 'error')
        return redirect(url_for('login'))
    return render_template('profile.html', user=user)


@app.route('/upload', methods=['POST'])
def upload():
    user = current_user()
    if user is None:
        return redirect(url_for('login'))
    f = request.files.get('file')
    if not f or not f.filename:
        flash('Choose a file first.', 'error')
        return redirect(url_for('profile'))
    try:
        stored, original, word_count = save_upload(f, user['username'])
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('profile'))
    with get_db() as conn:
        conn.execute('''UPDATE users SET filename = ?, original_filename = ?,
                        word_count = ? WHERE username = ?''',
                     (stored, original, word_count, user['username']))
    flash('File uploaded.', 'success')
    return redirect(url_for('profile'))


@app.route('/download')
def download():
    user = current_user()
    if user is None:
        return redirect(url_for('login'))
    if not user['filename']:
        flash('No file uploaded yet.', 'error')
        return redirect(url_for('profile'))
    return send_from_directory(UPLOAD_DIR, user['filename'], as_attachment=True,
                               download_name=user['original_filename'])


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'success')
    return redirect(url_for('login'))


@app.errorhandler(413)
def too_large(_e):
    flash('File too large (limit 1 MB).', 'error')
    return redirect(request.referrer or url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
