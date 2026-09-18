import os
import uuid
from datetime import timedelta
import urllib.request
import urllib.parse

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    Response,
    stream_with_context,
    session
)

import psycopg2
from supabase import create_client, Client


app = Flask(__name__)


# =========================================================
# Flask 세션 설정
# =========================================================

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "change-this-secret-key"
)

app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)


# =========================================================
# Supabase 설정
# =========================================================

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL"
)

SUPABASE_KEY = os.environ.get(
    "SUPABASE_PUBLISHABLE_KEY"
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL"
)


# =========================================================
# 관리자 비밀번호
# 게시글 삭제에 사용
# =========================================================

ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "1234"
)


# =========================================================
# Supabase 연결
# =========================================================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================================================
# 데이터베이스 연결
# =========================================================

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


# =========================================================
# 데이터베이스 초기화
# =========================================================

def init_db():

    conn = get_db_connection()
    cursor = conn.cursor()

    # -----------------------------------------------------
    # 게시글 테이블
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # 사이트 비밀번호 테이블
    # -----------------------------------------------------

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS site_settings (
            id INTEGER PRIMARY KEY,
            site_password TEXT NOT NULL
        )
    ''')


    # -----------------------------------------------------
    # 사이트 비밀번호가 아직 없으면 기본값 생성
    # -----------------------------------------------------

    cursor.execute('''
        SELECT id
        FROM site_settings
        WHERE id = 1
    ''')

    row = cursor.fetchone()


    if not row:

        # Render 환경변수 SITE_PASSWORD가 있으면 사용
        # 없으면 임시 기본 비밀번호 사용
        default_password = os.environ.get(
            "SITE_PASSWORD",
            "1234"
        )

        cursor.execute('''
            INSERT INTO site_settings (
                id,
                site_password
            )
            VALUES (%s, %s)
        ''', (
            1,
            default_password
        ))


    conn.commit()

    cursor.close()
    conn.close()


# =========================================================
# 사이트 비밀번호 확인
# =========================================================

def check_site_password(password):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT site_password
        FROM site_settings
        WHERE id = 1
    ''')

    row = cursor.fetchone()

    cursor.close()
    conn.close()


    if row and password == row[0]:
        return True

    return False


# =========================================================
# 로그인 여부 확인
# =========================================================

def is_logged_in():

    return session.get(
        "site_authenticated",
        False
    )


# =========================================================
# 로그인 페이지
# =========================================================

@app.route(
    '/login',
    methods=['GET', 'POST']
)
def login():

    # 이미 로그인되어 있으면 게시판으로 이동
    if is_logged_in():

        return redirect(
            url_for('index')
        )


    # 로그인 시도
    if request.method == 'POST':

        password = request.form.get(
            'password',
            ''
        )


        # 비밀번호 확인
        if check_site_password(password):

            session.permanent = True

            session[
                'site_authenticated'
            ] = True

            return redirect(
                url_for('index')
            )


        return render_template(
            'login.html',
            error='비밀번호가 틀렸습니다.'
        )


    return render_template(
        'login.html'
    )


# =========================================================
# 로그아웃
# =========================================================

@app.route('/logout')
def logout():

    session.pop(
        'site_authenticated',
        None
    )

    return redirect(
        url_for('login')
    )


# =========================================================
# 메인 페이지
# =========================================================

