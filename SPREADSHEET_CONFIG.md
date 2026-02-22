# 📘 SPREADSHEET CONFIGURATION (ULTIMATE v4)

Berikut adalah dokumentasi resmi mengenai **13 Tab (Sheet) yang Mutlak Aktif** digunakan dalam sistem Bot IoT Bioflok saat ini, beserta detail rincian kolom header dan fungsinya masing-masing.

---

## 🧠 1. INTI AI & LOGIKA (KOKPIT UTAMA)

### 1a. `Matrix Diagnosis`
*Jantung dari klasifikasi Bayesian AI. Berisi probabilitas frekuensi dari berbagai penyakit (simtom) dan rentetan gejalanya.*
*   **Headers:** `Index`, `Frequency`, `Diagnosis`, `Low DO` ... `High Feed`, `Power Outage`, `High Biomass`, `Cost ($)`
*   **Fungsi Utama:** Menyimpan daftar penyakit, bobot awal (Frekuensi/Prior), dan rentang pola syarat kondisi (PASS/FAIL/?) pembentuk penyakit.

### 1b. `Diagnosis_Rules`
*Kamus penamaan variabel dan penetapan *threshold* (batas) logika angka menjadi teks klasifikasi biner (PASS/FAIL).*
*   **Headers:** `Parameter`, `Keyword`, `Tab Source`, `Operator`, `Threshold 1`, `Threshold 2`
*   **Fungsi Utama:** Menerjemahkan data mentah angka (Misal: DO "4.2") di-*mapping* agar disebut DO TINGGI atau RENDAH. Algoritmanya digunakan oleh Backend untuk validasi *Matrix Diagnosis*.

### 1c. `AI Event Log Analysis`
*Rak penyimpanan rekapitulasi histori mesin dari setiap vonis diagnosa.*
*   **Headers:** `Timestamp`, `Diagnosis`, `Trigger Data`, `Note`
*   **Fungsi Utama:** Pencatatan *Output* murni kesimpulan Diagnosa AI setiap ditrigger (termasuk list parameter "Miss"/meleset). Tidak ada data input di sini.

### 1d. `THRESHOLD`
*Batas ambang parameter standar limit fisik IoT (File legacy).*
*   **Headers:** `Parameter`, `Min Value`, `Max Value`, `Unit`, `Alert Low`, `Alert High`
*   **Fungsi Utama:** Memberikan rentang parameter bahaya yang bersifat konvensional (Untuk memicu trigger Early Warning non-Bayesian).

---

## 📡 2. IOT & TELEMETRI SENSOR

### 2a. `Water Quality`
*Log pencatatan masuk dominan dari sensor air IoT ESP32 (ataupun lewat manual Web/WA).*
*   **Headers:** `Timestamp`, `Type`, `Device`, `DO`, `DO ADC`, `pH`, `pH ADC`, `TDS`, `TDS ADC`, `Temp`, `Temp ADC`, `DO Photo`, `pH Photo`, `TDS Photo`, `Temp Photo`, `Note`
*   **Fungsi Utama:** Penentu kualitas nafas lingkungan, dipakai konstan oleh AI untuk parameter DO, pH, Temperature, & TDS.

### 2b. `Farm Control`
*Log pencatatan kendali jarak jauh aktivasi infrastruktur tambak.*
*   **Headers:** `Timestamp`, `Type`, `Device`, `AC Status`, `DC Status`, `Pump Relay`, `Aerator Relay`, `Note`
*   **Fungsi Utama:** Melacak rekam kelistrikan dan IoT, membantu menjawab pertanyaan *"Kenapa DO Drop?"* (Oh.. karena Pompa Mati tercatat disini).

### 2c. `Machine - Inverter Data`
*Catatan khusus telemetri tegangan dan frekuensi putaran mesin pakan otomatis (Auto-feeder).*
*   **Headers:** `Timestamp`, `Reporter ID`, `Inverter Feed (Hz)`, `Inverter Feed Photo`, `Inverter Rest (Hz)`, `Inverter Rest Photo`, `Note`
*   **Fungsi Utama:** Data pembantu pergerakan arus & inverter untuk analisa kerusakan mekanis.

---

## 🐟 3. MANAJEMEN BUDIDAYA (BIOMASSA)

