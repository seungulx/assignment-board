import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash

app = Flask(__name__)
app.secret_key = 'super-secret-key-for-flash-messages'  # 암호 틀렸을 때 알림 띄우기용

UPLOAD_FOLDER = 'uploads'
DB_FILE = 'database.db'
ADMIN_PASSWORD = '0000'  # <-- 여기에 원하시는 관리자 비밀번호를 설정하세요!

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
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
        cursor.execute('INSERT INTO posts (user_id, author, content, filename) VALUES (?, ?, ?, ?)', (0, author, content, filename))
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

# 삭제 처리 라우트 (비밀번호 검증)
@app.route('/delete/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    entered_password = request.form.get('admin_password', '')
    
    if entered_password != ADMIN_PASSWORD:
        # 비밀번호가 틀리면 경고를 띄우기 위해 메인으로 리다이렉트 (실무에선 flash 메시지 사용)
        return "<script>alert('관리자 비밀번호가 틀렸습니다!'); history.back();</script>"
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 삭제할 파일이 있다면 서버 폴더에서도 실제 파일 삭제
    cursor.execute('SELECT filename FROM posts WHERE id = ?', (post_id,))
    row = cursor.fetchone()
    if row and row[0]:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], row[0])
        if os.path.exists(file_path):
            os.remove(file_path)
            
    # DB에서 게시글 데이터 삭제
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