@app.route(
    '/',
    methods=['GET', 'POST']
)
def index():

    # -----------------------------------------------------
    # 로그인 확인
    # -----------------------------------------------------

    if not is_logged_in():

        return redirect(
            url_for('login')
        )


    # =====================================================
    # 게시글 작성
    # =====================================================

    if request.method == 'POST':

        author = request.form.get(
            'author',
            '익명'
        )

        content = request.form.get(
            'content',
            ''
        )

        file = request.files.get(
            'file'
        )


        filename = ''
        storage_path = ''
        file_url = ''


        # =================================================
        # 파일 업로드
        # =================================================

        if file and file.filename != '':

            # 사용자가 올린 원래 파일 이름
            filename = file.filename


            # 확장자 추출
            ext = os.path.splitext(
                filename
            )[1]


            # Supabase Storage에 저장할 실제 이름
            storage_path = (
                f"{uuid.uuid4()}{ext}"
            )


            # 파일 읽기
            file_bytes = file.read()


            # Supabase Storage 업로드
            supabase.storage.from_(
                'uploads'
            ).upload(
                path=storage_path,
                file=file_bytes,
                file_options={
                    "content-type":
                        file.content_type
                        or
                        "application/octet-stream",

                    "upsert": "false"
                }
            )


            # 공개 URL 생성
            file_url = (
                supabase
                .storage
                .from_('uploads')
                .get_public_url(
                    storage_path
                )
            )


        # =================================================
        # 게시글 DB 저장
        # =================================================

        conn = get_db_connection()
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
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
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


        return redirect(
            url_for('index')
        )


    # =====================================================
    # 게시글 가져오기
    # =====================================================

    conn = get_db_connection()
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


    # =====================================================
    # HTML에 전달할 데이터
    # =====================================================

    posts = []


    for r in rows:

        posts.append({

            'id': r[0],

            'author': r[1],

            'content': r[2],

            'filename': r[3],

            'file_url': r[4],

            # UTC → 한국 시간
            'time':
                (
                    r[5] + timedelta(hours=9)
                ).strftime(
                    '%Y-%m-%d %H:%M:%S'
                )
                if r[5]
                else ''
        })


    return render_template(
        'index.html',
        posts=posts
    )


# =========================================================
# 파일 다운로드
# =========================================================

@app.route('/proxy_download')
def proxy_download():

    # -----------------------------------------------------
    # 로그인 확인
    # -----------------------------------------------------

    if not is_logged_in():

        return redirect(
            url_for('login')
        )


    file_url = request.args.get(
        'url'
    )

    filename = request.args.get(
        'filename',
        'download'
    )


    if not file_url:

        return (
            "잘못된 요청입니다.",
            400
        )


    try:

        # 원본 파일 열기
        resp_obj = urllib.request.urlopen(
            file_url
        )


        content_type = (
            resp_obj.headers.get(
                'Content-Type',
                'application/octet-stream'
            )
        )


        def generate():

            with resp_obj as resp:

                while True:

                    chunk = resp.read(
                        8192
                    )

                    if not chunk:
                        break

                    yield chunk


        encoded_filename = (
            urllib.parse.quote(
                filename
            )
        )


        return Response(

            stream_with_context(
                generate()
            ),

            headers={

                'Content-Type':
                    content_type,

                'Content-Disposition':
                    f"attachment; "
                    f"filename*=UTF-8''"
                    f"{encoded_filename}",

                'X-Content-Type-Options':
                    'nosniff'
            }
        )


    except Exception as e:

        print(
            "파일 다운로드 오류:",
            e
        )

        return (
            "파일을 다운로드할 수 없습니다.",
            404
        )


# =========================================================
# 게시글 삭제
# =========================================================

@app.route(
    '/delete/<int:post_id>',
    methods=['POST']
)
def delete_post(post_id):

    # -----------------------------------------------------
    # 로그인 확인
    # -----------------------------------------------------

    if not is_logged_in():

        return redirect(
            url_for('login')
        )


    # -----------------------------------------------------
    # 삭제 비밀번호 확인
    # -----------------------------------------------------

    input_password = request.form.get(
        'password',
        ''
    )


    if input_password != ADMIN_PASSWORD:

        return redirect(
            url_for('index')
        )


    # -----------------------------------------------------
    # DB 연결
    # -----------------------------------------------------

    conn = get_db_connection()
    cursor = conn.cursor()


    # -----------------------------------------------------
    # 게시글의 Storage 경로 가져오기
    # -----------------------------------------------------

    cursor.execute('''
        SELECT storage_path
        FROM posts
        WHERE id = %s
    ''', (
        post_id,
    ))


    row = cursor.fetchone()


    if row:

        storage_path = row[0]


        # -------------------------------------------------
        # Supabase Storage 파일 삭제
        # -------------------------------------------------

        if storage_path:

            try:

                supabase.storage.from_(
                    'uploads'
                ).remove([
                    storage_path
                ])

            except Exception as e:

                print(
                    "Storage 파일 삭제 오류:",
                    e
                )


        # -------------------------------------------------
        # DB에서 게시글 삭제
        # -------------------------------------------------

        cursor.execute('''
            DELETE FROM posts
            WHERE id = %s
        ''', (
            post_id,
        ))


        conn.commit()


    cursor.close()
    conn.close()


    return redirect(
        url_for('index')
    )


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
