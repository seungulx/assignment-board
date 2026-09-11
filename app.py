import os
from flask import Flask, render_template, request, redirect, url_for
import psycopg2
from supabase import create_client, Client

app = Flask(__name__)

# 🔒 Supabase 환경 변수 설정 (Render Environment 변수에 등록하거나 직접 입력)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "sb_publishable_GfxJ2pWNAnd55GmHCOjG5w_eHVVyw6a")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "https://abytfhtylcsaykczjpgg.supabase.co")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:[YOUR-PASSWORD]@db.abytfhtylcsaykczjpgg.supabase.co:5432/postgres")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
ADMIN_PASSWORD = '1234'

def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER DEFAULT 0,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            filename TEXT,
            file_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        author = request.form.get('author', '익명')
        content = request.form.get('content', '')
        file = request.files.get('file')

        filename = ''
        file_url = ''
        
        if file and file.filename != '':
            filename = file.filename
            file_bytes = file.read()
            
            # Supabase Storage에 파일 업로드
            response = supabase.storage.from_('uploads').upload(
                path=filename,
                file=file_bytes,
                file_options={"content-type": file.content_type, "upsert": "true"}
            )
            # 공개 다운로드 URL 가져오기
            file_url = supabase.storage.from_('uploads').get_public_url(filename)

        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO posts (user_id, author, content, filename, file_url) 
            VALUES (%s, %s, %s, %s, %s)
        ''', (0, author, content, filename, file_url))
        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('index'))

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('SELECT id, author, content, filename, file_url, created_at FROM posts ORDER BY id DESC')
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    posts = [{
        'id': r[0], 'author': r[1], 'content': r[2], 
        'filename': r[3], 'file_url': r[4], 'time': r[5].strftime('%Y-%m-%d %H:%M:%S') if r[5] else ''
    } for r in rows]
    
    return render_template('index.html', posts=posts)

@app.route('/delete/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    input_password = request.form.get('password', '')

    if input_password == ADMIN_PASSWORD:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('SELECT filename FROM posts WHERE id = %s', (post_id,))
        row = cursor.fetchone()

        if row:
            filename = row[0]
            if filename:
                # Supabase Storage에서 파일 삭제
                supabase.storage.from_('uploads').remove([filename])

            cursor.execute('DELETE FROM posts WHERE id = %s', (post_id,))
            conn.commit()
        cursor.close()
        conn.close()

    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
