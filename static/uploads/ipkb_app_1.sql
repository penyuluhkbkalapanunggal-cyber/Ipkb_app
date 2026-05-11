-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Waktu pembuatan: 26 Apr 2026 pada 17.55
-- Versi server: 10.4.32-MariaDB
-- Versi PHP: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `ipkb_app`
--

-- --------------------------------------------------------

--
-- Struktur dari tabel `iuran`
--

CREATE TABLE `iuran` (
  `id` int(11) NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  `bulan` varchar(20) DEFAULT NULL,
  `tahun` int(11) DEFAULT NULL,
  `jumlah` int(11) DEFAULT NULL,
  `status` varchar(20) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data untuk tabel `iuran`
--

INSERT INTO `iuran` (`id`, `user_id`, `bulan`, `tahun`, `jumlah`, `status`, `created_at`) VALUES
(1, 9, '3', 2026, 60000, 'lunas', '2026-04-23 08:24:42');

-- --------------------------------------------------------

--
-- Struktur dari tabel `users`
--

CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `nip` varchar(30) DEFAULT NULL,
  `password` varchar(255) DEFAULT NULL,
  `role` enum('admin','user') DEFAULT NULL,
  `nama` varchar(100) DEFAULT NULL,
  `foto` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data untuk tabel `users`
--

INSERT INTO `users` (`id`, `nip`, `password`, `role`, `nama`, `foto`) VALUES
(4, '197708162024211002', 'scrypt:32768:8:1$ZWd7UyO9F71muxAe$0b4c39d029ec88bad1b4bd13899ada39aff7e749243634b3e2a4927f937113032c9b7ece5d04d2198adc82362b0060ff9b042ae50ad5622d7c36da7ed1890995', 'admin', 'Helmi Ramdan', '0_WhatsApp_Image_2026-04-20_at_14.01.09.jpeg'),
(8, '197708162024211003', 'scrypt:32768:8:1$NSOoRhrcLnwDFOtn$033ac082225702fcc88cb6e463755aac1c58740746527581973ed7bc3e50140257afbe196440ed846585804266ba9fd39a354a34fa2607b787bbd1f84e5238a6', 'admin', 'MAHLUDIN', '0_WhatsApp_Image_2026-04-20_at_14.01.09.jpeg'),
(9, '197708162024211005', 'scrypt:32768:8:1$NM1W6YzufoUFDOi0$cd5dca763fdae51b00a512d9603c35fbed1b1afadccf55495688b96b3ea3e6662470668448da5201819030c905048c7dbd93e9e9abafc9e626f576e4b2d43ceb', 'admin', 'RUDIANSAH', '0_tamsya.jpg'),
(18, '1977081620242111526', 'scrypt:32768:8:1$FTZWEK67QLBBd6a1$d63258417b343a6ca3c03402d214e558d3cfb084c61e06d38007b7c8a4f42838a7bdf58532dad87f9265c460cab636a7ddef55c079a26cf89b9fcef953dbaef4', '', 'budi', '0_bkkbn.jpg'),
(19, '197708162024211', 'scrypt:32768:8:1$jnmj9L7BdYRQV3Xz$d7ef7eed7f60fb63bdec866708ce76c6700df25515b68abe467507002db6620baffad20fea6a79e3282a9841fed003ec56f142cd622f340081136f0e35876329', '', '197708162024211', '0_download-removebg-preview_3.png');

--
-- Indexes for dumped tables
--

--
-- Indeks untuk tabel `iuran`
--
ALTER TABLE `iuran`
  ADD PRIMARY KEY (`id`);

--
-- Indeks untuk tabel `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `nip` (`nip`);

--
-- AUTO_INCREMENT untuk tabel yang dibuang
--

--
-- AUTO_INCREMENT untuk tabel `iuran`
--
ALTER TABLE `iuran`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT untuk tabel `users`
--
ALTER TABLE `users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=20;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
