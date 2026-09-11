import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, send_from_directory

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
DB_FILE = 'database.db'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 🔒 고정 관리자 암호 설정 (원하시는 비밀번호로 변경하세요)
ADMIN_PASSWORD = '1234'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 게시글 테이블 (비밀번호 컬럼 불필요)
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
        cursor.execute('''
            INSERT INTO posts (user_id, author, content, filename) 
            VALUES (?, ?, ?, ?)
        ''', (0, author, content, filename))
        conn.commit()
        conn.close()
        
        return redirect(url_for('index'))
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, author, content, filename, created_at FROM posts ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()
    
    posts = [{'id': r[0], 'author': r[1], 'content': r[2], 'filename': r[3], 'time': r[4]} for r in rows]
    return render_template('index.html', posts=posts)

# 고정 관리자 암호로 삭제하는 라우트
@app.route('/delete/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    input_password = request.form.get('password', '')
    
    # 입력한 암호가 설정한 관리자 암호와 같을 때만 진행
    if input_password == ADMIN_PASSWORD:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT filename FROM posts WHERE id = ?', (post_id,))
        row = cursor.fetchone()
        
        if row:
            filename = row[0]
            if filename:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            cursor.execute('DELETE FROM posts WHERE id = ?', (post_id,))
            conn.commit()
        conn.close()
        
    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def downloaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
