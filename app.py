import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, send_from_directory

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
DB_FILE = 'database.db'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # 게시글 테이블 (나중의 로그인 회원 아이디 연결을 대비한 user_id 포함)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 0,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 사용자 테이블 미리 선언 (미래 로그인 기능 대비)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        author = request.form.get('author', '익명')
        content = request.form.get('content', '')
        file = request.files.get('file')
        
        filename = ''
        if file and file.filename != '':
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO posts (user_id, author, content, filename) VALUES (?, ?, ?, ?)', (0, author, content, filename))
        conn.commit()
        conn.close()
        
        return redirect(url_for('index'))
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT author, content, filename, created_at FROM posts ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()
    
    posts = [{'author': r[0], 'content': r[1], 'filename': r[2], 'time': r[3]} for r in rows]
    return render_template('index.html', posts=posts)

@app.route('/uploads/<filename>')
def downloaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
