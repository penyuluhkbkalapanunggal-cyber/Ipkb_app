import os
import time
import math
import threading
import json
import locale
import pandas as pd
from xhtml2pdf import pisa
import pdfplumber
import re


from dotenv import load_dotenv
from datetime import date, datetime, timedelta
from functools import wraps
from io import BytesIO

import pymysql
pymysql.install_as_MySQLdb()
import MySQLdb.cursors

from flask import render_template, request, redirect, session, send_file
from werkzeug.utils import secure_filename
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Hello Render"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
# LOAD ENV
load_dotenv()
FONNTE_TOKEN = os.getenv("FONNTE_TOKEN")

# PDF (ganti dari xhtml2pdf ke reportlab)
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

try:
    locale.setlocale(locale.LC_TIME, 'id_ID.UTF-8')
except:
    pass

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
from flask import Flask, render_template, request, redirect, session, jsonify, Response, send_from_directory
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
try:
    import requests
except Exception:
    requests = None

app = Flask(__name__)
app.secret_key = "secret123"

# ================= CONFIG =================
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = ""
app.config["MYSQL_DB"] = "ipkb_app"

# ================= WA / PWA CONFIG =================
# Isi token di environment Windows, misalnya:
# set FONNTE_TOKEN=token_kamu
# set WA_AUTO_SEND=1
WA_PROVIDER = os.environ.get("WA_PROVIDER", "fonnte")
FONNTE_TOKEN = os.environ.get("FONNTE_TOKEN", "")
WA_AUTO_SEND = os.environ.get("WA_AUTO_SEND", "0") == "1"
WA_CHECK_SECONDS = int(os.environ.get("WA_CHECK_SECONDS", "60"))

