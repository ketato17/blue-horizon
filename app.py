import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
import os
import glob
from bs4 import BeautifulSoup

app = Flask(__name__, static_folder='.')
app.secret_key = 'your_secret_key_here'
DATABASE = 'site.db'

# --- DATABASE SETUP ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT,
            name TEXT,
            surname TEXT,
            bio TEXT,
            is_admin INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            question TEXT,
            answer TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        ''')
        # Create default admin if not exists
        cur = db.execute("SELECT * FROM users WHERE email=?", ("admin@example.com",))
        if not cur.fetchone():
            db.execute("INSERT INTO users (username, email, password_hash, name, surname, bio, is_admin) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("admin", "admin@example.com", generate_password_hash("admin123"), "Admin", "User", "Site admin", 1))
        db.commit()

# --- USER AUTH ---
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        name = request.form.get('name', '')
        surname = request.form.get('surname', '')
        bio = request.form.get('bio', '')
        db = get_db()
        try:
            db.execute("INSERT INTO users (username, email, password_hash, name, surname, bio) VALUES (?, ?, ?, ?, ?, ?)",
                (username, email, generate_password_hash(password), name, surname, bio))
            db.commit()
            flash('Sign up successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists.', 'danger')
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['is_admin'] = user['is_admin']
            flash('Logged in successfully!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('login'))

# --- PROFILE ---
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
    if request.method == 'POST':
        name = request.form.get('name', '')
        surname = request.form.get('surname', '')
        bio = request.form.get('bio', '')
        db.execute("UPDATE users SET name=?, surname=?, bio=? WHERE id=?", (name, surname, bio, session['user_id']))
        db.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=user)

# --- ADMIN: VIEW & ANSWER QUESTIONS ---
@app.route('/admin/questions', methods=['GET', 'POST'])
def admin_questions():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    db = get_db()
    if request.method == 'POST':
        qid = request.form['qid']
        answer = request.form['answer']
        db.execute("UPDATE questions SET answer=?, status='answered' WHERE id=?", (answer, qid))
        db.commit()
        flash('Answer sent!', 'success')
    questions = db.execute("SELECT q.*, u.email FROM questions q JOIN users u ON q.user_id=u.id WHERE q.status='pending' OR q.status='answered' ORDER BY q.id DESC").fetchall()
    return render_template('admin_questions.html', questions=questions)

# --- HOME PAGE ---
@app.route('/')
def home():
    return render_template('index.html')

# --- NEW ROUTES ---
@app.route('/reviews')
def reviews():
    return render_template('reviews.html')

@app.route('/todo')
def todo():
    return render_template('todo.html')

@app.route('/places')
def places():
    return render_template('places.html')

@app.route('/my-questions')
def my_questions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    questions = db.execute("SELECT * FROM questions WHERE user_id=? ORDER BY id DESC", (session['user_id'],)).fetchall()
    return render_template('my_questions.html', questions=questions)

@app.route('/search')
def search():
    query = request.args.get('q', '').lower()
    results = []
    # Search all HTML files in templates
    for filepath in glob.glob('templates/*.html'):
        filename = os.path.basename(filepath)
        with open(filepath, encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
            # Get all visible text as a single string
            visible_text = soup.get_text(separator='\n', strip=True)
            # Split into lines for context
            for line in visible_text.split('\n'):
                if query in line.lower() and line.strip():
                    results.append({'file': filename, 'snippet': line.strip()})
    return render_template('search_results.html', query=query, results=results)

@app.route('/admin/create-file', methods=['GET', 'POST'])
def create_file():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        filename = request.form['filename']
        content = request.form['content']
        with open(f'static/{filename}', 'w', encoding='utf-8') as f:
            f.write(content)
        flash('File created!', 'success')
    return render_template('create_file.html')

# --- INIT DB IF NEEDED ---
if not os.path.exists(DATABASE):
    init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
