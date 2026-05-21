# 🧠 Blueprint Final: Smart Diagnosis Logic (V3)

Dokumen ini adalah **rangkuman konsep final** yang telah disepakati. Mencakup seluruh workflow logika, struktur tabel Spreadsheet, dan format output Diagnosis History.

---

## 📊 BAGIAN 1: Struktur Tabel `Diagnosis_Rules`

Enam kolom pertama (A-F) adalah struktur LAMA yang tidak diubah. Kolom G-J adalah **ekstensi opsional** yang hanya diisi jika Kolom F (`Logic`) ada nilainya.

```
A (Parameter) | B (Keyword) | C (Tab) | D (Op) | E (Nilai) | F (Logic) | G (Keyword 2) | H (Tab 2) | I (Op 2) | J (Nilai 2) | K (Logic 2) | L (Keyword 3) | ...
```

| Kolom | Nama | Isi | Tipe Input |
| :--- | :--- | :--- | :--- |
| A | Parameter | Nama gejala (sinkron dengan Matrix) | Teks bebas |
| B | Keyword | Nama kolom sensor | Dropdown |
| C | Tab Source | Nama sheet sumber data | Dropdown |
| D | Operator | `<, >, =, <=, >=` | Dropdown |
| E | Nilai | Angka batas | Teks bebas |
| **F** | **Logic** | **`AND`, `OR`, `TIME`, atau kosong** | **Dropdown** |
| G | Keyword 2 | Nama kolom sensor ke-2 | Dropdown (disaring otomatis) |
| H | Tab 2 | Nama sheet ke-2 | Dropdown |
| I | Op 2 | Operator ke-2 | Dropdown |
| J | Nilai 2 | Batas ke-2 (atau Jam jika TIME) | Teks bebas |
| **K** | **Logic 2** | **Rantai berikutnya (opsional)** | **Dropdown** |
| L-O | Syarat 3 | Seperti G-J | ... |

---

## ⚙️ BAGIAN 2: Katalog Logic dan Cara Kerjanya

### `AND` — Kedua Syarat Wajib Terpenuhi
**Kapan dipakai:** Gejala hanya valid jika DUA sensor bersamaan bermasalah.

| Rules (A-E) | F (Logic) | Rules 2 (G-J) |
| :--- | :--- | :--- |
| `Ammonia > 1.5` | **`AND`** | `pH > 8.0` |

- ✅ NH3:2.0, pH:8.5 → `NH3:2.0 (pH:8.5) → PASS`
- ❌ NH3:2.0, pH:7.0 → `NH3:2.0 (pH:7.0) → FAIL` *(pH gagal, AND runtuh)*

---

### `OR` — Cukup Salah Satu Syarat Terpenuhi
**Kapan dipakai:** Gejala terdeteksi dari salah satu dari dua indikator berbeda.

| Rules (A-E) | F (Logic) | Rules 2 (G-J) |
| :--- | :--- | :--- |
| `DO < 4.0` | **`OR`** | `AC Status = OFF` |

- ✅ DO:6.0, AC:OFF → `DO:6.0 (AC:OFF) → PASS` *(DO aman, tapi AC mati cukup jadi bukti)*
- ✅ DO:3.5, AC:ON → `DO:3.5 (AC:ON) → PASS` *(AC-nya hidup, tapi DO yang membuktikan)*
- ❌ DO:6.0, AC:ON → `DO:6.0 (AC:ON) → FAIL` *(Keduanya aman)*

---

### `TIME` — Syarat Waktu dari Timestamp Data
**Kapan dipakai:** Gejala hanya relevan pada rentang jam tertentu. Waktu diambil dari **Kolom Timestamp di sheet sumber data**, bukan dari jam server.

| Rules (A-E) | F (Logic) | G (Keyword 2) | H (Tab 2) | I (Op 2) | J (Nilai 2) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `DO < 4.5` | **`TIME`** | `Timestamp` | `WATER QUALITY` | `>=` | `08:00` |

> **Format Timestamp Didukung:** `06/02/2026 7:08:28`, `2026-01-29 18:47:40`, dll. Bot otomatis mengekstrak hanya angka Jam-nya melalui `new Date()`.