mysql = MySQL(app)
BULAN_LIST = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
BULAN_NAMA = {
    "1": "Januari", "2": "Februari", "3": "Maret", "4": "April",
    "5": "Mei", "6": "Juni", "7": "Juli", "8": "Agustus",
    "9": "September", "10": "Oktober", "11": "November", "12": "Desember",
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

def bulan_sampai_berjalan_list():
    """Daftar (bulan, tahun, urut) dari Januari 2026 sampai bulan berjalan."""
    hasil = []
    now = date.today()
    for tahun in range(2026, now.year + 1):
        max_bulan = now.month if tahun == now.year else 12
        for urut in range(1, max_bulan + 1):
            hasil.append((BULAN_LIST[urut - 1], tahun, urut))
    return hasil

def ensure_iuran_jan_2026_to_current(cur, default_jumlah=50000, user_id=None):
    params = []
    where_user = ""

    if user_id:
        where_user = " AND users.id=%s"
        params.append(user_id)

    # ambil user + nominal iuran masing-masing
    cur.execute(f"""
        SELECT users.id, users.nama, users.nip, IFNULL(users.nominal_iuran, %s)
        FROM users
        WHERE users.role IN ('anggota','user') {where_user}
        ORDER BY users.nama ASC
    """, tuple([default_jumlah] + params))

    anggota = cur.fetchall()
    periode = bulan_sampai_berjalan_list()
    created = 0

    for u in anggota:
        uid = u[0]
        nominal = int(u[3] or default_jumlah)

        for bulan, tahun, _urut in periode:
            cur.execute("""
                SELECT id FROM iuran
                WHERE user_id=%s AND bulan=%s AND tahun=%s
                LIMIT 1
            """, (uid, bulan, tahun))

            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO iuran (user_id, bulan, tahun, jumlah)
                    VALUES (%s,%s,%s,%s)
                """, (uid, bulan, tahun, nominal))
                created += 1

    return created


def periode_jan_2026_label():
    return f"Januari 2026 s/d {bulan_nama(date.today().month)} {date.today().year}"



# ================= HELPER =================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/")
        return f(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect("/")
            if session.get("role") not in roles:
                return redirect("/iuran?msg=❌ Akses ditolak")
            return f(*args, **kwargs)
        return wrapper
    return decorator


def is_anggota_role():
    # Role anggota di database lama kadang tersimpan sebagai "user".
    return session.get("role") in ["anggota", "user"]


def save_upload(field_name):
    file = request.files.get(field_name)
    if file and file.filename:
        filename = f"{int(time.time())}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        return filename
    return ""


def rupiah(value):
    return "Rp " + f"{int(value or 0):,}".replace(",", ".")




def table_exists(cur, name):
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=%s", (name,))
    return (cur.fetchone()[0] or 0) > 0


def paginate(total_rows, page, per_page=10):
    total_pages = max(1, math.ceil((total_rows or 0) / per_page))
    page = max(1, min(int(page or 1), total_pages))
    offset = (page - 1) * per_page
    return page, total_pages, offset


def pagination_pages(page, total_pages, max_buttons=5):
    """Nomor pagination dibatasi maksimal 5 tombol agar rapi di HP."""
    total_pages = int(total_pages or 1)
    page = int(page or 1)
    max_buttons = int(max_buttons or 5)
    start = max(1, page - max_buttons // 2)
    end = min(total_pages, start + max_buttons - 1)
    start = max(1, end - max_buttons + 1)
    return list(range(start, end + 1))


def current_month_order():
    return date.today().month


def bulan_lalu_sampai_sekarang_sql(alias='iuran'):
    # Tagihan dihitung mulai Januari 2026 sampai bulan berjalan.
    urut = f"FIELD({alias}.bulan,'Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des')"
    return (
        f"({alias}.tahun >= 2026 AND ("
        f"{alias}.tahun < YEAR(CURDATE()) OR "
        f"({alias}.tahun = YEAR(CURDATE()) AND {urut} <= MONTH(CURDATE()))"
        f"))"
    )


def bulan_nama(value):
    return BULAN_NAMA.get(value, BULAN_NAMA.get(str(value), str(value or 'Semua Bulan')))



def bulan_values_from_request():
    # Mendukung ?bulan=1&bulan=2, ?bulan=1,2, ?bulan[]=1, ?bulan=Jan, ?bulan=Januari.
    raw = []
    raw.extend(request.args.getlist('bulan'))
    raw.extend(request.args.getlist('bulan[]'))
    raw.extend(request.args.getlist('bulan_multi'))
    raw.extend(request.args.getlist('bulan_multi[]'))
    alias = {
        'jan': 1, 'januari': 1,
        'feb': 2, 'februari': 2,
        'mar': 3, 'maret': 3,
        'apr': 4, 'april': 4,
        'mei': 5,
        'jun': 6, 'juni': 6,
        'jul': 7, 'juli': 7,
        'agu': 8, 'agustus': 8, 'aug': 8,
        'sep': 9, 'september': 9,
        'okt': 10, 'oct': 10, 'oktober': 10,
        'nov': 11, 'november': 11,
        'des': 12, 'dec': 12, 'desember': 12
    }
    out = []
    for item in raw:
        for part in str(item).replace(';', ',').split(','):
            part = part.strip()
            if not part:
                continue
            val = int(part) if part.isdigit() else alias.get(part.lower())
            if val and 1 <= val <= 12 and val not in out:
                out.append(val)
    return out


def bulan_multi_label(values):
    if not values:
        return 'Semua Bulan'
    return ', '.join(bulan_nama(v) for v in values)


def month_in_clause(expr, values):
    if not values:
        return '', []
    placeholders = ','.join(['%s'] * len(values))
    return f" AND {expr} IN ({placeholders})", list(values)



def monthly_iuran_unpaid_subquery(extra_where):
    """Subquery tunggakan per user/bulan/tahun.

    Menggabungkan data per bulan supaya kalau ada iuran duplikat pada user/bulan/tahun,
    tidak salah membaca tunggakan berdasarkan ID iuran yang berbeda.
    """
    return f"""
        SELECT m.user_id, m.bulan, m.tahun, m.urut, m.jumlah, IFNULL(SUM(pembayaran.jumlah_bayar),0) AS terbayar,
               (m.jumlah - IFNULL(SUM(pembayaran.jumlah_bayar),0)) AS sisa
        FROM (
            SELECT user_id, bulan, tahun,
                   FIELD(bulan,'Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des') AS urut,
                   MAX(jumlah) AS jumlah,
                   GROUP_CONCAT(id) AS ids
            FROM iuran
            WHERE {extra_where}
            GROUP BY user_id, bulan, tahun
        ) m
        LEFT JOIN iuran i2 ON i2.user_id=m.user_id AND i2.bulan=m.bulan AND i2.tahun=m.tahun
        LEFT JOIN pembayaran ON pembayaran.iuran_id=i2.id
        GROUP BY m.user_id, m.bulan, m.tahun, m.urut, m.jumlah
        HAVING sisa > 0
    """


def get_bendahara_reporter(cur):
    # Nama pelapor laporan resmi selalu bendahara.
    try:
        cur.execute("SELECT nama, role FROM users WHERE role='bendahara' ORDER BY id ASC LIMIT 1")
        row = cur.fetchone()
        if row:
            return {"nama": row[0], "role": "Bendahara"}
    except Exception:
        pass
    return {"nama": session.get("user", ""), "role": "Bendahara"}


def column_exists(cur, table, column):
    cur.execute("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s AND column_name=%s", (table, column))
    return (cur.fetchone()[0] or 0) > 0


def ensure_app_schema():
    cur = mysql.connection.cursor()
    try:
        # ================= USERS =================
        if table_exists(cur, 'users') and not column_exists(cur, 'users', 'no_hp'):
            cur.execute("ALTER TABLE users ADD COLUMN no_hp VARCHAR(30) NULL AFTER foto")

        # 🔥 TAMBAHAN NOMINAL IURAN PER USER
        if table_exists(cur, 'users') and not column_exists(cur, 'users', 'nominal_iuran'):
            cur.execute("ALTER TABLE users ADD COLUMN nominal_iuran INT NOT NULL DEFAULT 50000 AFTER no_hp")

        # ================= RENCANA KERJA =================
        if table_exists(cur, 'rencana_kerja') and not column_exists(cur, 'rencana_kerja', 'jam'):
            cur.execute("ALTER TABLE rencana_kerja ADD COLUMN jam TIME NULL AFTER tanggal")

        if table_exists(cur, 'rencana_kerja') and not column_exists(cur, 'rencana_kerja', 'jam_selesai'):
            cur.execute("ALTER TABLE rencana_kerja ADD COLUMN jam_selesai TIME NULL AFTER jam")

        if table_exists(cur, 'rencana_kerja') and not column_exists(cur, 'rencana_kerja', 'wa_diingatkan'):
            cur.execute("ALTER TABLE rencana_kerja ADD COLUMN wa_diingatkan TINYINT(1) NOT NULL DEFAULT 0 AFTER status")

        # ================= UNIQUE NIP =================
        if table_exists(cur, 'users'):
            try:
                cur.execute("ALTER TABLE users ADD UNIQUE KEY uniq_users_nip (nip)")
            except Exception:
                mysql.connection.rollback()

        # ================= PENGELUARAN =================
        if not table_exists(cur, 'pengeluaran'):
            cur.execute("""
                CREATE TABLE pengeluaran (
                  id INT(11) NOT NULL AUTO_INCREMENT,
                  tanggal DATE NOT NULL,
                  uraian VARCHAR(255) NOT NULL,
                  jumlah INT(11) NOT NULL DEFAULT 0,
                  keterangan TEXT DEFAULT NULL,
                  bukti VARCHAR(255) DEFAULT NULL,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  INDEX idx_pengeluaran_tanggal (tanggal)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
            """)
        elif not column_exists(cur, 'pengeluaran', 'bukti'):
            cur.execute("ALTER TABLE pengeluaran ADD COLUMN bukti VARCHAR(255) NULL AFTER keterangan")

        # ================= WA LOG (ANTI SPAM) =================
        if not table_exists(cur, 'wa_log_iuran'):
            cur.execute("""
                CREATE TABLE wa_log_iuran (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    bulan VARCHAR(10) NOT NULL,
                    tahun INT NOT NULL,
                    terkirim_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uniq_wa_iuran (user_id, bulan, tahun)
                )
            """)

        # ================= AUTO GENERATE IURAN =================
        if table_exists(cur, 'users') and table_exists(cur, 'iuran'):
            ensure_iuran_jan_2026_to_current(cur)

        # ================= SKP TAMBAHAN =================
        if table_exists(cur, 'skp'):
            for col, sql in [
                ('bulan', "ALTER TABLE skp ADD COLUMN bulan VARCHAR(30) NULL"),
                ('volume', "ALTER TABLE skp ADD COLUMN volume VARCHAR(100) NULL"),
                ('jenis_kegiatan', "ALTER TABLE skp ADD COLUMN jenis_kegiatan TEXT NULL"),
                ('hari', "ALTER TABLE skp ADD COLUMN hari VARCHAR(50) NULL"),
                ('tanggal_pelaksanaan', "ALTER TABLE skp ADD COLUMN tanggal_pelaksanaan DATE NULL"),
                ('tanggal', "ALTER TABLE skp ADD COLUMN tanggal DATE NULL"),
                ('jam_mulai', "ALTER TABLE skp ADD COLUMN jam_mulai TIME NULL"),
                ('jam_selesai', "ALTER TABLE skp ADD COLUMN jam_selesai TIME NULL"),
                ('sasaran', "ALTER TABLE skp ADD COLUMN sasaran TEXT NULL"),
                ('lokasi_kegiatan', "ALTER TABLE skp ADD COLUMN lokasi_kegiatan TEXT NULL"),
                ('gambar', "ALTER TABLE skp ADD COLUMN gambar VARCHAR(255) NULL"),
                ('tanda_tangan', "ALTER TABLE skp ADD COLUMN tanda_tangan VARCHAR(255) NULL"),
                ('nomor_laporan', "ALTER TABLE skp ADD COLUMN nomor_laporan VARCHAR(100) NULL")
            ]:
                if not column_exists(cur, 'skp', col):
                    cur.execute(sql)

        mysql.connection.commit()

    except Exception:
        mysql.connection.rollback()

    finally:
        cur.close()
@app.before_request
def auto_prepare_schema():
    if not getattr(app, '_schema_ready', False):
        try:
            ensure_app_schema()
            app._schema_ready = True
        except Exception:
            pass


def wa_number(no_hp):
    nomor = ''.join(ch for ch in str(no_hp or '') if ch.isdigit())
    if nomor.startswith('0'):
        nomor = '62' + nomor[1:]
    return nomor

def send_whatsapp(no_hp, message):
    """Kirim WhatsApp otomatis via Fonnte. Return (status_bool, pesan)."""
    nomor = wa_number(no_hp)
    if not nomor:
        return False, "Nomor WhatsApp kosong"
    if not FONNTE_TOKEN:
        return False, "Token FONNTE_TOKEN belum diisi"
    if requests is None:
        return False, "Library requests belum terpasang"
    try:
        resp = requests.post(
            "https://api.fonnte.com/send",
            headers={"Authorization": FONNTE_TOKEN},
            data={"target": nomor, "message": message},
            timeout=15,
        )
        ok = 200 <= resp.status_code < 300
        return ok, resp.text[:200]
    except Exception as exc:
        return False, str(exc)


def build_tagihan_message(nama, periode, total_sisa):
    return (
        f"Yth. {nama},\n\n"
        f"Kami mengingatkan bahwa iuran IPKB Bapak/Ibu masih belum lunas.\n"
        f"Periode: {periode}\n"
        f"Total sisa: {rupiah(total_sisa)}\n\n"
        f"Mohon segera melakukan pembayaran. Terima kasih."
    )


def build_renja_message(nama, kegiatan, tanggal, jam, jam_selesai=None):
    rentang = f"{jam}"
    if jam_selesai:
        rentang += f" - {jam_selesai}"
    return (
        f"Yth. {nama},\n\n"
        f"Pengingat kegiatan IPKB:\n"
        f"Kegiatan: {kegiatan}\n"
        f"Tanggal: {tanggal}\n"
        f"Jam: {rentang}\n\n"
        f"Silakan mempersiapkan kegiatan sesuai jadwal."
    )


def bulan_order_sql(alias='iuran'):
    return f"FIELD({alias}.bulan,'Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des')"

def pdf_escape(text):
    return str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_simple_pdf(title, lines):
    """PDF sederhana tanpa library tambahan."""
    content = ["BT", "/F1 16 Tf", "50 800 Td", f"({pdf_escape(title)}) Tj", "/F1 10 Tf", "0 -25 Td"]
    for line in lines:
        content.append(f"({pdf_escape(line)}) Tj")
        content.append("0 -15 Td")
    content.append("ET")
    stream = "\n".join(content)
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        f"5 0 obj << /Length {len(stream.encode('latin-1', errors='replace'))} >> stream\n{stream}\nendstream endobj"
    ]
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf.encode('latin-1', errors='replace')))
        pdf += obj + "\n"
    xref_pos = len(pdf.encode('latin-1', errors='replace'))
    pdf += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n"
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n"
    pdf += f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF"
    return pdf.encode('latin-1', errors='replace')



@app.context_processor
def inject_page_helpers():
    titles = {
        "dashboard": "Dashboard",
        "iuran": "Data Iuran",
        "belum_bayar": "Anggota Belum Bayar",
        "pembayaran": "Pembayaran",
        "pengeluaran": "Pengeluaran",
        "tambah_pengeluaran": "Tambah Pengeluaran",
        "edit_pengeluaran": "Edit Pengeluaran",
        "laporan": "Laporan PDF",
        "laporan_kegiatan": "Laporan Kegiatan",
        "laporan_print": "Cetak Laporan",
        "skp": "SKP",
        "rencana_kerja": "Rencana Kerja",
        "api_notifikasi": "Notifikasi",
        "users": "Manajemen User",
        "tambah_user": "Tambah User",
        "edit_user": "Edit User",
        "edit_profil": "Edit Profil",
        "tambah_pembayaran": "Tambah Pembayaran",
    }
    endpoint = request.endpoint or ""
    return dict(page_title=titles.get(endpoint, "IPKB"), pagination_pages=pagination_pages)


@app.context_processor
def inject_notifications():
    notif = {"belum_lunas": 0, "kegiatan": 0, "anggota_belum_bayar": 0}
    if "user_id" not in session:
        return dict(notif=notif)
    try:
        cur = mysql.connection.cursor()

        if table_exists(cur, 'users') and table_exists(cur, 'iuran'):
            # Jangan salah NIP: hanya lengkapi iuran untuk user yang punya histori nominal.
            ensure_iuran_jan_2026_to_current(cur, user_id=session.get("user_id") if is_anggota_role() else None)
            mysql.connection.commit()

        if is_anggota_role():
            extra = bulan_lalu_sampai_sekarang_sql('iuran') + " AND iuran.user_id=%s"
            sql_unpaid = monthly_iuran_unpaid_subquery(extra)
            cur.execute(f"SELECT COUNT(*) FROM ({sql_unpaid}) x", (session["user_id"],))
            notif["belum_lunas"] = cur.fetchone()[0] or 0
            if table_exists(cur, 'rencana_kerja'):
                cur.execute("""
                    SELECT COUNT(*) FROM rencana_kerja
                    WHERE user_id=%s AND status NOT IN ('Selesai','Dilaksanakan')
                    AND (tanggal < CURDATE() OR (tanggal = CURDATE() AND (jam IS NULL OR jam <= CURTIME())))
                """, (session["user_id"],))
                notif["kegiatan"] = cur.fetchone()[0] or 0
        else:
            extra = bulan_lalu_sampai_sekarang_sql('iuran')
            sql_unpaid = monthly_iuran_unpaid_subquery(extra)
            cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT user_id) FROM ({sql_unpaid}) x")
            row = cur.fetchone() or (0, 0)
            notif["belum_lunas"] = row[0] or 0
            notif["anggota_belum_bayar"] = row[1] or 0
            if table_exists(cur, 'rencana_kerja'):
                cur.execute("""
                    SELECT COUNT(*) FROM rencana_kerja
                    WHERE status NOT IN ('Selesai','Dilaksanakan')
                    AND (tanggal < CURDATE() OR (tanggal = CURDATE() AND (jam IS NULL OR jam <= CURTIME())))
                """)
                notif["kegiatan"] = cur.fetchone()[0] or 0
        cur.close()
    except Exception:
        pass
    return dict(notif=notif)
# ================ Edit |Pemabayaran ========
@app.route("/edit_pembayaran/<int:id>", methods=["GET", "POST"])
@role_required("bendahara")
def edit_pembayaran(id):
    cur = mysql.connection.cursor()

    if request.method == "POST":
        jumlah = int(request.form.get("jumlah", 0))

        cur.execute("""
            UPDATE pembayaran SET jumlah_bayar=%s WHERE id=%s
        """, (jumlah, id))

        mysql.connection.commit()
        cur.close()
        return redirect("/pembayaran?msg=✅ Pembayaran berhasil diubah")

    cur.execute("""
        SELECT pembayaran.id, users.nama, iuran.bulan, iuran.tahun, pembayaran.jumlah_bayar
        FROM pembayaran
        JOIN iuran ON pembayaran.iuran_id=iuran.id
        JOIN users ON iuran.user_id=users.id
        WHERE pembayaran.id=%s
    """, (id,))
    
    data = cur.fetchone()
    cur.close()

    if not data:
        return redirect("/pembayaran?msg=❌ Data tidak ditemukan")

    return render_template("edit_pembayaran.html", data=data)
# =============== Hapus ==================
@app.route("/hapus_pembayaran/<int:id>")
@role_required("bendahara")
def hapus_pembayaran(id):
    cur = mysql.connection.cursor()

    cur.execute("SELECT id FROM pembayaran WHERE id=%s", (id,))
    data = cur.fetchone()

    if not data:
        cur.close()
        return redirect("/pembayaran?msg=❌ Data pembayaran tidak ditemukan")

    cur.execute("DELETE FROM pembayaran WHERE id=%s", (id,))
    mysql.connection.commit()
    cur.close()

    return redirect("/pembayaran?msg=✅ Pembayaran berhasil dihapus")

# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nip = request.form.get("nip", "").strip()
        password = request.form.get("password", "").strip()
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE nip=%s", (nip,))
        user = cur.fetchone()
        cur.close()
        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["nip"] = user[1]
            session["role"] = user[3]
            session["user"] = user[4]
            session["foto"] = user[5]
            return redirect("/dashboard")
        return render_template("login.html", error="Login gagal!")
    return render_template("login.html")


# ================= DASHBOARD KEUANGAN =================
@app.route("/dashboard")
@login_required
def dashboard():
    cur = mysql.connection.cursor()
    cur.execute("SELECT IFNULL(SUM(jumlah_bayar), 0) FROM pembayaran")
    total_masuk_all = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'pengeluaran'")
    ada_pengeluaran = cur.fetchone()[0] > 0
    if ada_pengeluaran:
        cur.execute("SELECT IFNULL(SUM(jumlah), 0) FROM pengeluaran")
        total_keluar_all = cur.fetchone()[0] or 0
    else:
        total_keluar_all = 0
    saldo_all = total_masuk_all - total_keluar_all
    if is_anggota_role():
        cur.execute("""
            SELECT IFNULL(SUM(x.jumlah),0), IFNULL(SUM(x.terbayar),0)
            FROM (
                SELECT iuran.id, iuran.jumlah, IFNULL(SUM(pembayaran.jumlah_bayar),0) AS terbayar
                FROM iuran LEFT JOIN pembayaran ON pembayaran.iuran_id=iuran.id
                WHERE iuran.user_id=%s
                GROUP BY iuran.id, iuran.jumlah
            ) x
        """, (session["user_id"],))
        total_tagihan, total_bayar = cur.fetchone()
        total_tagihan = total_tagihan or 0
        total_bayar = total_bayar or 0
        cur.close()
        return render_template("dashboard.html", total_masuk=total_bayar, total_keluar=0,
                               saldo=total_tagihan-total_bayar, user_dashboard=True,
                               total_tagihan=total_tagihan, total_bayar=total_bayar,
                               total_masuk_all=total_masuk_all, total_keluar_all=total_keluar_all,
                               saldo_all=saldo_all)
    cur.close()
    return render_template("dashboard.html", total_masuk=total_masuk_all, total_keluar=total_keluar_all,
                           saldo=saldo_all, total_masuk_all=total_masuk_all,
                           total_keluar_all=total_keluar_all, saldo_all=saldo_all, user_dashboard=False)
# ============== nominal iuaran ============
@app.route("/ubah_nominal_iuran/<int:user_id>", methods=["POST"])
@role_required("bendahara", "admin")
def ubah_nominal_iuran(user_id):
    nominal = int(request.form.get("nominal_iuran", 0) or 0)

    if nominal <= 0:
        return redirect("/iuran?msg=❌ Nominal iuran tidak valid")

    cur = mysql.connection.cursor()

    cur.execute("""
        UPDATE users 
        SET nominal_iuran=%s 
        WHERE id=%s
    """, (nominal, user_id))

    cur.execute("""
        UPDATE iuran
        SET jumlah=%s
        WHERE user_id=%s
        AND id NOT IN (
            SELECT DISTINCT iuran_id 
            FROM pembayaran 
            WHERE iuran_id IS NOT NULL
        )
    """, (nominal, user_id))

    mysql.connection.commit()
    cur.close()

    return redirect("/iuran?msg=✅ Nominal iuran berhasil diubah")
# ================= IURAN =================
@app.route("/iuran")
@login_required
def iuran():
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    page = int(request.args.get("page", 1) or 1)
    show_all = request.args.get("all") == "1"
    per_page = 10

    cur = mysql.connection.cursor()

    # ✅ AUTO BUAT TAGIHAN
    ensure_iuran_jan_2026_to_current(
        cur,
        user_id=session.get("user_id") if is_anggota_role() else None
    )
    mysql.connection.commit()

    where = ["users.role IN ('anggota','user')"]
    params = []

    if is_anggota_role():
        where.append("users.id=%s")
        params.append(session["user_id"])

    if q:
        where.append("(users.nama LIKE %s OR users.nip LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like])

    where_sql = "WHERE " + " AND ".join(where)

    having_sql = ""
    if status_filter == "lunas":
        having_sql = "HAVING sisa <= 0"
    elif status_filter == "belum":
        having_sql = "HAVING sisa > 0"

    base_sql = f"""
        FROM users
        LEFT JOIN (
            SELECT 
                iuran.id,
                iuran.user_id,
                iuran.jumlah,
                IFNULL(SUM(pembayaran.jumlah_bayar),0) AS terbayar
            FROM iuran
            LEFT JOIN pembayaran ON pembayaran.iuran_id = iuran.id
            GROUP BY iuran.id, iuran.user_id, iuran.jumlah
        ) x ON x.user_id = users.id
        {where_sql}
        GROUP BY users.id, users.nama, users.nip, users.no_hp, users.nominal_iuran
        {having_sql}
    """

    # 🔢 TOTAL DATA
    cur.execute(f"""
        SELECT COUNT(*) FROM (
            SELECT users.id,
                   IFNULL(SUM(x.jumlah),0) - IFNULL(SUM(x.terbayar),0) AS sisa
            {base_sql}
        ) total
    """, tuple(params))
    total_rows = cur.fetchone()[0] or 0

    # 📄 PAGINATION
    if show_all:
        page, total_pages, offset = 1, 1, 0
        limit_sql = ""
        limit_params = []
    else:
        page, total_pages, offset = paginate(total_rows, page, per_page)
        limit_sql = "LIMIT %s OFFSET %s"
        limit_params = [per_page, offset]

    # 📊 DATA UTAMA (TAMBAH nominal_iuran)
    cur.execute(f"""
        SELECT 
            users.id,
            users.nama,
            users.nip,
            users.no_hp,
            IFNULL(SUM(x.jumlah),0) AS total_tagihan,
            IFNULL(SUM(x.terbayar),0) AS total_terbayar,
            IFNULL(SUM(x.jumlah),0) - IFNULL(SUM(x.terbayar),0) AS sisa,
            IFNULL(users.nominal_iuran,50000) AS nominal_iuran
        {base_sql}
        ORDER BY sisa DESC, users.nama ASC
        {limit_sql}
    """, tuple(params + limit_params))
    data = cur.fetchall()

    # 💰 TOTAL RINGKASAN
    cur.execute(f"""
        SELECT 
            IFNULL(SUM(total_tagihan),0),
            IFNULL(SUM(total_terbayar),0),
            IFNULL(SUM(sisa),0)
        FROM (
            SELECT 
                users.id,
                IFNULL(SUM(x.jumlah),0) AS total_tagihan,
                IFNULL(SUM(x.terbayar),0) AS total_terbayar,
                IFNULL(SUM(x.jumlah),0) - IFNULL(SUM(x.terbayar),0) AS sisa
            {base_sql}
        ) total
    """, tuple(params))
    tagihan_total, terbayar_total, belum_lunas_total = cur.fetchone()

    # 📊 CHART
    cur.execute(f"""
        SELECT 
            users.nama,
            IFNULL(SUM(x.jumlah),0) - IFNULL(SUM(x.terbayar),0) AS sisa
        {base_sql}
        ORDER BY sisa DESC
        LIMIT 5
    """, tuple(params))
    chart = cur.fetchall()

    # ✅ FIX ERROR ZERO DIVISION
    max_chart = max([int(c[1] or 0) for c in chart], default=0)
    if max_chart <= 0:
        max_chart = 1

    cur.close()

    return render_template(
        "iuran.html",
        data=data,
        chart=chart,
        max_chart=max_chart,
        q=q,
        status_filter=status_filter,
        page=page,
        total_pages=total_pages,
        total_rows=total_rows,
        offset=offset,
        show_all=show_all,
        tagihan_total=tagihan_total or 0,
        terbayar_total=terbayar_total or 0,
        belum_lunas_total=belum_lunas_total or 0
    )

# ============ detail iuran =============
@app.route("/iuran_detail/<int:user_id>")
@login_required
def iuran_detail(user_id):

    page = int(request.args.get("page", 1))
    per_page = 10

    cur = mysql.connection.cursor()

    if is_anggota_role() and user_id != session.get("user_id"):
        cur.close()
        return redirect("/iuran?msg=❌ Akses ditolak")

    cur.execute("""
        SELECT id, nama, nip, IFNULL(nominal_iuran,50000)
        FROM users
        WHERE id=%s
    """, (user_id,))
    user = cur.fetchone()

    if not user:
        cur.close()
        return redirect("/iuran?msg=❌ Anggota tidak ditemukan")

    # TOTAL DATA
    cur.execute("""
        SELECT COUNT(*)
        FROM iuran
        WHERE user_id=%s
    """, (user_id,))

    total_rows = cur.fetchone()[0]

    # PAGINATION
    page, total_pages, offset = paginate(total_rows, page, per_page)

    # DATA
    cur.execute("""
        SELECT 
            iuran.id,
            iuran.bulan,
            iuran.tahun,
            iuran.jumlah,
            IFNULL(SUM(pembayaran.jumlah_bayar),0) AS terbayar,
            iuran.jumlah - IFNULL(SUM(pembayaran.jumlah_bayar),0) AS sisa,
            (
                SELECT p2.bukti 
                FROM pembayaran p2 
                WHERE p2.iuran_id=iuran.id 
                AND p2.bukti<>''
                ORDER BY p2.tanggal DESC, p2.id DESC
                LIMIT 1
            ) AS bukti

        FROM iuran

        LEFT JOIN pembayaran 
        ON pembayaran.iuran_id=iuran.id

        WHERE iuran.user_id=%s

        GROUP BY 
            iuran.id,
            iuran.bulan,
            iuran.tahun,
            iuran.jumlah

        ORDER BY 
            iuran.tahun ASC,
            FIELD(
                iuran.bulan,
                'Jan','Feb','Mar','Apr',
                'Mei','Jun','Jul','Agu',
                'Sep','Okt','Nov','Des'
            ) ASC

        LIMIT %s OFFSET %s

    """, (user_id, per_page, offset))

    data = cur.fetchall()

    cur.close()

    return render_template(
        "iuran_detail.html",
        user=user,
        data=data,
        page=page,
        total_pages=total_pages,
        total_rows=total_rows,
        offset=offset
    )
@app.route("/bayar/<int:id>", methods=["POST"])
@role_required("bendahara")
def bayar(id):
    jumlah = int(request.form.get("jumlah", 0))
    filename = save_upload("bukti")
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT iuran.jumlah, IFNULL(SUM(pembayaran.jumlah_bayar),0)
        FROM iuran LEFT JOIN pembayaran ON pembayaran.iuran_id = iuran.id
        WHERE iuran.id=%s GROUP BY iuran.id
    """, (id,))
    data = cur.fetchone()
    if not data:
        cur.close(); return redirect("/iuran?msg=❌ Iuran tidak ditemukan")
    sisa = data[0] - data[1]
    if jumlah <= 0 or jumlah > sisa:
        cur.close(); return redirect("/iuran?msg=❌ Jumlah bayar tidak valid / melebihi tagihan")
    cur.execute("INSERT INTO pembayaran (iuran_id, tanggal, jumlah_bayar, metode, bukti) VALUES (%s, NOW(), %s, %s, %s)", (id, jumlah, "transfer", filename))
    mysql.connection.commit(); cur.close()
    return redirect("/iuran?msg=✅ Pembayaran berhasil")


@app.route("/edit_iuran/<int:id>", methods=["GET", "POST"])
@role_required("bendahara")
def edit_iuran(id):
    cur = mysql.connection.cursor()
    if request.method == "POST":
        jumlah = int(request.form.get("jumlah", 0))
        cur.execute("UPDATE iuran SET jumlah=%s WHERE id=%s", (jumlah, id))
        mysql.connection.commit(); cur.close()
        return redirect("/iuran?msg=✅ Iuran berhasil diubah")
    cur.execute("SELECT iuran.id, users.nama, iuran.bulan, iuran.tahun, iuran.jumlah FROM iuran JOIN users ON iuran.user_id=users.id WHERE iuran.id=%s", (id,))
    data = cur.fetchone(); cur.close()
    if not data: return redirect("/iuran?msg=❌ Iuran tidak ditemukan")
    return render_template("edit_iuran.html", data=data)


@app.route("/hapus_iuran/<int:id>")
@role_required("bendahara")
def hapus_iuran(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM pembayaran WHERE iuran_id=%s", (id,))
    cur.execute("DELETE FROM iuran WHERE id=%s", (id,))
    mysql.connection.commit(); cur.close()
    return redirect("/iuran?msg=✅ Iuran berhasil dihapus")


# ================= PEMBAYARAN =================
@app.route("/pembayaran")
@role_required("bendahara")
def pembayaran():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT pembayaran.id, users.nama, iuran.bulan, iuran.tahun, pembayaran.jumlah_bayar, pembayaran.tanggal, pembayaran.bukti
        FROM pembayaran JOIN iuran ON pembayaran.iuran_id=iuran.id JOIN users ON iuran.user_id=users.id
        ORDER BY pembayaran.tanggal DESC, pembayaran.id DESC
    """)
    data = cur.fetchall(); cur.close()
    return render_template("pembayaran.html", data=data)


@app.route("/tambah_pembayaran", methods=["GET", "POST"])
@role_required("bendahara")
def tambah_pembayaran():
    cur = mysql.connection.cursor()

    if request.method == "POST":
        user_id = request.form.get("user_id")
        bulan = request.form.get("bulan")
        tahun = request.form.get("tahun")
        jumlah = int(request.form.get("jumlah", 0) or 0)

        if not user_id:
            cur.close()
            return redirect("/tambah_pembayaran?msg=❌ Nama anggota wajib dipilih")

        cur.execute(
            "SELECT id FROM iuran WHERE user_id=%s AND bulan=%s AND tahun=%s",
            (user_id, bulan, tahun)
        )
        iuran_data = cur.fetchone()

        if not iuran_data:
            cur.execute(
                "INSERT INTO iuran (user_id, bulan, tahun, jumlah) VALUES (%s,%s,%s,%s)",
                (user_id, bulan, tahun, 50000)
            )
            mysql.connection.commit()
            iuran_id = cur.lastrowid
        else:
            iuran_id = iuran_data[0]

        cur.execute("""
            SELECT iuran.jumlah, IFNULL(SUM(pembayaran.jumlah_bayar),0)
            FROM iuran
            LEFT JOIN pembayaran ON pembayaran.iuran_id=iuran.id
            WHERE iuran.id=%s
            GROUP BY iuran.id
        """, (iuran_id,))

        tagihan = cur.fetchone()

        if not tagihan or jumlah <= 0 or jumlah + tagihan[1] > tagihan[0]:
            cur.close()
            return redirect("/tambah_pembayaran?msg=❌ Pembayaran tidak valid / melebihi tagihan")

        filename = save_upload("bukti")

        cur.execute("""
            INSERT INTO pembayaran (iuran_id, tanggal, jumlah_bayar, metode, bukti)
            VALUES (%s,NOW(),%s,%s,%s)
        """, (iuran_id, jumlah, "transfer", filename))

        mysql.connection.commit()
        cur.close()
        return redirect("/pembayaran?msg=✅ Pembayaran berhasil")

    cur.execute("""
        SELECT id, nama, nip
        FROM users
        WHERE role IN ('anggota','user')
        ORDER BY nama ASC
    """)
    users = cur.fetchall()
    cur.close()

    return render_template(
        "tambah_pembayaran.html",
        users=users,
        bulan_list=BULAN_LIST
    )
@app.route("/cek_tagihan")
@role_required("bendahara")
def cek_tagihan():
    user_id, bulan, tahun = request.args.get("user_id"), request.args.get("bulan"), request.args.get("tahun")
    cur = mysql.connection.cursor()
    cur.execute("SELECT iuran.jumlah, IFNULL(SUM(pembayaran.jumlah_bayar),0) FROM iuran LEFT JOIN pembayaran ON pembayaran.iuran_id=iuran.id WHERE iuran.user_id=%s AND iuran.bulan=%s AND iuran.tahun=%s GROUP BY iuran.id", (user_id, bulan, tahun))
    data = cur.fetchone(); cur.close()
    return jsonify({"sisa": data[0]-data[1] if data else 50000})


# ================= PENGELUARAN =================
@app.route("/pengeluaran")
@role_required("admin", "bendahara", "anggota", "user")
def pengeluaran():
    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1) or 1)
    show_all = request.args.get("all") == "1"
    per_page = 10
    cur = mysql.connection.cursor()
    where, params = "", []
    if q:
        where = "WHERE uraian LIKE %s OR keterangan LIKE %s OR bukti LIKE %s OR CAST(tanggal AS CHAR) LIKE %s OR CAST(jumlah AS CHAR) LIKE %s"
        like = f"%{q}%"
        params = [like, like, like, like, like]
    cur.execute(f"SELECT COUNT(*) FROM pengeluaran {where}", tuple(params))
    total_rows = cur.fetchone()[0] or 0
    if show_all:
        page, total_pages, offset = 1, 1, 0
        limit_sql = ""
        limit_params = []
    else:
        page, total_pages, offset = paginate(total_rows, page, per_page)
        limit_sql = "LIMIT %s OFFSET %s"
        limit_params = [per_page, offset]
    cur.execute(f"""
        SELECT id, tanggal, uraian, jumlah, keterangan, bukti
        FROM pengeluaran {where}
        ORDER BY tanggal DESC, id DESC
        {limit_sql}
    """, tuple(params + limit_params))
    data = cur.fetchall()
    cur.execute(f"SELECT IFNULL(SUM(jumlah),0) FROM pengeluaran {where}", tuple(params))
    total_pengeluaran = cur.fetchone()[0] or 0
    cur.close()
    return render_template("pengeluaran.html", data=data, q=q, page=page, total_pages=total_pages,
                           total_rows=total_rows, offset=offset, total_pengeluaran=total_pengeluaran, show_all=show_all)


@app.route("/tambah_pengeluaran", methods=["GET", "POST"])
@role_required("bendahara")
def tambah_pengeluaran():
    if request.method == "POST":
        tanggal = request.form.get("tanggal")
        uraian = request.form.get("uraian", "").strip()
        jumlah = int(request.form.get("jumlah", 0) or 0)
        keterangan = request.form.get("keterangan", "").strip()
        bukti = save_upload("bukti")
        if not tanggal or not uraian or jumlah <= 0:
            return redirect("/tambah_pengeluaran?msg=❌ Data pengeluaran belum lengkap")
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO pengeluaran (tanggal, uraian, jumlah, keterangan, bukti) VALUES (%s,%s,%s,%s,%s)",
                    (tanggal, uraian, jumlah, keterangan, bukti))
        mysql.connection.commit(); cur.close()
        return redirect("/pengeluaran?msg=✅ Pengeluaran berhasil ditambah")
    return render_template("form_pengeluaran.html", data=None)


@app.route("/edit_pengeluaran/<int:id>", methods=["GET", "POST"])
@role_required("bendahara")
def edit_pengeluaran(id):
    cur = mysql.connection.cursor()
    if request.method == "POST":
        tanggal = request.form.get("tanggal")
        uraian = request.form.get("uraian", "").strip()
        jumlah = int(request.form.get("jumlah", 0) or 0)
        keterangan = request.form.get("keterangan", "").strip()
        cur.execute("SELECT bukti FROM pengeluaran WHERE id=%s", (id,))
        old_bukti = cur.fetchone()
        bukti_lama = old_bukti[0] if old_bukti else ""
        bukti_baru = save_upload("bukti")
        bukti = bukti_baru if bukti_baru else bukti_lama
        if not tanggal or not uraian or jumlah <= 0:
            cur.close(); return redirect(f"/edit_pengeluaran/{id}?msg=❌ Data pengeluaran belum lengkap")
        cur.execute("UPDATE pengeluaran SET tanggal=%s, uraian=%s, jumlah=%s, keterangan=%s, bukti=%s WHERE id=%s",
                    (tanggal, uraian, jumlah, keterangan, bukti, id))
        mysql.connection.commit(); cur.close()
        return redirect("/pengeluaran?msg=✅ Pengeluaran berhasil diubah")
    cur.execute("SELECT id, tanggal, uraian, jumlah, keterangan, bukti FROM pengeluaran WHERE id=%s", (id,))
    data = cur.fetchone(); cur.close()
    if not data:
        return redirect("/pengeluaran?msg=❌ Data pengeluaran tidak ditemukan")
    return render_template("form_pengeluaran.html", data=data)


@app.route("/hapus_pengeluaran/<int:id>")
@role_required("bendahara")
def hapus_pengeluaran(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM pengeluaran WHERE id=%s", (id,))
    mysql.connection.commit(); cur.close()
    return redirect("/pengeluaran?msg=✅ Pengeluaran berhasil dihapus")


# ================= MANAJEMEN USER =================
@app.route("/users")
@role_required("admin")
def users():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, nip, password, role, nama, foto, no_hp FROM users ORDER BY nama ASC")
    users_data = cur.fetchall(); cur.close()
    return render_template("users.html", users=users_data)

# ====== Tambah User ===========
@app.route("/tambah_user", methods=["GET", "POST"])
@role_required("admin")
def tambah_user():
    if request.method == "POST":
        nip = request.form.get("nip", "").strip()
        nama = request.form.get("nama", "").strip()
        no_hp = request.form.get("no_hp", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "anggota")
        nominal_iuran = int(request.form.get("nominal_iuran", 50000) or 50000)

        cur = mysql.connection.cursor()

        cur.execute("SELECT id FROM users WHERE nip=%s", (nip,))
        if cur.fetchone():
            cur.close()
            return redirect("/tambah_user?msg=❌ NIP sudah terdaftar")

        filename = save_upload("foto")

        try:
            cur.execute("""
                INSERT INTO users (nip, password, role, nama, foto, no_hp, nominal_iuran)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                nip,
                generate_password_hash(password),
                role,
                nama,
                filename,
                no_hp,
                nominal_iuran
            ))

            new_user_id = cur.lastrowid

            if role in ["anggota", "user"]:
                ensure_iuran_jan_2026_to_current(
                    cur,
                    default_jumlah=nominal_iuran,
                    user_id=new_user_id
                )

            mysql.connection.commit()

        except Exception:
            mysql.connection.rollback()
            cur.close()
            return redirect("/tambah_user?msg=❌ Gagal menyimpan user")

        cur.close()
        return redirect("/users?msg=✅ User berhasil ditambah + tagihan otomatis dibuat")

    return render_template("tambah_user.html")

