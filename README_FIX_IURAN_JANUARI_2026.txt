FIX IURAN JANUARI 2026 BELUM KEBACA

Penyebab:
Halaman belum bayar hanya bisa membaca baris yang sudah ada di tabel iuran.
Kalau iuran Januari/Februari/dst belum pernah dibuat untuk anggota, maka data belum bayar tidak muncul.

Perbaikan:
1. Aplikasi sekarang mengambil anggota dari tabel users kolom id, nama, nip.
2. Saat membuka dashboard/iuran/belum bayar/notifikasi, aplikasi otomatis mengecek iuran dari Januari 2026 sampai bulan berjalan.
3. Jika ada bulan yang belum punya baris iuran, aplikasi membuat otomatis dengan jumlah default dari iuran terakhir.
4. Halaman Belum Bayar, Notifikasi, dan WA memakai data iuran dari Januari 2026 sampai bulan berjalan.

Catatan:
- Kalau jumlah default 0, isi nominal iuran di data iuran pertama/terakhir, lalu data berikutnya akan mengikuti nominal itu.
- Tidak perlu import ulang database.