- ✅ DO:4.0, Timestamp:14:05 → `DO:4.0 (@14:05) → PASS` *(Siang, valid crash)*
- ❌ DO:4.0, Timestamp:04:00 → `DO:4.0 (@04:00) → FAIL` *(Subuh, maklum dilewati)*

---

## 🔗 BAGIAN 3: Infinite Logic Chaining (Rantai Berlapis)

Setiap **Kolom Logic** (F, K, dst.) dapat diisi **`AND`, `OR`, atau `TIME`** secara bebas dan bertumpuk. Evaluasi berjalan melompat kiri ke kanan seperti gerbong kereta.

**Contoh Tumpukan 3 Syarat:**

| A-E (Utama) | F (Logic 1) | G-J (Syarat 2) | K (Logic 2) | L-O (Syarat 3) |
| :--- | :--- | :--- | :--- | :--- |
| `DO < 4.0` | **`AND`** | `pH < 7.0` | **`TIME`** | `Timestamp >= 08:00` |

- Skenario PASS (Siang, DO+pH rusak): `DO:3.0 (pH:6.5, @14:00) → PASS` 🟢
- Skenario FAIL (Subuh, meski DO+pH rusak): `DO:3.0 (pH:6.5, @04:00) → FAIL` 🔴

> **Kunci:** Jika satu gerbong syarat gagal dan ikatannya adalah `AND`, seluruh rantai langsung dibatalkan tanpa mengeksekusi gerbong berikutnya.

---

## 📋 BAGIAN 4: Format Output di `Diagnosis History`

Setiap kali diagnosa berjalan, hanya **1 baris baru ditambahkan**. Tidak ada duplikat selama mekanisme **Anti-Duplikat Time Window** (cek 5 menit terakhir) aktif.

### Format Nilai di Setiap Sel Parameter:

| Jenis Logic | Format Nilai | Contoh Nyata |
| :--- | :--- | :--- |
| *(Tanpa Logic)* | `[KW]:[Nilai] → STATUS` | `DO:2.5 → PASS` |
| `AND` | `[KW1]:[Nilai1] ([KW2]:[Nilai2]) → STATUS` | `NH3:2.0 (pH:8.5) → PASS` |
| `OR` | `[KW1]:[Nilai1] ([KW2]:[Nilai2]) → STATUS` | `DO:6.0 (AC:OFF) → PASS` |
| `TIME` | `[KW1]:[Nilai1] (@[Jam]) → STATUS` | `DO:3.5 (@14:05) → PASS` |
| **Bertumpuk** | `[KW1]:[Nilai1] ([KW2]:[Nilai2], @[Jam]) → STATUS` | `DO:3.0 (pH:6.5, @14:00) → PASS` |

### Contoh Baris `Diagnosis History` secara Lengkap:

| Timestamp | Diagnosa Utama | Prob | Kemungkinan Lain | Low DO | Blower Off | Toxic NH3 | Crash DO Siang |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 13/03/2026 14:05 | Plankton Crash | 87% | D69, D22... | `DO:3.0 → PASS` 🟢 | `DO:3.0 (AC:ON) → FAIL` 🔴 | `NH3:2.0 (pH:7.5) → FAIL` 🔴 | `DO:3.0 (@14:05) → PASS` 🟢 |

---

## ✅ BAGIAN 5: Ringkasan Apa yang Berubah dan Apa yang Tidak

| Aspek | Status | Keterangan |
| :--- | :--- | :--- |
| Kolom A-E di `Diagnosis_Rules` | **TIDAK BERUBAH** | Struktur inti tetap utuh |
| Kolom F (`Logic`) | **DIAKTIFKAN** | Sebelumnya ada tapi kosong, sekarang fungsional |
| Kolom G-O | **BARU (Opsional)** | Hanya muncul jika Logic diisi |
| Format `Diagnosis History` | **DIPERKAYA** | Nilai sekarang berlabel nama sensor dan konteks logika |
| Struktur baris di `Diagnosis History` | **TIDAK BERUBAH** | Tetap 1 baris per sesi diagnosa |
| Akurasi Diagnosa | **SANGAT MENINGKAT** | Tidak ada false alarm dari logika tunggal |
