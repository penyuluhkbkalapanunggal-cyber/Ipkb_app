FIX ALARM KEGIATAN

Yang diperbaiki:
- Ditambahkan file suara alarm: static/audio/alarm.wav
- Header ada tombol icon volume untuk mengaktifkan alarm.
- Halaman Rencana Kerja ada tombol Aktifkan Alarm.
- Cek notifikasi kegiatan dipercepat menjadi setiap 15 detik.
- Jika ada kegiatan yang waktunya masuk, muncul SweetAlert dan suara alarm berbunyi.

Penting:
- Browser HP tidak mengizinkan suara otomatis sebelum user klik tombol.
- Jadi user wajib klik 'Aktifkan Alarm' sekali setelah login.
- Suara alarm hanya bisa dijamin saat aplikasi/PWA masih terbuka.
- Jika aplikasi ditutup total, browser biasanya hanya mengizinkan push notification, bukan suara alarm panjang.
- Untuk alarm tetap jalan walau aplikasi ditutup, solusi paling aman adalah WhatsApp otomatis dari server.