@app.route("/edit_user/<int:id>", methods=["GET", "POST"])
@role_required("admin")
def edit_user(id):
    cur = mysql.connection.cursor()
    if request.method == "POST":
        nip = request.form.get("nip", "").strip(); nama = request.form.get("nama", "").strip(); no_hp = request.form.get("no_hp", "").strip(); role = request.form.get("role", "anggota"); password = request.form.get("password", "").strip()
        cur.execute("SELECT foto FROM users WHERE id=%s", (id,)); old = cur.fetchone(); filename = old[0] if old else ""
        uploaded = save_upload("foto")
        if uploaded: filename = uploaded
        if password:
            cur.execute("UPDATE users SET nip=%s,password=%s,role=%s,nama=%s,foto=%s,no_hp=%s WHERE id=%s", (nip, generate_password_hash(password), role, nama, filename, no_hp, id))
        else:
            cur.execute("UPDATE users SET nip=%s,role=%s,nama=%s,foto=%s,no_hp=%s WHERE id=%s", (nip, role, nama, filename, no_hp, id))
        mysql.connection.commit(); cur.close()
        return redirect("/users?msg=✅ User berhasil diubah")
    cur.execute("SELECT id, nip, password, role, nama, foto, no_hp FROM users WHERE id=%s", (id,))
    user = cur.fetchone(); cur.close()
    if not user: return redirect("/users?msg=❌ User tidak ditemukan")
    return render_template("edit_user.html", user=user)


