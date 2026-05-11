IPKB PWA + WhatsApp Otomatis
============================

1. Install dependency:
   pip install -r requirements.txt

2. Jalankan database_fix.sql di phpMyAdmin.

3. Jalankan aplikasi:
   python app.py

4. PWA install di HP:
   - Buka aplikasi dari Chrome Android.
   - Login.
   - Tap menu titik tiga browser.
   - Pilih "Tambahkan ke layar utama" / "Install app".
   - Buka dari ikon IPKB.
   - Masuk menu Rencana Kerja lalu klik "Aktifkan Notifikasi".

5. WhatsApp otomatis via Fonnte:
   - Daftar akun Fonnte dan ambil token.
   - Windows PowerShell/CMD sebelum menjalankan Flask:
     set FONNTE_TOKEN=token_kamu
     set WA_AUTO_SEND=1
     python app.py

Catatan penting:
- Notifikasi PWA lokal butuh izin notifikasi dari browser/HP.
- WA otomatis berjalan selama server Flask menyala.
- Untuk notifikasi yang benar-benar tetap aktif 24 jam, aplikasi Flask harus dijalankan di server/VPS/laptop yang tidak dimatikan.
- Jika hanya di XAMPP/laptop lokal dan laptop mati, WA otomatis tidak bisa terkirim.
