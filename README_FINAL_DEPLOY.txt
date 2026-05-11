VERSI FINAL SIAP DEPLOY - IPKB

Perubahan final:
1. Header mobile dirapikan, tombol menu dipindahkan dekat logo.
2. Notifikasi tagihan dihitung dari Januari sampai bulan berjalan.
3. Laporan PDF bisa filter semua bulan / per bulan / dari bulan sampai bulan.
4. Pagination iuran tetap urut dan bisa klik ke halaman berikutnya.
5. Grafik iuran menjadi line chart.
6. Rencana kerja:
   - tampilan awal otomatis kegiatan hari ini
   - ada tombol aksi "selesaikan pekerjaan"
   - rekap kegiatan sama dihitung otomatis
   - rekap per bulan tampil untuk role anggota/user
7. Dashboard anggota/user:
   - ringkasan iuran pribadi
   - pemasukan keseluruhan
   - pengeluaran keseluruhan
   - sisa saldo keseluruhan

Checklist deploy:
- Install dependency: pip install -r requirements.txt
- Pastikan database MySQL aktif.
- Import database awal bila perlu.
- Pastikan file .env / konfigurasi DB sesuai server.
- Jalankan: python app.py

Catatan:
- Jika tabel pengeluaran belum ada, aplikasi akan mencoba membuat otomatis.
- Jika data lama sudah ada, tidak perlu import ulang semua file SQL kecuali pada server baru.
