import os
import uuid

from flask import Flask, render_template, request, redirect, url_for
import psycopg2
from supabase import create_client, Client

app = Flask(__name__)

# =========================================================
# Supabase 설정
# =========================================================

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL",
    "https://abytfhtylcsaykczjpgg.supabase.co"
)

SUPABASE_KEY = os.environ.get(
    "SUPABASE_PUBLISHABLE_KEY",
    "sb_publishable_GfxJ2pWNAnd55GmHCOjG5w_eHVVyw6a"
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres.abytfhtylcsaykczjpgg:seunguk0130!@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"
)

# 관리자 비밀번호
ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "1234"
)

# Supabase 연결
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================================================
# 데이터베이스 초기화
# =========================================================

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
            storage_path TEXT,
            file_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    cursor.close()
    conn.close()


# =========================================================
# 메인 페이지
# =========================================================

@app.route('/', methods=['GET', 'POST'])
def index():

    # -----------------------------------------------------
    # 게시글 작성
    # -----------------------------------------------------
    if request.method == 'POST':

        author = request.form.get(
            'author',
            '익명'
        )

        content = request.form.get(
            'content',
            ''
        )

        file = request.files.get('file')

        filename = ''
        storage_path = ''
        file_url = ''

        # -------------------------------------------------
        # 파일 업로드
        # -------------------------------------------------

        if file and file.filename != '':

            # 사용자가 올린 원래 파일 이름
            filename = file.filename

            # UUID를 이용해서 고유한 Storage 파일명 생성
            storage_path = f"{uuid.uuid4()}_{filename}"

            # 파일 읽기
            file_bytes = file.read()

            # Supabase Storage 업로드
            supabase.storage.from_('uploads').upload(
                path=storage_path,
                file=file_bytes,
                file_options={
                    "content-type": file.content_type or "application/octet-stream",
                    "upsert": "false"
                }
            )

            # 공개 URL 생성
            file_url = supabase.storage.from_(
                'uploads'
            ).get_public_url(storage_path)

        # -------------------------------------------------
        # 게시글 DB 저장
        # -------------------------------------------------

        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO posts (
                user_id,
                author,
                content,
                filename,
                storage_path,
                file_url
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            0,
            author,
            content,
            filename,
            storage_path,
            file_url
        ))

        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for('index'))

    # -----------------------------------------------------
    # 게시글 가져오기
    # -----------------------------------------------------

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            id,
            author,
            content,
            filename,
            file_url,
            created_at
        FROM posts
        ORDER BY id DESC
    ''')

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    # -----------------------------------------------------
    # HTML에 전달할 데이터 생성
    # -----------------------------------------------------

    posts = []

    for r in rows:

        posts.append({
            'id': r[0],
            'author': r[1],
            'content': r[2],
            'filename': r[3],
            'file_url': r[4],
            'time': r[5].strftime(
                '%Y-%m-%d %H:%M:%S'
            ) if r[5] else ''
        })

    return render_template(
        'index.html',
        posts=posts
    )


# =========================================================
# 게시글 삭제
# =========================================================

@app.route('/delete/<int:post_id>', methods=['POST'])
def delete_post(post_id):

    input_password = request.form.get(
        'password',
        ''
    )

    # 관리자 비밀번호 확인
    if input_password != ADMIN_PASSWORD:
        return redirect(url_for('index'))

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # 게시글의 실제 Storage 경로 가져오기
    cursor.execute('''
        SELECT storage_path
        FROM posts
        WHERE id = %s
    ''', (post_id,))

    row = cursor.fetchone()

    if row:

        storage_path = row[0]

        # Supabase Storage 파일 삭제
        if storage_path:

            try:
                supabase.storage.from_(
                    'uploads'
                ).remove([storage_path])

            except Exception as e:
                print(
                    "Storage 파일 삭제 오류:",
                    e
                )

        # DB에서 게시글 삭제
        cursor.execute('''
            DELETE FROM posts
            WHERE id = %s
        ''', (post_id,))

        conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('index'))


# =========================================================
# 서버 실행
# =========================================================

if __name__ == '__main__':

    init_db()

    port = int(
        os.environ.get(
            'PORT',
            5000
        )
    )

    app.run(
        host='0.0.0.0',
        port=port
    )