@app.route("/hapus_user/<int:id>")
@role_required("admin")
def hapus_user(id):
    if id == session.get("user_id"):
        return redirect("/users?msg=❌ Tidak bisa hapus akun sendiri")
    cur = mysql.connection.cursor()
    cur.execute("DELETE pembayaran FROM pembayaran JOIN iuran ON pembayaran.iuran_id=iuran.id WHERE iuran.user_id=%s", (id,))
    cur.execute("DELETE FROM iuran WHERE user_id=%s", (id,))
    cur.execute("DELETE FROM users WHERE id=%s", (id,))
    mysql.connection.commit(); cur.close()
    return redirect("/users?msg=✅ User berhasil dihapus")


# ================= LAPORAN_SKP =================
@app.route("/skp", methods=["GET", "POST"])
@role_required("admin", "anggota", "user")
def skp():

    cur = mysql.connection.cursor()

    # =========================================
    # SIMPAN DATA
    # =========================================
    if request.method == "POST":

        from datetime import datetime

        user_id = session["user_id"] if is_anggota_role() else request.form.get("user_id")

        tahun = request.form.get("tahun") or datetime.now().year
        bulan = request.form.get("bulan") or datetime.now().strftime("%B")

        volume = request.form.get("volume")

        jenis_kegiatan = request.form.get("jenis_kegiatan")

        hari = request.form.get("hari")
        tanggal_pelaksanaan = request.form.get("tanggal_pelaksanaan")

        tanggal = request.form.get("tanggal")

        jam_mulai = request.form.get("jam_mulai")
        jam_selesai = request.form.get("jam_selesai")

        sasaran = request.form.get("sasaran")

        lokasi_kegiatan = request.form.get("lokasi_kegiatan")

        uraian = request.form.get("uraian")

        target = request.form.get("target")
        capaian = request.form.get("capaian")

        kategori_kegiatan = request.form.get("kategori_kegiatan") or "SKP"

        gambar = save_upload("gambar")
        tanda_tangan = save_upload("tanda_tangan")

        # =========================================
        # INSERT
        # =========================================
        cur.execute("""
            INSERT INTO laporan_skp
            (
                user_id,
                tahun,
                kategori_kegiatan,
                uraian,
                target,
                capaian,
                bulan,
                volume,
                jenis_kegiatan,
                hari,
                tanggal_pelaksanaan,
                tanggal,
                jam_mulai,
                jam_selesai,
                sasaran,
                lokasi_kegiatan,
                gambar,
                tanda_tangan
            )
            VALUES
            (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s
            )
        """, (
            user_id,
            tahun,
            kategori_kegiatan,
            uraian,
            target,
            capaian,
            bulan,
            volume,
            jenis_kegiatan,
            hari,
            tanggal_pelaksanaan,
            tanggal,
            jam_mulai,
            jam_selesai,
            sasaran,
            lokasi_kegiatan,
            gambar,
            tanda_tangan
        ))

        mysql.connection.commit()

        return redirect("/skp?msg=✅ Laporan SKP berhasil disimpan")

    # =========================================
    # DATA TABEL SKP
    # =========================================
    if is_anggota_role():

        cur.execute("""
            SELECT
                id,
                uraian,
                target,
                IFNULL(kategori_kegiatan, 'SKP')
            FROM laporan_skp
            WHERE user_id=%s
            ORDER BY id DESC
        """, (session["user_id"],))

    else:

        cur.execute("""
            SELECT
                id,
                uraian,
                target,
                IFNULL(kategori_kegiatan, 'SKP')
            FROM laporan_skp
            ORDER BY id DESC
        """)

    data = cur.fetchall()

    # =========================================
    # DATA USER
    # =========================================
    cur.execute("""
        SELECT id, nama
        FROM users
        WHERE role IN ('anggota','user')
        ORDER BY nama ASC
    """)

    users = cur.fetchall()

    # =========================================
    # AMBIL DATA KEGIATAN PKB
    # =========================================
    if is_anggota_role():

        cur.execute("""
            SELECT
                id,
                judul_kegiatan,
                deskripsi,
                sasaran,
                tempat,
                hasil_kegiatan,
                tgl_mulai,
                tgl_selesai
            FROM kegiatan_pkb
            WHERE user_id=%s
            ORDER BY id DESC
        """, (session["user_id"],))

    else:

        cur.execute("""
            SELECT
                id,
                judul_kegiatan,
                deskripsi,
                sasaran,
                tempat,
                hasil_kegiatan,
                tgl_mulai,
                tgl_selesai
            FROM kegiatan_pkb
            ORDER BY id DESC
        """)

    kegiatan_list = cur.fetchall()

    cur.close()

    return render_template(
        "skp.html",
        data=data,
        users=users,
        kegiatan_list=kegiatan_list
    )


