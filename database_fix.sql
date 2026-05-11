-- DATABASE FIX / UPDATE IPKB
-- Jalankan di phpMyAdmin database `ipkb_app`.

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;

-- Hilangkan UNIQUE pada pembayaran.iuran_id supaya 1 iuran bisa dibayar bertahap.
ALTER TABLE pembayaran DROP FOREIGN KEY IF EXISTS fk_iuran;
ALTER TABLE pembayaran DROP FOREIGN KEY IF EXISTS pembayaran_ibfk_1;
ALTER TABLE pembayaran DROP INDEX IF EXISTS iuran_id;

ALTER TABLE pembayaran
  MODIFY id INT(11) NOT NULL AUTO_INCREMENT;

CREATE INDEX IF NOT EXISTS idx_pembayaran_iuran_id ON pembayaran(iuran_id);

ALTER TABLE pembayaran
  ADD CONSTRAINT fk_pembayaran_iuran
  FOREIGN KEY (iuran_id) REFERENCES iuran(id)
  ON DELETE CASCADE ON UPDATE CASCADE;

-- Tabel SKP
CREATE TABLE IF NOT EXISTS skp (
  id INT(11) NOT NULL AUTO_INCREMENT,
  user_id INT(11) NOT NULL,
  tahun INT(11) NOT NULL,
  uraian TEXT NOT NULL,
  target VARCHAR(255) DEFAULT NULL,
  capaian VARCHAR(255) DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_skp_user_id (user_id),
  CONSTRAINT fk_skp_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Tabel Rencana Kerja / Renja
CREATE TABLE IF NOT EXISTS rencana_kerja (
  id INT(11) NOT NULL AUTO_INCREMENT,
  user_id INT(11) NOT NULL,
  tanggal DATE NOT NULL,
  kegiatan VARCHAR(255) NOT NULL,
  keterangan TEXT DEFAULT NULL,
  status ENUM('Rencana','Proses','Selesai') NOT NULL DEFAULT 'Rencana',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_renja_user_id (user_id),
  INDEX idx_renja_status (status),
  CONSTRAINT fk_renja_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Tabel Pengeluaran untuk laporan keuangan
CREATE TABLE IF NOT EXISTS pengeluaran (
  id INT(11) NOT NULL AUTO_INCREMENT,
  tanggal DATE NOT NULL,
  uraian VARCHAR(255) NOT NULL,
  jumlah INT(11) NOT NULL DEFAULT 0,
  keterangan TEXT DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_pengeluaran_tanggal (tanggal)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

COMMIT;

-- Update tambahan: nomor HP/WhatsApp dan jam kegiatan
ALTER TABLE users ADD COLUMN IF NOT EXISTS no_hp VARCHAR(30) NULL AFTER foto;
ALTER TABLE rencana_kerja ADD COLUMN IF NOT EXISTS jam TIME NULL AFTER tanggal;
ALTER TABLE rencana_kerja ADD COLUMN IF NOT EXISTS wa_diingatkan TINYINT(1) NOT NULL DEFAULT 0 AFTER status;
CREATE INDEX IF NOT EXISTS idx_renja_tanggal_jam ON rencana_kerja(tanggal, jam);

-- Pastikan tabel Pengeluaran tersedia untuk menu Pengeluaran
CREATE TABLE IF NOT EXISTS pengeluaran (
  id INT(11) NOT NULL AUTO_INCREMENT,
  tanggal DATE NOT NULL,
  uraian VARCHAR(255) NOT NULL,
  jumlah INT(11) NOT NULL DEFAULT 0,
  keterangan TEXT DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_pengeluaran_tanggal (tanggal)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ================= UPDATE PWA + WA + RENJA JAM SELESAI =================
ALTER TABLE users ADD COLUMN IF NOT EXISTS no_hp VARCHAR(30) NULL AFTER foto;
ALTER TABLE users ADD UNIQUE KEY IF NOT EXISTS uniq_users_nip (nip);
ALTER TABLE rencana_kerja ADD COLUMN IF NOT EXISTS jam_selesai TIME NULL AFTER jam;
ALTER TABLE rencana_kerja ADD COLUMN IF NOT EXISTS wa_diingatkan TINYINT(1) NOT NULL DEFAULT 0 AFTER status;