### 3a. `Feed Tracker`
*Pencatatan konsolidasi riwayat total pemberian suplai pakan harian.*
*   **Headers:** `Date`, `Day`, `Pangan (kg)`, `Harga/kg`, `Biaya Harian`, `Photo Link`, `Reporter`, `Note`
*   **Fungsi Utama:** Log harian suplai nutrisi. Dipakai sebagai penentu kalori harian yang masuk ke badan air.

### 3b. `Target Pangan`
*Tabel Kurva Referensi Ideal jumlah target pemberian makanan ikan (SOP).*
*   **Headers:** `Minggu`, `Bobot Target (g)`, `Feed Rate (%)`, `Pangan Target (kg)`, `FCR Standard`
*   **Fungsi Utama:** AI akan membandingkan `Feed Tracker` riil VS `Target Pangan` SOP untuk menilai/menebak indikasi kelaparan, *Underfeeding*, ataupun sisa *Overfeeding*.

### 3c. `Sampling`
*Gudang rekapitulasi pencatatan angkat jaring (pengukuran bobot pertumbuhan).*
*   **Headers:** `Timestamp`, `Reporter ID`, `Avg Weight (g)`, `Avg Length (cm)`, `Fish 1 Photo`, `Fish 1 Weight`, `Fish 1 Length` *(...sampai 30 ekor)*
*   **Fungsi Utama:** Alat ukur hasil evaluasi, mencari performa bobot aktual dan ABW (Average Body Weight) rata-rata.

### 3d. `Bio - Dead Fish`
*Pencatatan mutlak tabel angka kematian (Mortalitas harian).*
*   **Headers:** `Timestamp`, `Reporter ID`, `Count`, `Photo Link`, `Note`
*   **Fungsi Utama:** Mempengaruhi parameter SR (Survival Rate). Sinyal utama bila ada serangan penyakit massal.

### 3e. `FCR Analysis`
*Analisa skor Rapor Konversi Pakan (Food Conversion Ratios).*
*   **Headers:** `Minggu`, `Kenaikan Bobot (kg)`, `Pakan Mingguan (kg)`, `FCR Real`, `FCR Target`, `Status`
*   **Fungsi Utama:** Indikator tingkat efisiensi bisnis tambak (Apakah pangan terserap menjadi bobot daging atau hanya jadi limbah racun).

---

## 🎬 4. MULTIMEDIA

### 4a. `Media - General Video`
*Penyimpanan file pelampiran aset visual sembarang di ekosistem tambak.*
*   **Headers:** `Timestamp`, `Reporter ID`, `Video Link`, `Note`
*   **Fungsi Utama:** Database pemetaan riwayat evidensi foto/video kondisi visual kolam (ex: kondisi mati lampu, bangkai mencurigakan, dsb).

---

## 💻 5. GOOGLE APPS SCRIPT CODE (BACKUP ARCHITECTURE)
Kumpulan kode *Javascript Virtual* yang ditanamkan menempel pada UI Database Google Sheets untuk kendali luar (Thirdparty automation).

### A. `Rule2Matrix.gs`
Pusat kontrol navigasi UI (*Frontend*) dan pengurus menu Dropdown. Fungsi unggulan terbarunya adalah menyediakan **UI HTML Modal Database Manager** agar *rules* & *matrix* tetap selalu sinkron sejajar baris demi baris secara otomatis.
### B. `server.gs`
Kurir data ekspres (Kabel Fiber virtual). Mengkalkulasi pergerakan *cells* di Spreadsheet dan mem- *POST Webhook Payload* segera ke Server Python NGrok IoT Bapak secara kilat tanpa jeda polling.
### C. `Simulator.gs` (MENGAGUMKAN!)
Modul Simulator Mandiri yang mencangkok algoritma Probabilitas bersyarat (AI Bayesian Bayes) dari Python lalu ditransplantasi ke JavaScript sehingga Petani bisa mensimulasikan penyakit langsung di Jendela Animasi UI Modal Google Sheets tanpa server eksternal sekalipun!

> 🗑️ **Log Penghapusan Artefak Tab (Februari 2026):** 
> *Telah resmi digugurkan & dihapus secara aman dari Backend: `Dashboard`, `Bio - Feed Weight`, `Bio - Feeding Freq`, dan `Model_Predictions`.*