@app.route("/hapus_skp/<int:id>")
@role_required("admin", "anggota", "user")
def hapus_skp(id):
    cur = mysql.connection.cursor()

    if is_anggota_role():
        cur.execute("DELETE FROM skp WHERE id=%s AND user_id=%s", (id, session["user_id"]))
    else:
        cur.execute("DELETE FROM skp WHERE id=%s", (id,))

    mysql.connection.commit()
    cur.close()
    return redirect("/skp?msg=✅ SKP berhasil dihapus")


@app.route("/skp/pdf/<int:id>")
@role_required("admin", "anggota", "user")
def skp_pdf(id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if is_anggota_role():
        cur.execute("""
            SELECT skp.*, users.nama
            FROM skp 
            JOIN users ON skp.user_id=users.id
            WHERE skp.id=%s AND skp.user_id=%s
        """, (id, session["user_id"]))
    else:
        cur.execute("""
            SELECT skp.*, users.nama
            FROM skp 
            JOIN users ON skp.user_id=users.id
            WHERE skp.id=%s
        """, (id,))

    data = cur.fetchone()
    cur.close()

    if not data:
        return redirect("/skp?msg=❌ Data tidak ditemukan")

    html = render_template("skp_pdf.html", data=data)

    pdf = BytesIO()
    pisa.CreatePDF(BytesIO(html.encode("UTF-8")), dest=pdf)
    pdf.seek(0)

    return send_file(pdf, download_name="laporan_skp.pdf", as_attachment=True)


@app.route("/skp/print/<int:id>")
@role_required("admin", "anggota", "user")
def skp_print(id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if is_anggota_role():
        cur.execute("""
            SELECT skp.*, users.nama
            FROM skp 
            JOIN users ON skp.user_id=users.id
            WHERE skp.id=%s AND skp.user_id=%s
        """, (id, session["user_id"]))
    else:
        cur.execute("""
            SELECT skp.*, users.nama
            FROM skp 
            JOIN users ON skp.user_id=users.id
            WHERE skp.id=%s
        """, (id,))

    data = cur.fetchone()
    cur.close()

    if not data:
        return redirect("/skp?msg=❌ Data tidak ditemukan")

    return render_template("skp_pdf.html", data=data)

# ================= RENCANA KERJA =================
@app.route("/rencana_kerja", methods=["GET", "POST"])
@role_required("admin", "anggota", "user")
def rencana_kerja():
    cur = mysql.connection.cursor()

    if request.method == "POST":
        user_id = session["user_id"] if is_anggota_role() else request.form.get("user_id")
        status = request.form.get("status", "Proses")

        if status == "Rencana":
            status = "Proses"

        cur.execute("""
            INSERT INTO rencana_kerja (
                user_id,
                tanggal,
                jam,
                jam_selesai,
                kategori_kegiatan,
                kegiatan,
                sasaran,
                hasil_kegiatan,
                tindak_lanjut,
                tempat,
                keterangan,
                status
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            request.form.get("tanggal"),
            request.form.get("jam"),
            request.form.get("jam_selesai"),
            request.form.get("kategori_kegiatan"),
            request.form.get("kegiatan"),
            request.form.get("sasaran"),
            request.form.get("hasil_kegiatan"),
            request.form.get("tindak_lanjut"),
            request.form.get("tempat"),
            request.form.get("keterangan"),
            status
        ))

        mysql.connection.commit()
        cur.close()

        return redirect("/rencana_kerja?msg=✅ Kegiatan berhasil disimpan")

    page = int(request.args.get("page", 1) or 1)
    per_page_raw = request.args.get("per_page", "5")
    per_page = 999999 if per_page_raw == "all" else int(per_page_raw)

    bulan_filter = request.args.get("bulan", "").strip()
    tahun_filter = request.args.get("tahun", "").strip()
    mode = request.args.get("mode", "today").strip() or "today"
    status_filter = request.args.get("status", "").strip()
    kegiatan_filter = request.args.get("kegiatan", "").strip()

    filters = []
    params = []

    if is_anggota_role():
        filters.append("rencana_kerja.user_id=%s")
        params.append(session["user_id"])

    if bulan_filter.isdigit():
        filters.append("MONTH(rencana_kerja.tanggal)=%s")
        params.append(int(bulan_filter))
        mode = "all"
    if tahun_filter.isdigit():
        filters.append("YEAR(rencana_kerja.tanggal)=%s")
        params.append(int(tahun_filter))
        mode = "all"
    if status_filter == "selesai":
        filters.append("rencana_kerja.status IN ('Selesai','Dilaksanakan')")
        mode = "all"

    elif status_filter == "belum":
        filters.append("rencana_kerja.status NOT IN ('Selesai','Dilaksanakan')")
        mode = "all"

    if kegiatan_filter:
        filters.append("rencana_kerja.kegiatan=%s")
        params.append(kegiatan_filter)
        mode = "all"

    if (
        not bulan_filter.isdigit()
        and not status_filter
        and not kegiatan_filter
        and mode == "today"
    ):
        filters.append("rencana_kerja.tanggal = CURDATE()")

    where_sql = (" WHERE " + " AND ".join(filters)) if filters else ""

    select_sql = """
        SELECT
            rencana_kerja.id,
            users.nama,
            rencana_kerja.tanggal,
            rencana_kerja.jam,
            rencana_kerja.jam_selesai,
            rencana_kerja.kegiatan,
            rencana_kerja.keterangan,
            rencana_kerja.status,
            users.no_hp,
            rencana_kerja.kategori_kegiatan,
            rencana_kerja.sasaran,
            rencana_kerja.hasil_kegiatan,
            rencana_kerja.tindak_lanjut,
            rencana_kerja.tempat
        FROM rencana_kerja
        JOIN users ON rencana_kerja.user_id = users.id
    """

    cur.execute(f"""
        SELECT COUNT(*)
        FROM rencana_kerja
        JOIN users ON rencana_kerja.user_id = users.id
        {where_sql}
    """, tuple(params))

    total_rows = cur.fetchone()[0] or 0
    page, total_pages, offset = paginate(total_rows, page, per_page)

    order_sql = """
        ORDER BY
            CASE WHEN rencana_kerja.tanggal = CURDATE() THEN 0 ELSE 1 END,
            rencana_kerja.tanggal DESC,
            rencana_kerja.jam DESC,
            users.nama ASC,
            rencana_kerja.id DESC
    """

    if per_page_raw == "all":
        cur.execute(
            select_sql + where_sql + order_sql,
            tuple(params)
        )
    else:
        cur.execute(
            select_sql + where_sql + order_sql + " LIMIT %s OFFSET %s",
            tuple(params + [per_page, offset])
        )

    data = cur.fetchall()

    if is_anggota_role():
        cur.execute("""
            SELECT
              SUM(CASE WHEN status IN ('Selesai','Dilaksanakan') THEN 1 ELSE 0 END),
              SUM(CASE WHEN status NOT IN ('Selesai','Dilaksanakan') THEN 1 ELSE 0 END),
              COUNT(*)
            FROM rencana_kerja
            WHERE user_id=%s
        """, (session["user_id"],))
    else:
        cur.execute("""
            SELECT
              SUM(CASE WHEN status IN ('Selesai','Dilaksanakan') THEN 1 ELSE 0 END),
              SUM(CASE WHEN status NOT IN ('Selesai','Dilaksanakan') THEN 1 ELSE 0 END),
              COUNT(*)
            FROM rencana_kerja
        """)

    rr = cur.fetchone() or (0, 0, 0)

    rekap = {
        "selesai": rr[0] or 0,
        "belum": rr[1] or 0,
        "total": rr[2] or 0
    }

    rekap_kegiatan_bulan = []

    if is_anggota_role():
        extra_where = ""
        extra_params = [session["user_id"]]

        if bulan_filter.isdigit():
            extra_where = " AND MONTH(tanggal)=%s"
            extra_params.append(int(bulan_filter))

        cur.execute(f"""
            SELECT kegiatan, COUNT(*) AS jumlah
            FROM rencana_kerja
            WHERE user_id=%s
            AND status IN ('Selesai','Dilaksanakan')
            {extra_where}
            GROUP BY kegiatan
            ORDER BY jumlah DESC, kegiatan ASC
        """, tuple(extra_params))

        rekap_kegiatan_bulan = cur.fetchall()

    cur.execute("""
        SELECT id, nama
        FROM users
        WHERE role IN ('anggota','user')
        ORDER BY nama ASC
    """)

    users = cur.fetchall()

    cur.execute("""
        SELECT
            id,
            kategori_kegiatan,
            uraian
        FROM skp
        WHERE kategori_kegiatan IS NOT NULL
        ORDER BY kategori_kegiatan ASC, uraian ASC
    """)

    skp_options = cur.fetchall()

    cur.close()

    return render_template(
        "rencana_kerja.html",
        data=data,
        users=users,
        wa_number=wa_number,
        today=date.today(),

        rekap=rekap,
        rekap_kegiatan_bulan=rekap_kegiatan_bulan,

        bulan_filter=bulan_filter,
        bulan_nama=bulan_nama,
        tahun_filter=tahun_filter,

        mode=mode,
        status_filter=status_filter,
        kegiatan_filter=kegiatan_filter,

        page=page,
        total_pages=total_pages,
        total_rows=total_rows,
        offset=offset,
        per_page_raw=per_page_raw,

        skp_options=skp_options
    )
   # ================= SELESAI RENCANA KERJA =================
@app.route("/selesai_rencana_kerja/<int:id>")
@role_required("admin", "anggota", "user")
def selesai_rencana_kerja(id):
    cur = mysql.connection.cursor()

    if is_anggota_role():
        cur.execute("""
            UPDATE rencana_kerja
            SET status='Selesai'
            WHERE id=%s AND user_id=%s
        """, (id, session["user_id"]))
    else:
        cur.execute("""
            UPDATE rencana_kerja
            SET status='Selesai'
            WHERE id=%s
        """, (id,))

    mysql.connection.commit()
    cur.close()

    return redirect("/rencana_kerja?mode=today&msg=✅ Kegiatan selesai")


# ================= HAPUS RENCANA KERJA =================
@app.route("/hapus_rencana_kerja/<int:id>")
@role_required("admin", "anggota", "user")
def hapus_rencana_kerja(id):
    cur = mysql.connection.cursor()

    if is_anggota_role():
        cur.execute("""
            DELETE FROM rencana_kerja
            WHERE id=%s AND user_id=%s
        """, (id, session["user_id"]))
    else:
        cur.execute("""
            DELETE FROM rencana_kerja
            WHERE id=%s
        """, (id,))

    mysql.connection.commit()
    cur.close()

    return redirect("/rencana_kerja?mode=today&msg=✅ Data rencana kerja berhasil dihapus")
# ================= LAPORAN PDF =================
@app.route("/laporan")
@login_required
def laporan():
    if is_anggota_role():
        return redirect("/laporan_kegiatan?msg=ℹ️ Anggota menggunakan Laporan Kegiatan")
    return render_template("laporan.html")

@app.route("/laporan_pdf")
@login_required
def laporan_pdf():
    if is_anggota_role():
        return redirect("/laporan_kegiatan?msg=ℹ️ Anggota menggunakan Laporan Kegiatan")
    jenis = request.args.get("jenis", "iuran")
    bulan_values = bulan_values_from_request()
    cur = mysql.connection.cursor(); lines = []
    title = "Laporan IPKB"
    month_where_bayar, params_bayar = month_in_clause(bulan_order_sql('iuran'), bulan_values)
    month_where_keluar, params_keluar = month_in_clause("MONTH(tanggal)", bulan_values)
    iuran_where_bulan, params_iuran_bulan = month_in_clause(bulan_order_sql('iuran'), bulan_values)
    bulan_label = bulan_multi_label(bulan_values)
    if jenis == "pengeluaran":
        title = f"Laporan Pengeluaran IPKB - {bulan_label}"
        if table_exists(cur, 'pengeluaran'):
            cur.execute(f"SELECT tanggal, uraian, jumlah, keterangan FROM pengeluaran WHERE 1=1 {month_where_keluar} ORDER BY tanggal DESC, id DESC", tuple(params_keluar))
            lines = [f"Periode: {bulan_label}", "Tanggal | Uraian | Jumlah | Keterangan", "-"*80]
            for r in cur.fetchall()[:45]: lines.append(f"{r[0]} | {r[1]} | {rupiah(r[2])} | {r[3] or ''}")
        else:
            lines = ["Tabel pengeluaran belum tersedia."]
    elif jenis == "keuangan":
        cur.execute(f"""
            SELECT IFNULL(SUM(pembayaran.jumlah_bayar),0)
            FROM pembayaran
            JOIN iuran ON pembayaran.iuran_id=iuran.id
            WHERE 1=1 {month_where_bayar}
        """, tuple(params_bayar))
        masuk = cur.fetchone()[0] or 0
        keluar = 0
        if table_exists(cur, 'pengeluaran'):
            cur.execute(f"SELECT IFNULL(SUM(jumlah),0) FROM pengeluaran WHERE 1=1 {month_where_keluar}", tuple(params_keluar)); keluar = cur.fetchone()[0] or 0
        title = f"Laporan Keuangan IPKB - {bulan_label}"
        lines = [f"Periode      : {bulan_label}", f"Total Masuk  : {rupiah(masuk)}", f"Total Keluar : {rupiah(keluar)}", f"Saldo        : {rupiah(masuk-keluar)}", "", "Rincian Pemasukan:"]
        cur.execute(f"""
            SELECT pembayaran.tanggal, users.nama, CONCAT(iuran.bulan,' ',iuran.tahun), pembayaran.jumlah_bayar
            FROM pembayaran JOIN iuran ON pembayaran.iuran_id=iuran.id JOIN users ON iuran.user_id=users.id
            WHERE 1=1 {month_where_bayar}
            ORDER BY pembayaran.tanggal DESC, pembayaran.id DESC
        """, tuple(params_bayar))
        for r in cur.fetchall()[:25]: lines.append(f"Masuk | {r[0]} | {r[1]} | {r[2]} | {rupiah(r[3])}")
        lines.append(""); lines.append("Rincian Pengeluaran:")
        if table_exists(cur, 'pengeluaran'):
            cur.execute(f"SELECT tanggal, uraian, jumlah FROM pengeluaran WHERE 1=1 {month_where_keluar} ORDER BY tanggal DESC, id DESC", tuple(params_keluar))
            for r in cur.fetchall()[:25]: lines.append(f"Keluar | {r[0]} | {r[1]} | {rupiah(r[2])}")
    else:
        params=[]; where="WHERE 1=1"
        if is_anggota_role(): where += " AND iuran.user_id=%s"; params=[session["user_id"]]
        where += iuran_where_bulan; params += params_iuran_bulan
        cur.execute(f"""
            SELECT users.nama, iuran.bulan, iuran.tahun, iuran.jumlah, IFNULL(SUM(pembayaran.jumlah_bayar),0), (iuran.jumlah-IFNULL(SUM(pembayaran.jumlah_bayar),0))
            FROM iuran JOIN users ON iuran.user_id=users.id LEFT JOIN pembayaran ON pembayaran.iuran_id=iuran.id {where}
            GROUP BY iuran.id, users.nama, iuran.bulan, iuran.tahun, iuran.jumlah
            ORDER BY users.nama ASC, iuran.tahun DESC, {bulan_order_sql('iuran')}
        """, tuple(params))
        rows = cur.fetchall(); title = f"Laporan Iuran IPKB - {bulan_label}"
        lines = [f"Periode: {bulan_label}", "Nama | Bulan | Tahun | Tagihan | Terbayar | Sisa", "-"*82]
        for r in rows[:45]: lines.append(f"{r[0]} | {r[1]} | {r[2]} | {rupiah(r[3])} | {rupiah(r[4])} | {rupiah(r[5])}")
    cur.close()
    filename = f"laporan_{jenis}.pdf"
    return Response(make_simple_pdf(title, lines), mimetype="application/pdf", headers={"Content-Disposition": f"inline; filename={filename}"})
# ========================= LPAORAN PRINT =================

@app.route("/laporan_print")
@login_required
def laporan_print():
    if is_anggota_role():
        return redirect("/laporan_kegiatan?msg=ℹ️ Anggota menggunakan Laporan Kegiatan")
    jenis = request.args.get("jenis", "iuran")
    bulan_values = bulan_values_from_request()
    cur = mysql.connection.cursor()
    rows, rows_keluar = [], []
    totals = {"masuk": 0, "keluar": 0, "saldo": 0}
    month_where_bayar, params_bayar = month_in_clause(bulan_order_sql('iuran'), bulan_values)
    month_where_keluar, params_keluar = month_in_clause("MONTH(tanggal)", bulan_values)
    iuran_where_bulan, params_iuran_bulan = month_in_clause(bulan_order_sql('iuran'), bulan_values)
    bulan_label = bulan_multi_label(bulan_values)
    if jenis == "pengeluaran":
        if table_exists(cur, 'pengeluaran'):
            cur.execute(f"SELECT tanggal, uraian, jumlah, keterangan FROM pengeluaran WHERE 1=1 {month_where_keluar} ORDER BY tanggal DESC, id DESC", tuple(params_keluar))
            rows = cur.fetchall()
    elif jenis == "keuangan":
        cur.execute(f"""
            SELECT IFNULL(SUM(pembayaran.jumlah_bayar),0)
            FROM pembayaran
            JOIN iuran ON pembayaran.iuran_id=iuran.id
            WHERE 1=1 {month_where_bayar}
        """, tuple(params_bayar))
        totals["masuk"] = cur.fetchone()[0] or 0
        if table_exists(cur, 'pengeluaran'):
            cur.execute(f"SELECT IFNULL(SUM(jumlah),0) FROM pengeluaran WHERE 1=1 {month_where_keluar}", tuple(params_keluar))
            totals["keluar"] = cur.fetchone()[0] or 0
        totals["saldo"] = totals["masuk"] - totals["keluar"]
        cur.execute(f"""
            SELECT 'Pemasukan' AS jenis, pembayaran.tanggal, users.nama, CONCAT(iuran.bulan,' ',iuran.tahun) AS uraian, pembayaran.jumlah_bayar
            FROM pembayaran JOIN iuran ON pembayaran.iuran_id=iuran.id JOIN users ON iuran.user_id=users.id
            WHERE 1=1 {month_where_bayar}
            ORDER BY pembayaran.tanggal DESC, pembayaran.id DESC
        """, tuple(params_bayar))
        rows = cur.fetchall()
        if table_exists(cur, 'pengeluaran'):
            cur.execute(f"SELECT 'Pengeluaran' AS jenis, tanggal, '-' AS nama, uraian, jumlah FROM pengeluaran WHERE 1=1 {month_where_keluar} ORDER BY tanggal DESC, id DESC", tuple(params_keluar))
            rows_keluar = cur.fetchall()
    else:
        params=[]; where="WHERE 1=1"
        if is_anggota_role(): where += " AND iuran.user_id=%s"; params=[session["user_id"]]
        where += iuran_where_bulan; params += params_iuran_bulan
        cur.execute(f"""
            SELECT users.nama, users.nip, iuran.bulan, iuran.tahun, iuran.jumlah,
                   IFNULL(SUM(pembayaran.jumlah_bayar),0), (iuran.jumlah-IFNULL(SUM(pembayaran.jumlah_bayar),0))
            FROM iuran JOIN users ON iuran.user_id=users.id LEFT JOIN pembayaran ON pembayaran.iuran_id=iuran.id {where}
            GROUP BY iuran.id, users.nama, users.nip, iuran.bulan, iuran.tahun, iuran.jumlah
            ORDER BY users.nama ASC, iuran.tahun DESC, {bulan_order_sql('iuran')}
        """, tuple(params))
        rows = cur.fetchall()
    reporter = get_bendahara_reporter(cur)
    cur.close()
    return render_template("laporan_print.html", jenis=jenis, rows=rows, rows_keluar=rows_keluar, totals=totals, bulan_filter=','.join(map(str, bulan_values)), bulan_label=bulan_label, today=date.today(), reporter=reporter)

# ===============LPAORAN KEGIATAN

@app.route("/laporan_kegiatan")
@role_required("admin", "anggota", "user")
def laporan_kegiatan():
    cur = mysql.connection.cursor()
    bulan_filter = request.args.get("bulan", "").strip()
    params = []
    where = "WHERE rencana_kerja.status IN ('Selesai','Dilaksanakan')"
    if is_anggota_role():
        where += " AND rencana_kerja.user_id=%s"
        params.append(session["user_id"])
    if bulan_filter.isdigit():
        where += " AND MONTH(rencana_kerja.tanggal)=%s"
        params.append(int(bulan_filter))
    cur.execute(f"""
        SELECT rencana_kerja.kegiatan, COUNT(*) AS jumlah
        FROM rencana_kerja
        {where}
        GROUP BY rencana_kerja.kegiatan
        ORDER BY jumlah DESC, rencana_kerja.kegiatan ASC
    """, tuple(params))
    rekap_kegiatan = cur.fetchall()
    cur.execute(f"""
        SELECT rencana_kerja.tanggal, rencana_kerja.jam, rencana_kerja.jam_selesai,
               rencana_kerja.kegiatan, rencana_kerja.keterangan, users.nama
        FROM rencana_kerja JOIN users ON users.id=rencana_kerja.user_id
        {where}
        ORDER BY rencana_kerja.tanggal DESC, rencana_kerja.jam DESC, rencana_kerja.id DESC
    """, tuple(params))
    data = cur.fetchall()
    total = len(data)
    cur.close()
    return render_template("laporan_kegiatan.html", data=data, rekap_kegiatan=rekap_kegiatan, total=total, bulan_filter=bulan_filter, bulan_nama=bulan_nama)

# ================= PWA + NOTIFIKASI REALTIME =================
@app.route('/manifest.json')
def manifest_json():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

@app.route('/service-worker.js')
def service_worker():
    return send_from_directory('static', 'service-worker.js', mimetype='application/javascript')

@app.route('/offline')
def offline():
    return render_template('offline.html')

@app.route('/api/notifikasi')
@login_required
def api_notifikasi():
    cur = mysql.connection.cursor()
    items = []
    try:
        if is_anggota_role():
            cur.execute(f"""
                SELECT COUNT(*) FROM (
                    SELECT iuran.id, (iuran.jumlah-IFNULL(SUM(pembayaran.jumlah_bayar),0)) AS sisa
                    FROM iuran LEFT JOIN pembayaran ON pembayaran.iuran_id=iuran.id
                    WHERE iuran.user_id=%s AND {bulan_lalu_sampai_sekarang_sql('iuran')}
                    GROUP BY iuran.id, iuran.jumlah HAVING sisa > 0
                ) x
            """, (session['user_id'],))
            belum = cur.fetchone()[0] or 0
            if belum:
                items.append({'type':'tagihan','title':'Tagihan iuran belum lunas','body':f'Ada {belum} bulan/tagihan iuran yang belum lunas.', 'url':'/iuran'})
            cur.execute("""
                SELECT kegiatan, tanggal, jam, jam_selesai FROM rencana_kerja
                WHERE user_id=%s AND status NOT IN ('Selesai','Dilaksanakan')
                AND tanggal = CURDATE() AND jam IS NOT NULL AND jam <= ADDTIME(CURTIME(),'00:10:00')
                ORDER BY tanggal ASC, jam ASC LIMIT 3
            """, (session['user_id'],))
        else:
            cur.execute(f"""
                SELECT COUNT(*), COUNT(DISTINCT user_id) FROM (
                    SELECT iuran.user_id, iuran.id, (iuran.jumlah-IFNULL(SUM(pembayaran.jumlah_bayar),0)) sisa
                    FROM iuran LEFT JOIN pembayaran ON pembayaran.iuran_id=iuran.id
                    WHERE {bulan_lalu_sampai_sekarang_sql('iuran')}
                    GROUP BY iuran.user_id, iuran.id, iuran.jumlah
                    HAVING sisa > 0
                ) z
            """)
            row = cur.fetchone() or (0,0)
            belum, anggota = row[0] or 0, row[1] or 0
            if belum:
                items.append({'type':'tagihan','title':'Tagihan anggota belum lunas','body':f'Ada {belum} tagihan dari {anggota} anggota yang belum lunas.', 'url':'/belum_bayar'})
            cur.execute("""
                SELECT kegiatan, tanggal, jam, jam_selesai FROM rencana_kerja
                WHERE status NOT IN ('Selesai','Dilaksanakan')
                AND tanggal = CURDATE() AND jam IS NOT NULL AND jam <= ADDTIME(CURTIME(),'00:10:00')
                ORDER BY tanggal ASC, jam ASC LIMIT 3
            """)
        for r in cur.fetchall():
            items.append({'type':'kegiatan','title':'Pengingat kegiatan', 'body':f'{r[0]} - {r[1]} {r[2]}', 'url':'/rencana_kerja'})
    except Exception as exc:
        items.append({'type':'error','title':'Notifikasi belum siap','body':str(exc)[:120], 'url':'/'})
    finally:
        cur.close()
    return jsonify({'items': items, 'count': len(items), 'time': datetime.now().isoformat()})
@app.route("/belum_bayar")
@login_required
def belum_bayar():
    cur = mysql.connection.cursor()

    if table_exists(cur, 'users') and table_exists(cur, 'iuran'):
        ensure_iuran_jan_2026_to_current(
            cur,
            user_id=session.get("user_id") if is_anggota_role() else None
        )
        mysql.connection.commit()

    params = []
    extra_where = bulan_lalu_sampai_sekarang_sql('iuran')

    if is_anggota_role():
        extra_where += " AND iuran.user_id=%s"
        params.append(session["user_id"])

    unpaid_sql = monthly_iuran_unpaid_subquery(extra_where)

    cur.execute(f"""
        SELECT users.id, users.nama, users.nip, users.no_hp,
               COUNT(x.bulan) AS jumlah_iuran,
               IFNULL(SUM(x.sisa),0) AS total_sisa,
               GROUP_CONCAT(CONCAT(x.bulan,' ',x.tahun)
                   ORDER BY x.tahun ASC, x.urut ASC SEPARATOR ', ') AS periode
        FROM ({unpaid_sql}) x
        JOIN users ON users.id=x.user_id
        WHERE users.role IN ('anggota','user')
        GROUP BY users.id, users.nama, users.nip, users.no_hp
        ORDER BY users.nama ASC
    """, tuple(params))

    data = cur.fetchall()
    periode_label = periode_jan_2026_label()
    cur.close()

    return render_template(
        "belum_bayar.html",
        data=data,
        wa_number=wa_number,
        periode_label=periode_label
    )


@app.route("/belu_bayar")
@login_required
def belu_bayar_alias():
    return redirect("/belum_bayar")

@app.route('/wa_kirim_belum_bayar/<int:user_id>')
@role_required('bendahara', 'admin')
def wa_kirim_belum_bayar(user_id):
    cur = mysql.connection.cursor()
    if table_exists(cur, 'users') and table_exists(cur, 'iuran'):
        ensure_iuran_jan_2026_to_current(cur, user_id=user_id)
        mysql.connection.commit()

    extra = bulan_lalu_sampai_sekarang_sql('iuran') + " AND iuran.user_id=%s"
    unpaid_sql = monthly_iuran_unpaid_subquery(extra)
    cur.execute(f"""
        SELECT users.nama, users.no_hp, users.nip,
               IFNULL(SUM(x.sisa),0) AS total_sisa,
               GROUP_CONCAT(CONCAT(x.bulan,' ',x.tahun) ORDER BY x.tahun ASC, x.urut ASC SEPARATOR ', ') AS periode
        FROM ({unpaid_sql}) x
        JOIN users ON users.id=x.user_id
        WHERE users.id=%s
        GROUP BY users.id, users.nama, users.no_hp, users.nip
    """, (user_id, user_id))
    row = cur.fetchone(); cur.close()
    if not row:
        return redirect('/belum_bayar?msg=✅ Anggota sudah tidak memiliki tunggakan')
    pesan = build_tagihan_message(f"{row[0]} (NIP: {row[2]})", row[4] or '-', row[3] or 0)
    ok, msg = send_whatsapp(row[1], pesan)
    return redirect('/belum_bayar?msg=' + ('✅ WhatsApp berhasil dikirim' if ok else '❌ WhatsApp gagal: ' + msg))

@app.route('/wa_kirim_renja/<int:id>')
@login_required
def wa_kirim_renja(id):
    cur = mysql.connection.cursor()
    where = 'rencana_kerja.id=%s'
    params = [id]
    if is_anggota_role():
        where += ' AND rencana_kerja.user_id=%s'; params.append(session['user_id'])
    cur.execute(f"""
        SELECT users.nama, users.no_hp, rencana_kerja.kegiatan, rencana_kerja.tanggal,
               rencana_kerja.jam, rencana_kerja.jam_selesai
        FROM rencana_kerja JOIN users ON users.id=rencana_kerja.user_id
        WHERE {where}
    """, tuple(params))
    row = cur.fetchone(); cur.close()
    if not row:
        return redirect('/rencana_kerja?msg=❌ Kegiatan tidak ditemukan')
    ok, msg = send_whatsapp(row[1], build_renja_message(row[0], row[2], row[3], row[4], row[5]))
    return redirect('/rencana_kerja?msg=' + ('✅ Pengingat WA berhasil dikirim' if ok else '❌ Pengingat WA gagal: ' + msg))

def auto_wa_worker():
    with app.app_context():
        while True:
            try:
                if WA_AUTO_SEND and FONNTE_TOKEN:
                    cur = mysql.connection.cursor()
                    cur.execute("""
                        SELECT rencana_kerja.id, users.nama, users.no_hp, rencana_kerja.kegiatan,
                               rencana_kerja.tanggal, rencana_kerja.jam, rencana_kerja.jam_selesai
                        FROM rencana_kerja JOIN users ON users.id=rencana_kerja.user_id
                        WHERE rencana_kerja.wa_diingatkan=0
                          AND rencana_kerja.status NOT IN ('Selesai','Dilaksanakan')
                          AND rencana_kerja.tanggal = CURDATE()
                          AND rencana_kerja.jam IS NOT NULL
                          AND rencana_kerja.jam <= CURTIME()
                        LIMIT 10
                    """)
                    rows = cur.fetchall()
                    for r in rows:
                        ok, _ = send_whatsapp(r[2], build_renja_message(r[1], r[3], r[4], r[5], r[6]))
                        if ok:
                            cur.execute('UPDATE rencana_kerja SET wa_diingatkan=1 WHERE id=%s', (r[0],))
                    mysql.connection.commit(); cur.close()
            except Exception:
                pass
            time.sleep(WA_CHECK_SECONDS)


# ================= EDIT PROFIL =================
@app.route("/edit_profil", methods=["GET", "POST"])
@login_required
def edit_profil():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, nama, nip, password, role, foto FROM users WHERE id=%s", (session["user_id"],))
    user = cur.fetchone()
    if request.method == "POST":
        nama = request.form.get("nama", "").strip(); filename = user[5]
        old_password = request.form.get("password_lama", "").strip()
        new_password = request.form.get("password_baru", "").strip()
        confirm_password = request.form.get("konfirmasi_password", "").strip()
        uploaded = save_upload("foto")
        if uploaded: filename = uploaded
        if new_password:
            if not check_password_hash(user[3], old_password):
                cur.close(); return redirect("/edit_profil?msg=❌ Password lama salah")
            if new_password != confirm_password:
                cur.close(); return redirect("/edit_profil?msg=❌ Konfirmasi password tidak sama")
            cur.execute("UPDATE users SET nama=%s, foto=%s, password=%s WHERE id=%s", (nama, filename, generate_password_hash(new_password), session["user_id"]))
        else:
            cur.execute("UPDATE users SET nama=%s, foto=%s WHERE id=%s", (nama, filename, session["user_id"]))
        mysql.connection.commit(); cur.close()
        session["user"] = nama; session["foto"] = filename
        return redirect(("/iuran" if is_anggota_role() else "/dashboard") + "?msg=✅ Profil berhasil diperbarui")
    cur.close()
    return render_template("edit_profil.html", user=user)


# ================= KEGIATAN PKB =================
@app.route("/kegiatan_pkb")
@role_required("admin", "anggota", "user")
def kegiatan_pkb():

    page = int(request.args.get("page", 1) or 1)

    # ===== PER PAGE =====
    per_page_raw = request.args.get("per_page", "10")

    q = request.args.get("q", "").strip()
    kategori = request.args.get("kategori", "").strip()
    bulan = request.args.get("bulan", "").strip()

    cur = mysql.connection.cursor()

    where = []
    params = []

    if session.get("role") != "admin":
        where.append("kegiatan_pkb.user_id=%s")
        params.append(session["user_id"])

    if q:
        where.append("kegiatan_pkb.judul_kegiatan LIKE %s")
        params.append(f"%{q}%")

    if kategori:
        where.append("kegiatan_pkb.kategori_kegiatan=%s")
        params.append(kategori)

    if bulan:
        where.append("MONTH(kegiatan_pkb.tgl_mulai)=%s")
        params.append(int(bulan))

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    # ===== TOTAL DATA =====
    cur.execute(f"""
        SELECT COUNT(*)
        FROM kegiatan_pkb
        LEFT JOIN users ON kegiatan_pkb.user_id = users.id
        {where_sql}
    """, tuple(params))

    total_rows = cur.fetchone()[0] or 0

    # ===== ALL OPTION =====
    if per_page_raw == "all":
        per_page = total_rows if total_rows > 0 else 1
    else:
        per_page = int(per_page_raw)

    page, total_pages, offset = paginate(total_rows, page, per_page)

    # ===== DATA =====
    cur.execute(f"""
        SELECT
            kegiatan_pkb.id,
            kegiatan_pkb.no_kegiatan,
            kegiatan_pkb.tipe_kegiatan,
            kegiatan_pkb.kategori_kegiatan,
            kegiatan_pkb.judul_kegiatan,
            kegiatan_pkb.angka_kredit,
            kegiatan_pkb.tempat,
            kegiatan_pkb.tgl_mulai,
            kegiatan_pkb.tgl_selesai,
            kegiatan_pkb.status_kegiatan,
            users.nama
        FROM kegiatan_pkb
        LEFT JOIN users ON kegiatan_pkb.user_id = users.id
        {where_sql}
        ORDER BY kegiatan_pkb.no_kegiatan ASC, kegiatan_pkb.id ASC
        LIMIT %s OFFSET %s
    """, tuple(params + [per_page, offset]))

    data = cur.fetchall()

    # ===== KATEGORI =====
    if session.get("role") == "admin":
        cur.execute("""
            SELECT DISTINCT kategori_kegiatan
            FROM kegiatan_pkb
            WHERE kategori_kegiatan IS NOT NULL AND kategori_kegiatan <> ''
            ORDER BY kategori_kegiatan ASC
        """)
    else:
        cur.execute("""
            SELECT DISTINCT kategori_kegiatan
            FROM kegiatan_pkb
            WHERE user_id=%s
            AND kategori_kegiatan IS NOT NULL
            AND kategori_kegiatan <> ''
            ORDER BY kategori_kegiatan ASC
        """, (session["user_id"],))

    kategori_list = cur.fetchall()
    cur.close()

    return render_template(
        "kegiatan_pkb.html",
        data=data,
        page=page,
        total_pages=total_pages,
        total_rows=total_rows,
        offset=offset,
        per_page=per_page,
        per_page_raw=per_page_raw,
        q=q,
        kategori=kategori,
        bulan=bulan,
        kategori_list=kategori_list
    )
# ================= UPLOAD KEGIATAN =================
@app.route("/upload_kegiatan", methods=["GET", "POST"])
@role_required("anggota", "user")
def upload_kegiatan():

    def bersih(nilai):
        if pd.isna(nilai):
            return None
        return str(nilai).strip()

    def angka(nilai):
        try:
            if pd.isna(nilai):
                return 0
            return float(nilai)
        except:
            return 0

    def tanggal(nilai):
        if pd.isna(nilai):
            return None
        try:
            return pd.to_datetime(nilai, dayfirst=True).strftime("%Y-%m-%d %H:%M:%S")
        except:
            return None

    if request.method == "POST":

        file = request.files.get("file_excel")

        if not file or file.filename == "":
            return redirect("/upload_kegiatan?msg=❌ File Excel wajib dipilih")

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".xlsx", ".xls"]:
            return redirect("/upload_kegiatan?msg=❌ Hanya file Excel (.xlsx / .xls)")

        try:
            # Header Excel ada di baris ke-6
            df = pd.read_excel(file, header=5)
            df.columns = df.columns.astype(str).str.strip()
            df = df.dropna(how="all")

            cur = mysql.connection.cursor()

            cur.execute("DELETE FROM kegiatan_pkb WHERE user_id=%s", (session["user_id"],))

            total = 0

            for _, row in df.iterrows():

                if pd.isna(row.get("No")):
                    continue

                cur.execute("""
                    INSERT INTO kegiatan_pkb (
                        user_id, no_kegiatan, tipe_kegiatan, kategori_kegiatan,
                        iki, judul_kegiatan, butir_kegiatan, langkah_kerja,
                        angka_kredit, deskripsi, sasaran, tempat,
                        tgl_mulai, tgl_selesai, hasil_kegiatan,
                        tindak_lanjut, status_kegiatan, sync_date
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    session["user_id"],
                    int(row["No"]),
                    bersih(row.get("Tipe Kegiatan")),
                    bersih(row.get("Kategori Kegiatan")),
                    bersih(row.get("IKI")),
                    bersih(row.get("Judul Kegiatan")),
                    bersih(row.get("Butir Kegiatan Jenjang Jabatan")),
                    bersih(row.get("Langkah Kerja")),
                    angka(row.get("Angka Kredit")),
                    bersih(row.get("Deskripsi")),
                    bersih(row.get("Sasaran")),
                    bersih(row.get("Tempat")),
                    tanggal(row.get("Tgl Mulai")),
                    tanggal(row.get("Tgl Selesai")),
                    bersih(row.get("Hasil Kegiatan")),
                    bersih(row.get("Tindak Lanjut")),
                    bersih(row.get("Status")),
                    tanggal(row.get("Sync Date"))
                ))

                total += 1

            mysql.connection.commit()
            cur.close()

            return redirect(f"/kegiatan_pkb?msg=✅ {total} data berhasil diupload")

        except Exception as e:
            try:
                mysql.connection.rollback()
            except:
                pass
            return redirect(f"/upload_kegiatan?msg=❌ Upload gagal: {str(e)}")

    return render_template("upload_kegiatan.html")

# ================= ARSIP DIGITAL =================
@app.route("/arsip_digital", methods=["GET", "POST"])
@role_required("admin", "anggota", "user")
def arsip_digital():

    page = int(request.args.get("page", 1) or 1)
    per_page_raw = request.args.get("per_page", "5")
    q = request.args.get("q", "").strip()
    kategori = request.args.get("kategori", "").strip()

    per_page = 999999 if per_page_raw == "all" else int(per_page_raw)

    cur = mysql.connection.cursor()

    if request.method == "POST":
        nama_file = request.form.get("nama_file", "").strip()
        kategori_id = request.form.get("kategori_id")
        file = request.files.get("file_upload")

        if not nama_file:
            return redirect("/arsip_digital?msg=❌ Nama file wajib diisi")

        if not kategori_id:
            return redirect("/arsip_digital?msg=❌ Kategori wajib dipilih")

        if not file or file.filename == "":
            return redirect("/arsip_digital?msg=❌ File wajib diupload")

        filename = f"{int(time.time())}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        cur.execute("""
            INSERT INTO arsip_digital (user_id, kategori_id, nama_file, file_upload)
            VALUES (%s,%s,%s,%s)
        """, (session["user_id"], kategori_id, nama_file, filename))

        mysql.connection.commit()
        cur.close()

        return redirect("/arsip_digital?msg=✅ Arsip berhasil diupload")

    where = []
    params = []

    if session.get("role") != "admin":
        where.append("arsip_digital.user_id=%s")
        params.append(session["user_id"])

    if q:
        where.append("arsip_digital.nama_file LIKE %s")
        params.append(f"%{q}%")

    if kategori:
        where.append("arsip_digital.kategori_id=%s")
        params.append(kategori)

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    cur.execute(f"""
        SELECT COUNT(*)
        FROM arsip_digital
        LEFT JOIN kategori_arsip ON arsip_digital.kategori_id = kategori_arsip.id
        {where_sql}
    """, tuple(params))

    total_rows = cur.fetchone()[0] or 0

    page, total_pages, offset = paginate(total_rows, page, per_page)

    order_sql = """
        ORDER BY arsip_digital.id DESC
    """

    if per_page_raw == "all":
        cur.execute(f"""
            SELECT
                arsip_digital.id,
                arsip_digital.nama_file,
                arsip_digital.file_upload,
                arsip_digital.created_at,
                kategori_arsip.nama_kategori,
                users.nama,
                arsip_digital.kategori_id
            FROM arsip_digital
            LEFT JOIN kategori_arsip ON arsip_digital.kategori_id = kategori_arsip.id
            LEFT JOIN users ON arsip_digital.user_id = users.id
            {where_sql}
            {order_sql}
        """, tuple(params))
    else:
        cur.execute(f"""
            SELECT
                arsip_digital.id,
                arsip_digital.nama_file,
                arsip_digital.file_upload,
                arsip_digital.created_at,
                kategori_arsip.nama_kategori,
                users.nama,
                arsip_digital.kategori_id
            FROM arsip_digital
            LEFT JOIN kategori_arsip ON arsip_digital.kategori_id = kategori_arsip.id
            LEFT JOIN users ON arsip_digital.user_id = users.id
            {where_sql}
            {order_sql}
            LIMIT %s OFFSET %s
        """, tuple(params + [per_page, offset]))

    data = cur.fetchall()

    cur.execute("""
        SELECT id, nama_kategori
        FROM kategori_arsip
        ORDER BY nama_kategori ASC
    """)
    kategori_list = cur.fetchall()

    cur.close()

    return render_template(
        "arsip_digital.html",
        data=data,
        kategori_list=kategori_list,
        kategori=kategori,
        q=q,
        page=page,
        total_pages=total_pages,
        total_rows=total_rows,
        offset=offset,
        per_page_raw=per_page_raw
    )
@app.route("/edit_arsip/<int:id>", methods=["POST"])
@role_required("admin", "anggota", "user")
def edit_arsip(id):
    cur = mysql.connection.cursor()

    nama_file = request.form.get("nama_file", "").strip()
    kategori_id = request.form.get("kategori_id")
    file = request.files.get("file_upload")

    if is_anggota_role():
        cur.execute("SELECT file_upload FROM arsip_digital WHERE id=%s AND user_id=%s", (id, session["user_id"]))
    else:
        cur.execute("SELECT file_upload FROM arsip_digital WHERE id=%s", (id,))

    old = cur.fetchone()

    if not old:
        cur.close()
        return redirect("/arsip_digital?msg=❌ Data arsip tidak ditemukan")

    filename = old[0]

    if file and file.filename:
        filename = f"{int(time.time())}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    if is_anggota_role():
        cur.execute("""
            UPDATE arsip_digital
            SET kategori_id=%s, nama_file=%s, file_upload=%s
            WHERE id=%s AND user_id=%s
        """, (kategori_id, nama_file, filename, id, session["user_id"]))
    else:
        cur.execute("""
            UPDATE arsip_digital
            SET kategori_id=%s, nama_file=%s, file_upload=%s
            WHERE id=%s
        """, (kategori_id, nama_file, filename, id))

    mysql.connection.commit()
    cur.close()

    return redirect("/arsip_digital?msg=✅ Arsip berhasil diubah")


@app.route("/hapus_arsip/<int:id>")
@role_required("admin", "anggota", "user")
def hapus_arsip(id):
    cur = mysql.connection.cursor()

    if is_anggota_role():
        cur.execute("DELETE FROM arsip_digital WHERE id=%s AND user_id=%s", (id, session["user_id"]))
    else:
        cur.execute("DELETE FROM arsip_digital WHERE id=%s", (id,))

    mysql.connection.commit()
    cur.close()

    return redirect("/arsip_digital?msg=✅ Arsip berhasil dihapus")
    # =-============ UPLOAD SKP PDF ===============#
@app.route("/upload_skp_pdf", methods=["GET", "POST"])
@role_required("admin", "anggota", "user")
def upload_skp_pdf():
    if request.method == "POST":
        file = request.files.get("file_pdf")
        tahun = request.form.get("tahun") or date.today().year
        bulan = request.form.get("bulan") or date.today().month

        if not file or file.filename == "":
            return redirect("/skp?msg=❌ File PDF wajib dipilih")

        filename = f"{int(time.time())}_{secure_filename(file.filename)}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        rows = []

        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines = text.split("\n")

                for line in lines:
                    line = line.strip()

                    if "Kuantitas" in line:
                        isi = line.split("Kuantitas", 1)[1].strip()

                        target_match = re.search(r"(\d+\s*(laporan|Laporan|JP))$", isi)

                        if target_match:
                            target = target_match.group(1)
                            uraian = isi.replace(target, "").strip()
                        else:
                            target = ""
                            uraian = isi

                        if uraian:
                            rows.append((uraian, target))

        if not rows:
            return redirect("/skp?msg=❌ Data SKP tidak terbaca dari PDF")

        cur = mysql.connection.cursor()
        user_id = session["user_id"] if is_anggota_role() else request.form.get("user_id")

        for uraian, target in rows:
            cur.execute("""
                INSERT INTO skp
                (
                    user_id,
                    tahun,
                    bulan,
                    kategori_kegiatan,
                    uraian,
                    target,
                    capaian,
                    sasaran,
                    hasil_kegiatan,
                    tindak_lanjut,
                    lokasi_kegiatan
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                user_id,
                tahun,
                bulan,
                "SKP",
                uraian,
                target,
                "",
                "-",
                target,
                "-",
                "-"
            ))

        mysql.connection.commit()
        cur.close()

        return redirect(f"/skp?msg=✅ {len(rows)} data SKP berhasil diupload")

    return render_template("upload_skp_pdf.html")
    
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if not getattr(app, "_wa_thread_started", False):
    app._wa_thread_started = True
    threading.Thread(target=auto_wa_worker, daemon=True).start()

if __name__ == "__main__":
    app.run(debug=True)
