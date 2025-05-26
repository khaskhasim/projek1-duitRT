from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from sqlalchemy.sql import extract
from collections import defaultdict
from flask_migrate import Migrate
import calendar
from flask import render_template, request
from io import BytesIO
import pandas as pd
from fpdf import FPDF  # install via pip install fpdf
import xlsxwriter
import io
import csv
import sqlite3
from flask_bcrypt import Bcrypt
from sqlalchemy import func, extract, desc, literal
from pytz import timezone
import calendar



db = SQLAlchemy()

app = Flask(__name__)
bcrypt = Bcrypt(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kas_rt.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'rahasia-sangat-rahasia'  # Tambahkan secret key
db = SQLAlchemy(app)
migrate = Migrate(app, db)  # Pindahkan ke sini untuk inisialisasi yang benar

# =====================
# MODEL DATABASE
# =====================
class Warga(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    nik = db.Column(db.String(30), unique=True)
    alamat = db.Column(db.String(255))
    telepon = db.Column(db.String(30))
    status = db.Column(db.String(20), default='aktif')
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user')



# Model Iuran
class Iuran(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    warga_id = db.Column(db.Integer, db.ForeignKey('warga.id'), nullable=False)
    tanggal = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    jumlah = db.Column(db.Integer, nullable=False)
    petugas = db.Column(db.String(100), nullable=True)  

    # Relasi ke model Warga
    warga = db.relationship('Warga', backref=db.backref('iurans', lazy=True))


# Model Pengeluaran
class Pengeluaran(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    warga_id = db.Column(db.Integer, db.ForeignKey('warga.id'), nullable=True)
    keterangan = db.Column(db.String(200), nullable=False)
    penerima = db.Column(db.String(100), nullable=True)
    tanggal = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    jumlah = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    petugas = db.Column(db.String(50))  # tambahkan ini bila belum ada

    warga = db.relationship('Warga', backref=db.backref('pengeluarans', lazy=True))




class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'user', atau 'petugas'


# =====================
# ROUTES
# =====================

app.secret_key = 'rahasia'  # Ganti dengan secret key aman

def insert_default_users():
    # Admin
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password=bcrypt.generate_password_hash('admin123').decode('utf-8'),
            role='admin'
        )
        db.session.add(admin)

    # Petugas
    if not User.query.filter_by(username='petugas1').first():
        petugas = User(
            username='petugas1',
            password=bcrypt.generate_password_hash('petugas123').decode('utf-8'),
            role='petugas'
        )
        db.session.add(petugas)

    # Warga (user biasa)
    if not User.query.filter_by(username='warga1').first():
        warga = User(
            username='warga1',
            password=bcrypt.generate_password_hash('warga123').decode('utf-8'),
            role='user'
        )
        db.session.add(warga)

    db.session.commit()





from pytz import timezone
from sqlalchemy import literal

def get_aktivitas_terkini(limit=10):
    zona_wib = timezone('Asia/Jakarta')

    iuran_data = (
        db.session.query(
            Iuran.tanggal,
            Iuran.jumlah,
            Warga.nama.label('nama'),
            Iuran.petugas,
            literal('Iuran').label('jenis')
        )
        .join(Warga)
        .order_by(Iuran.tanggal.desc())
        .limit(limit)
        .all()
    )

    pengeluaran_data = (
        db.session.query(
            Pengeluaran.tanggal,
            Pengeluaran.jumlah,
            Pengeluaran.keterangan.label('nama'),
            Pengeluaran.petugas,
            literal('Pengeluaran').label('jenis')
        )
        .order_by(Pengeluaran.tanggal.desc())
        .limit(limit)
        .all()
    )

    gabung = iuran_data + pengeluaran_data
    gabung.sort(key=lambda x: x.tanggal, reverse=True)

    aktivitas = []
    for item in gabung[:limit]:
        waktu = item.tanggal.astimezone(zona_wib).strftime('%d/%m/%Y %H:%M')
        petugas = item.petugas or "Tidak Diketahui"

        if item.jenis == 'Iuran':
            keterangan = f"💰 {item.nama} membayar iuran Rp {item.jumlah:,} (oleh {petugas})"
            warna = "success"
            ikon = "bi-cash-coin"
        else:
            keterangan = f"🧾 Pengeluaran: {item.nama} Rp {item.jumlah:,} (oleh {petugas})"
            warna = "danger"
            ikon = "bi-credit-card-2-front"

        aktivitas.append({
            "keterangan": keterangan,
            "waktu": waktu,
            "icon": ikon,
            "color": warna
        })

    return aktivitas





@app.route('/')
def index():
    return redirect(url_for('dashboard'))



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pw = request.form['password']

        # ✅ Cek tabel User (admin/petugas)
        user = User.query.filter_by(username=uname).first()
        if user and bcrypt.check_password_hash(user.password, pw):
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('dashboard'))

        # ✅ Cek tabel Warga (jika warga juga bisa login)
        warga = Warga.query.filter_by(username=uname).first()
        if warga and bcrypt.check_password_hash(warga.password, pw):
            session['username'] = warga.username
            session['role'] = warga.role
            return redirect(url_for('dashboard'))

        flash('Username atau password salah', 'danger')

    return render_template('login.html')



@app.route('/logout')
def logout():
    session.pop('username', None)  # Hapus session
    flash('Anda telah logout', 'success')  # Opsional: tampilkan pesan
    return redirect(url_for('login'))


@app.context_processor
def inject_datetime():
    return dict(datetime=datetime, date=date)




@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    role = session.get('role')

    if role == 'admin':
        total_warga = db.session.query(func.count(Warga.id)).scalar() or 0
        warga_aktif = db.session.query(func.count(Warga.id)).filter(Warga.status == 'aktif').scalar() or 0
        total_iuran = db.session.query(func.sum(Iuran.jumlah)).scalar() or 0
        total_pengeluaran = db.session.query(func.sum(Pengeluaran.jumlah)).scalar() or 0
        sisa_kas = total_iuran - total_pengeluaran

        bulan_ini = datetime.now(timezone('Asia/Jakarta')).month
        iuran_bulan_ini = db.session.query(func.sum(Iuran.jumlah)).filter(
            extract('month', Iuran.tanggal) == bulan_ini
        ).scalar() or 0

        target_iuran = total_warga * 600000
        persentase_iuran_bulan_ini = round((iuran_bulan_ini / target_iuran) * 100) if target_iuran > 0 else 0

        pengeluaran_bulan_ini = db.session.query(func.sum(Pengeluaran.jumlah)).filter(
            extract('month', Pengeluaran.tanggal) == bulan_ini
        ).scalar() or 0

        anggaran_bulanan = 200000
        persentase_pengeluaran_bulan_ini = round((pengeluaran_bulan_ini / anggaran_bulanan) * 100) if anggaran_bulanan > 0 else 0

        warga_bayar_bulan_ini = db.session.query(Iuran.warga_id).filter(
            extract('month', Iuran.tanggal) == bulan_ini
        ).distinct().count()

        persentase_warga_aktif = round((warga_bayar_bulan_ini / warga_aktif) * 100) if warga_aktif > 0 else 0

        aktivitas_terkini = get_aktivitas_terkini()

        return render_template("dashboard.html",
            jumlah_warga=total_warga,
            total_iuran=total_iuran,
            total_pengeluaran=total_pengeluaran,
            sisa_kas=sisa_kas,
            persentase_warga_aktif=persentase_warga_aktif,
            persentase_iuran_bulan_ini=persentase_iuran_bulan_ini,
            persentase_pengeluaran_bulan_ini=persentase_pengeluaran_bulan_ini,
            aktivitas_terkini=aktivitas_terkini
        )

    elif role == 'petugas':
        return render_template('dashboard_petugas.html')

    elif role == 'user':
        return render_template('dashboard_user.html')

    else:
        flash("Peran tidak dikenali", "danger")
        return redirect(url_for('logout'))


@app.route('/input_iuran_petugas', methods=['GET', 'POST'])
def input_iuran_petugas():
    if 'username' not in session or session.get('role') not in ['petugas', 'admin']:
        flash("Akses ditolak", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        nama = request.form['nama'].strip()
        try:
            total_bayar = int(request.form['total_bayar'])
            jumlah_minggu = int(request.form['jumlah_minggu'])
        except ValueError:
            flash("Input tidak valid", "danger")
            return redirect(url_for('input_iuran_petugas'))

        if total_bayar < 2000 or jumlah_minggu < 1:
            flash("Minimal iuran total Rp 2.000 dan jumlah minggu minimal 1", "danger")
            return redirect(url_for('input_iuran_petugas'))

        per_minggu = total_bayar // jumlah_minggu

        if per_minggu < 2000:
            flash(f"Iuran per minggu Rp {per_minggu:,} terlalu kecil. Minimal Rp 2.000", "danger")
            return redirect(url_for('input_iuran_petugas'))

        if per_minggu > 5000:
            min_minggu = (total_bayar + 4999) // 5000
            flash(f"Iuran per minggu Rp {per_minggu:,} melebihi Rp 5.000. Coba gunakan minimal {min_minggu} minggu", "danger")
            return redirect(url_for('input_iuran_petugas'))

        warga = Warga.query.filter_by(nama=nama).first()
        if not warga:
            flash(f"Warga dengan nama '{nama}' tidak ditemukan", 'danger')
            return redirect(url_for('input_iuran_petugas'))

        # WIB time zone
        zona_wib = timezone('Asia/Jakarta')
        minggu_bentrok = []

        for i in range(jumlah_minggu):
            tanggal = datetime.now(zona_wib) + timedelta(weeks=i)
            tahun = tanggal.year
            bulan = tanggal.month
            minggu_ke = ((tanggal.day - 1) // 7) + 1

            iuran_minggu_ini = Iuran.query.filter(
                Iuran.warga_id == warga.id,
                extract('year', Iuran.tanggal) == tahun,
                extract('month', Iuran.tanggal) == bulan,
                ((extract('day', Iuran.tanggal) - 1) // 7 + 1) == minggu_ke
            ).first()

            if iuran_minggu_ini:
                minggu_bentrok.append(f"Minggu ke-{minggu_ke} ({tanggal.strftime('%d/%m')})")

        if minggu_bentrok:
            flash(f"❌ Pembayaran ditolak! Warga sudah bayar di: {', '.join(minggu_bentrok)}", "danger")
            return redirect(url_for('input_iuran_petugas'))

        # ✅ Catat semua minggu yang valid
        for i in range(jumlah_minggu):
            tanggal = datetime.now(zona_wib) + timedelta(weeks=i)
            db.session.add(Iuran(
                warga_id=warga.id,
                jumlah=per_minggu,
                tanggal=tanggal,
                petugas=session['username']
            ))

        db.session.commit()
        flash("✅ Iuran berhasil dicatat", "success")
        return redirect(url_for('input_iuran_petugas'))

    return render_template('input_iuran_petugas.html')



@app.route('/daftar_iuran')
def daftar_iuran():
    if 'username' not in session or session.get('role') not in ['admin', 'petugas']:
        flash("Akses ditolak", "danger")
        return redirect(url_for('login'))

    iurans = Iuran.query.order_by(Iuran.tanggal.desc()).all()
    return render_template('daftar_iuran.html', iurans=iurans)

@app.route('/iuran/edit/<int:id>', methods=['GET', 'POST'])
def edit_iuran(id):
    if 'username' not in session or session.get('role') not in ['admin', 'petugas']:
        flash("Akses ditolak", "danger")
        return redirect(url_for('login'))

    iuran = Iuran.query.get_or_404(id)

    if request.method == 'POST':
        try:
            iuran.jumlah = int(request.form['jumlah'])
            iuran.tanggal = datetime.strptime(request.form['tanggal'], '%Y-%m-%d').date()
            db.session.commit()
            flash("Data iuran berhasil diperbarui", "success")
            return redirect(url_for('daftar_iuran'))
        except Exception as e:
            flash(f"Gagal mengupdate: {str(e)}", "danger")

    return render_template('edit_iuran.html', iuran=iuran)

@app.route('/iuran/hapus/<int:id>', methods=['POST'])
def hapus_iuran(id):
    if 'username' not in session or session.get('role') not in ['admin', 'petugas']:
        flash("Akses ditolak", "danger")
        return redirect(url_for('login'))

    iuran = Iuran.query.get_or_404(id)
    try:
        db.session.delete(iuran)
        db.session.commit()
        flash("Data iuran berhasil dihapus", "success")
    except Exception as e:
        flash(f"Gagal menghapus: {str(e)}", "danger")
    return redirect(url_for('daftar_iuran'))



@app.route('/autocomplete-nama')
def autocomplete_nama():
    query = request.args.get('q', '')
    if query:
        hasil = Warga.query.filter(Warga.nama.ilike(f'%{query}%')).all()
        nama_list = [warga.nama for warga in hasil]
    else:
        nama_list = []
    return jsonify(nama_list)

@app.route('/laporan')
def laporan():
    bulan = request.args.get('bulan', default=date.today().month, type=int)
    tahun = request.args.get('tahun', default=date.today().year, type=int)

    # Rentang tanggal berdasarkan bulan & tahun
    start_date = date(tahun, bulan, 1)
    end_date = date(tahun, bulan, calendar.monthrange(tahun, bulan)[1])

    # Query data sesuai rentang
    pemasukan = Iuran.query.filter(Iuran.tanggal.between(start_date, end_date)).all()
    pengeluaran = Pengeluaran.query.filter(Pengeluaran.tanggal.between(start_date, end_date)).all()

    # Hitung total
    total_pemasukan = sum(i.jumlah for i in pemasukan)
    total_pengeluaran = sum(p.jumlah for p in pengeluaran)
    saldo_kas = total_pemasukan - total_pengeluaran
    total_transaksi = len(pemasukan) + len(pengeluaran)

    # Untuk grafik mingguan
    labels = [f"Minggu {i}" for i in range(1, 6)]
    pemasukan_data = [0] * 5
    pengeluaran_data = [0] * 5
    for i in pemasukan:
        week = ((i.tanggal.day - 1) // 7)
        pemasukan_data[week] += i.jumlah
    for p in pengeluaran:
        week = ((p.tanggal.day - 1) // 7)
        pengeluaran_data[week] += p.jumlah

    return render_template('laporan.html',
        pemasukan=pemasukan,
        pengeluaran=pengeluaran,
        total_pemasukan=total_pemasukan,
        total_pengeluaran=total_pengeluaran,
        saldo_kas=saldo_kas,
        total_transaksi=total_transaksi,
        labels=labels,
        pemasukan_data=pemasukan_data,
        pengeluaran_data=pengeluaran_data,
        bulan=bulan,
        tahun=tahun,
        date=date,
        datetime=datetime
    )




@app.route('/laporan_iuran_perminggu')
def laporan_iuran_perminggu():
    bulan = request.args.get('bulan', type=int, default=datetime.now().month)
    tahun = request.args.get('tahun', type=int, default=datetime.now().year)

    iurans = Iuran.query.join(Warga).filter(
        extract('month', Iuran.tanggal) == bulan,
        extract('year', Iuran.tanggal) == tahun
    ).order_by(Iuran.tanggal).all()

    from collections import defaultdict
    data = defaultdict(lambda: defaultdict(int))

    for iuran in iurans:
        if iuran.warga:  # Hindari error jika relasi kosong
            minggu_ke = ((iuran.tanggal.day - 1) // 7) + 1
            data[iuran.warga.nama][minggu_ke] += iuran.jumlah

    minggu_labels = ['Minggu 1', 'Minggu 2', 'Minggu 3', 'Minggu 4', 'Minggu 5']

    return render_template("laporan_iuran_perminggu.html",  # pastikan ini sesuai nama file HTML
        data=data,
        bulan=bulan,
        tahun=tahun,
        minggu_labels=minggu_labels,
        datetime=datetime
    )


@app.route('/laporan_input_petugas')
def laporan_input_petugas():
    bulan = request.args.get('bulan', default=date.today().month, type=int)
    tahun = request.args.get('tahun', default=date.today().year, type=int)

    # Ambil semua iuran bulan dan tahun tertentu
    awal_bulan = date(tahun, bulan, 1)
    akhir_bulan = date(tahun, bulan, calendar.monthrange(tahun, bulan)[1])

    iurans = Iuran.query.filter(Iuran.tanggal.between(awal_bulan, akhir_bulan)).all()

    # Mapping petugas → minggu → total
    from collections import defaultdict
    data = defaultdict(lambda: defaultdict(int))

    for iuran in iurans:
        # ❗ Gunakan petugas dari field Iuran.petugas, bukan warga.username
        petugas = iuran.petugas or "Tidak Diketahui"

        minggu_ke = ((iuran.tanggal.day - 1) // 7) + 1
        data[petugas][minggu_ke] += iuran.jumlah

    minggu_labels = [f"Minggu {i}" for i in range(1, 6)]

    return render_template("laporan_input_petugas.html",
        data=data,
        minggu_labels=minggu_labels,
        bulan=bulan,
        tahun=tahun,
        datetime=datetime
    )


@app.route('/admin')
def dashboard_admin():
    if 'username' not in session or session.get('role') != 'admin':
        flash("Akses ditolak", "danger")
        return redirect(url_for('login'))

    total_warga = Warga.query.count()
    total_iuran = db.session.query(func.sum(Iuran.jumlah)).scalar() or 0
    total_pengeluaran = db.session.query(func.sum(Pengeluaran.jumlah)).scalar() or 0
    sisa_kas = total_iuran - total_pengeluaran

    # Perhitungan statistik mingguan (bulan ini)
    from collections import defaultdict
    bulan_ini = datetime.now().month
    tahun_ini = datetime.now().year

    iurans = Iuran.query.filter(
        extract('month', Iuran.tanggal) == bulan_ini,
        extract('year', Iuran.tanggal) == tahun_ini
    ).all()

    pengeluarans = Pengeluaran.query.filter(
        extract('month', Pengeluaran.tanggal) == bulan_ini,
        extract('year', Pengeluaran.tanggal) == tahun_ini
    ).all()

    mingguan_iuran = defaultdict(int)
    mingguan_pengeluaran = defaultdict(int)

    for i in iurans:
        minggu = ((i.tanggal.day - 1) // 7) + 1
        mingguan_iuran[minggu] += i.jumlah

    for p in pengeluarans:
        minggu = ((p.tanggal.day - 1) // 7) + 1
        mingguan_pengeluaran[minggu] += p.jumlah

    labels = [f"Minggu {i}" for i in range(1, 6)]
    data_iuran = [mingguan_iuran[i] for i in range(1, 6)]
    data_pengeluaran = [mingguan_pengeluaran[i] for i in range(1, 6)]

    return render_template("dashboard_admin.html",
        username=session['username'],
        total_warga=total_warga,
        total_iuran=total_iuran,
        total_pengeluaran=total_pengeluaran,
        sisa_kas=sisa_kas,
        labels=labels,
        data_iuran=data_iuran,
        data_pengeluaran=data_pengeluaran
    )



@app.route('/data_warga', methods=['GET', 'POST'])
def data_warga():
    if request.method == 'POST':
        nama = request.form['nama']
        nik = request.form.get('nik') or None
        alamat = request.form.get('alamat') or None
        telepon = request.form.get('telepon') or None
        status = request.form.get('status', 'aktif')
        username = request.form['username']
        raw_password = request.form['password']

        # Validasi unik username
        if Warga.query.filter_by(username=username).first():
            flash("Username sudah digunakan. Gunakan username lain.", "danger")
            return redirect(url_for('data_warga'))

        # Hash password
        hashed_pw = bcrypt.generate_password_hash(raw_password).decode('utf-8')

        warga = Warga(
            nama=nama,
            nik=nik,
            alamat=alamat,
            telepon=telepon,
            status=status,
            username=username,
            password=hashed_pw,
            role='user'
        )
        db.session.add(warga)
        db.session.commit()

        flash("Data warga berhasil disimpan", "success")
        return redirect(url_for('data_warga'))

    # GET: tampilkan daftar warga
    wargas = Warga.query.order_by(Warga.nama).all()
    return render_template('warga.html', wargas=wargas)


@app.route('/tambah_warga', methods=['POST'])
def tambah_warga():
    nama = request.form['nama']
    nik = request.form['nik']
    alamat = request.form['alamat']
    telepon = request.form['telepon']
    status = request.form['status']
    username = request.form['username']
    raw_password = request.form['password']

    # Hash password sebelum disimpan
    hashed_pw = bcrypt.generate_password_hash(raw_password).decode('utf-8')

    # Cek jika username sudah digunakan
    existing = Warga.query.filter_by(username=username).first()
    if existing:
        flash('Username sudah digunakan, silakan pilih yang lain', 'danger')
        return redirect(url_for('data_warga'))

    warga = Warga(
        nama=nama,
        nik=nik,
        alamat=alamat,
        telepon=telepon,
        status=status,
        username=username,
        password=hashed_pw,
        role='user'
    )
    db.session.add(warga)
    db.session.commit()

    flash("Warga berhasil ditambahkan", "success")
    return redirect(url_for('data_warga'))



@app.route('/warga/edit/<int:id>', methods=['GET', 'POST'])
def edit_warga(id):
    warga = Warga.query.get_or_404(id)
    
    if request.method == 'POST':
        warga.nama = request.form['nama']
        nik = request.form.get('nik', '').strip()
        nik = nik if nik else None

        # Validasi NIK unik hanya jika berubah
        if nik and nik != warga.nik and Warga.query.filter_by(nik=nik).first():
            flash('NIK sudah terdaftar', 'danger')
            return redirect(url_for('edit_warga', id=id))
        
        warga.nik = nik
        warga.alamat = request.form['alamat']
        warga.telepon = request.form.get('telepon', '').strip()
        warga.status = request.form['status']
        warga.username = request.form['username']

        # Update password jika diisi
        if request.form['password']:
            warga.password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        
        db.session.commit()
        flash('Data warga berhasil diperbarui', 'success')
        return redirect(url_for('data_warga'))
    
    return render_template('edit_warga.html', warga=warga)

@app.route('/warga/hapus/<int:id>', methods=['POST'])
def hapus_warga(id):
    warga = Warga.query.get_or_404(id)
    db.session.delete(warga)
    db.session.commit()
    flash('Data warga berhasil dihapus', 'success')
    return redirect(url_for('data_warga'))


# Route Pengeluaran
@app.route('/pengeluaran/tambah', methods=['GET', 'POST'])
def tambah_pengeluaran():
    if request.method == 'POST':
        try:
            zona_wib = timezone('Asia/Jakarta')
            keterangan = request.form['keterangan'].strip()
            penerima = request.form['penerima'].strip()
            tanggal_str = request.form['tanggal']  # dari input HTML (format: YYYY-MM-DD)

            # Gabungkan tanggal dengan waktu saat ini
            tanggal_tanpa_jam = datetime.strptime(tanggal_str, '%Y-%m-%d')
            jam_sekarang = datetime.now(zona_wib).time()
            tanggal_full = datetime.combine(tanggal_tanpa_jam, jam_sekarang)
            tanggal_full = zona_wib.localize(tanggal_full)

            jumlah = int(request.form['jumlah'])

            if not keterangan or not penerima:
                flash('Keterangan dan Penerima tidak boleh kosong', 'danger')
                return redirect(url_for('tambah_pengeluaran'))

            if jumlah < 1000:
                flash('Jumlah pengeluaran minimal Rp 1.000', 'danger')
                return redirect(url_for('tambah_pengeluaran'))

            # Ambil petugas dari session
            petugas = session.get('username') if session.get('role') in ['admin', 'petugas'] else None

            pengeluaran_baru = Pengeluaran(
                keterangan=keterangan,
                penerima=penerima,
                tanggal=tanggal_full,
                jumlah=jumlah,
                petugas=petugas
            )

            db.session.add(pengeluaran_baru)
            db.session.commit()

            flash('Pengeluaran berhasil dicatat!', 'success')
            return redirect(url_for('daftar_pengeluaran'))

        except ValueError:
            flash('Format input tidak valid', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Terjadi kesalahan: {str(e)}', 'danger')

    return render_template('tambah_pengeluaran.html', date=datetime.now(timezone('Asia/Jakarta')))


@app.route('/pengeluaran')
def daftar_pengeluaran():
    # Dapatkan parameter filter
    bulan = request.args.get('bulan', type=int)
    tahun = request.args.get('tahun', type=int)
    
    # Query dengan filter
    query = Pengeluaran.query
    
    if bulan:
        query = query.filter(db.extract('month', Pengeluaran.tanggal) == bulan)
    if tahun:
        query = query.filter(db.extract('year', Pengeluaran.tanggal) == tahun)
    
    pengeluaran = query.order_by(Pengeluaran.tanggal.desc()).all()
    
    # Hitung total
    total = sum(p.jumlah for p in pengeluaran) if pengeluaran else 0
    
    return render_template('daftar_pengeluaran.html', 
                         pengeluaran=pengeluaran,
                         total=total,
                         bulan=bulan,
                         tahun=tahun)

@app.route('/pengeluaran/hapus/<int:id>', methods=['POST'])
def hapus_pengeluaran(id):
    pengeluaran = Pengeluaran.query.get_or_404(id)
    
    try:
        db.session.delete(pengeluaran)
        db.session.commit()
        flash('Data pengeluaran berhasil dihapus', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Gagal menghapus: {str(e)}', 'danger')
    
    return redirect(url_for('daftar_pengeluaran'))

@app.route('/pengeluaran/edit/<int:id>', methods=['GET', 'POST'])
def edit_pengeluaran(id):
    pengeluaran = Pengeluaran.query.get_or_404(id)
    
    if request.method == 'POST':
        pengeluaran.penerima = request.form['penerima'].strip()
        pengeluaran.keterangan = request.form['keterangan'].strip()
        pengeluaran.tanggal = datetime.strptime(request.form['tanggal'], '%Y-%m-%d').date()
        pengeluaran.jumlah = int(request.form['jumlah'])
        
        try:
            db.session.commit()
            flash('Data pengeluaran berhasil diperbarui', 'success')
            return redirect(url_for('daftar_pengeluaran'))  # Biasanya redirect ke daftar, bukan tambah
        except Exception as e:
            db.session.rollback()
            flash(f'Terjadi error: {str(e)}', 'danger')
    
    return render_template('form_pengeluaran.html', pengeluaran=pengeluaran)



# Fungsi helper ambil filter tanggal dari request args
def get_filter_dates():
    periode = request.args.get('periode', 'bulan-ini')
    today = date.today()

    if periode == 'hari-ini':
        return today, today
    elif periode == 'minggu-ini':
        awal = today - timedelta(days=today.weekday())
        akhir = awal + timedelta(days=6)
        return awal, akhir
    elif periode == 'tahun-ini':
        return date(today.year, 1, 1), date(today.year, 12, 31)
    elif periode == 'custom':
        try:
            tgl_awal = datetime.strptime(request.args.get('tgl_awal'), '%Y-%m-%d').date()
            tgl_akhir = datetime.strptime(request.args.get('tgl_akhir'), '%Y-%m-%d').date()
            return tgl_awal, tgl_akhir
        except:
            return date(today.year, today.month, 1), today
    else:  # Default: bulan-ini
        awal = date(today.year, today.month, 1)
        akhir = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        return awal, akhir



@app.route('/import_warga', methods=['POST'])
def import_warga():
    file = request.files.get('file')
    if not file:
        flash('File tidak ditemukan.', 'danger')
        return redirect(url_for('data_warga'))

    if not file.filename.endswith('.csv'):
        flash('Format file harus .csv', 'danger')
        return redirect(url_for('data_warga'))

    file_data = file.read().decode('utf-8')
    csv_reader = csv.reader(file_data.splitlines())

    baris_sukses = 0
    baris_duplikat = 0
    baris_skip = 0

    for idx, row in enumerate(csv_reader):
        if len(row) != 7:
            baris_skip += 1
            continue

        nama, nik, alamat, telepon, status, username, plain_pw = [x.strip() for x in row]

        if not nama or not username or not plain_pw:
            baris_skip += 1
            continue

        # Cek duplikat username
        if Warga.query.filter_by(username=username).first():
            baris_duplikat += 1
            continue

        # Hash password
        hashed_pw = bcrypt.generate_password_hash(plain_pw).decode('utf-8')

        warga_baru = Warga(
            nama=nama,
            nik=nik or None,
            alamat=alamat,
            telepon=telepon,
            status=status.lower(),
            username=username,
            password=hashed_pw,
            role='user'
        )
        db.session.add(warga_baru)
        baris_sukses += 1

    db.session.commit()
    flash(f'{baris_sukses} warga berhasil diimpor. {baris_duplikat} username sudah digunakan. {baris_skip} baris dilewati.', 'success')
    return redirect(url_for('data_warga'))



    db.session.commit()
    flash('Data warga berhasil diimpor.', 'success')
    return redirect(url_for('data_warga'))


class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "Laporan Kas RT", ln=True, align="C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Halaman {self.page_no()}", align="C")

    def table_section(self, title, headers, rows):
        self.set_font("Arial", "B", 11)
        self.cell(0, 8, title, ln=True)
        self.set_font("Arial", "B", 10)
        for h in headers:
            self.cell(40, 8, h, border=1)
        self.ln()
        self.set_font("Arial", "", 10)
        for row in rows:
            for item in row:
                self.cell(40, 8, str(item), border=1)
            self.ln()
        self.ln(5)

@app.route('/export_laporan/<format>')
def export_laporan(format):
    def get_filter_dates():
        periode = request.args.get('periode', 'bulan-ini')
        today = date.today()
        if periode == 'hari-ini':
            return today, today
        elif periode == 'minggu-ini':
            awal = today - timedelta(days=today.weekday())
            return awal, awal + timedelta(days=6)
        elif periode == 'tahun-ini':
            return date(today.year, 1, 1), date(today.year, 12, 31)
        elif periode == 'custom':
            try:
                tgl_awal = datetime.strptime(request.args.get('tgl_awal'), '%Y-%m-%d').date()
                tgl_akhir = datetime.strptime(request.args.get('tgl_akhir'), '%Y-%m-%d').date()
                return tgl_awal, tgl_akhir
            except:
                return date(today.year, today.month, 1), today
        else:
            awal = date(today.year, today.month, 1)
            akhir = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
            return awal, akhir

    tgl_awal, tgl_akhir = get_filter_dates()
    zona_wib = timezone('Asia/Jakarta')

    pemasukan = (
        db.session.query(Iuran)
        .join(Warga)
        .filter(Iuran.tanggal.between(tgl_awal, tgl_akhir))
        .order_by(Iuran.tanggal.asc())
        .all()
    )

    pengeluaran = (
        db.session.query(Pengeluaran)
        .filter(Pengeluaran.tanggal.between(tgl_awal, tgl_akhir))
        .order_by(Pengeluaran.tanggal.asc())
        .all()
    )

    headers1 = ['No', 'Tanggal', 'Nama Warga', 'Jumlah', 'Keterangan']
    headers2 = ['No', 'Tanggal', 'Keterangan', 'Jumlah', 'Petugas']

    if format == 'excel':
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # Sheet Pemasukan
        ws1 = workbook.add_worksheet('Pemasukan')
        for col, h in enumerate(headers1):
            ws1.write(0, col, h)

        for idx, item in enumerate(pemasukan, 1):
            tanggal = item.tanggal.astimezone(zona_wib).strftime('%d/%m/%Y %H:%M')
            ws1.write(idx, 0, idx)
            ws1.write(idx, 1, tanggal)
            ws1.write(idx, 2, item.warga.nama)
            ws1.write(idx, 3, item.jumlah)
            ws1.write(idx, 4, 'Iuran')

        # Sheet Pengeluaran
        ws2 = workbook.add_worksheet('Pengeluaran')
        for col, h in enumerate(headers2):
            ws2.write(0, col, h)

        for idx, item in enumerate(pengeluaran, 1):
            tanggal = item.tanggal.astimezone(zona_wib).strftime('%d/%m/%Y %H:%M')
            ws2.write(idx, 0, idx)
            ws2.write(idx, 1, tanggal)
            ws2.write(idx, 2, item.keterangan)
            ws2.write(idx, 3, item.jumlah)
            ws2.write(idx, 4, item.petugas or '-')

        workbook.close()
        output.seek(0)
        filename = f"laporan_kas_{tgl_awal.strftime('%Y%m%d')}_{tgl_akhir.strftime('%Y%m%d')}.xlsx"
        return send_file(output, download_name=filename, as_attachment=True)

    elif format == 'pdf':
        pdf = PDF()
        pdf.add_page()

        pemasukan_rows = [[
            idx,
            i.tanggal.astimezone(zona_wib).strftime('%d/%m/%Y %H:%M'),
            i.warga.nama,
            f"Rp {i.jumlah:,}",
            "Iuran"
        ] for idx, i in enumerate(pemasukan, 1)]

        pengeluaran_rows = [[
            idx,
            p.tanggal.astimezone(zona_wib).strftime('%d/%m/%Y %H:%M'),
            p.keterangan,
            f"Rp {p.jumlah:,}",
            p.petugas or "-"
        ] for idx, p in enumerate(pengeluaran, 1)]

        pdf.table_section("Pemasukan", headers1, pemasukan_rows)
        pdf.table_section("Pengeluaran", headers2, pengeluaran_rows)

        pdf_bytes = BytesIO()
        pdf_output = pdf.output(dest='S').encode('latin1')  # ✅ Fix here
        pdf_bytes.write(pdf_output)
        pdf_bytes.seek(0)

        filename = f"laporan_kas_{tgl_awal.strftime('%Y%m%d')}_{tgl_akhir.strftime('%Y%m%d')}.pdf"
        return send_file(pdf_bytes, download_name=filename, as_attachment=True)

    return "Format tidak didukung", 400



@app.route('/download_template')
def download_template():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['nama', 'nik', 'alamat', 'telepon', 'status', 'username', 'password'])
    writer.writerow(['Contoh Nama', '1234567890123456', 'Jl. Contoh Alamat', '08123456789', 'aktif', 'contohuser', '123456'])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='template_warga.csv'
    )

@app.route('/manajemen_user')
def manajemen_user():
    if session.get('role') != 'admin':
        flash("Akses ditolak", "danger")
        return redirect(url_for('dashboard'))

    users = User.query.all()
    return render_template('manajemen_user.html', users=users)

@app.route('/user/tambah', methods=['GET', 'POST'])
def tambah_user():
    if session.get('role') != 'admin':
        flash("Akses ditolak", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        role = request.form['role']

        # ✅ Hash password!
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

        if User.query.filter_by(username=username).first():
            flash('Username sudah digunakan', 'danger')
            return redirect(url_for('tambah_user'))

        user = User(username=username, password=hashed_pw, role=role)
        db.session.add(user)
        db.session.commit()
        flash('User berhasil ditambahkan', 'success')
        return redirect(url_for('manajemen_user'))

    return render_template('form_user.html')


@app.route('/user/edit/<int:id>', methods=['GET', 'POST'])
def edit_user(id):
    if session.get('role') != 'admin':
        flash("Akses ditolak", "danger")
        return redirect(url_for('dashboard'))

    user = User.query.get_or_404(id)

    if request.method == 'POST':
        user.username = request.form['username'].strip()
        user.role = request.form['role']

        new_password = request.form['password'].strip()
        if new_password:
            # ✅ Hash password baru
            user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')

        db.session.commit()
        flash('User berhasil diperbarui', 'success')
        return redirect(url_for('manajemen_user'))

    return render_template('form_user.html', user=user)


@app.route('/user/hapus/<int:id>', methods=['POST'])
def hapus_user(id):
    if session.get('role') != 'admin':
        flash("Akses ditolak", "danger")
        return redirect(url_for('dashboard'))

    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    flash('User berhasil dihapus', 'success')
    return redirect(url_for('manajemen_user'))

@app.route('/iuran_saya')
def iuran_saya():
    if 'username' not in session or session.get('role') != 'user':
        flash("Akses ditolak", "danger")
        return redirect(url_for('login'))

    warga = Warga.query.filter_by(username=session['username']).first()
    if not warga:
        flash("Data warga tidak ditemukan", "danger")
        return redirect(url_for('dashboard'))

    iurans = Iuran.query.filter_by(warga_id=warga.id).order_by(Iuran.tanggal.desc()).all()

    total = sum(i.jumlah for i in iurans)

    return render_template('iuran_saya.html', iurans=iurans, total=total)


# =====================
# INISIALISASI DB
# =====================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        insert_default_users()
    app.run(host='0.0.0.0', port=5001, debug=True)

