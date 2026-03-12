# 🚀 UPDATE LOG: Arsitektur Bioflok Chatbot V2 (Maret 2026)

## 📌 Ringkasan Pembaruan
Sistem Chatbot telah mengalami evolusi arsitektur berskala *Enterprise* dari **Monolitik (Semua logika diurus Python)** menjadi **Microservices (Hybrid Python + Google Apps Script)**. Pembaruan ini dirancang agar sistem tidak lagi *lagging* atau lambat, menghemat kuota Token AI (Gemini), dan mempercepat hitungan matematis (sekitar 0.1 detik).

---

## 🏗️ 1. Pembaruan Arsitektur & Fungsi Program Terbaru

### A. Fitur DO Analyzer (Oksigen Terlarut)
- **Versi Lama:** Python (`do_analyzer.py`) harus mengunduh ratusan baris data historis dari Google Sheets menggunakan `gspread` lalu menghitung rumus matematiknya (regresi) pelan-pelan secara lokal. Sangat boros bandwidth dan waktu.
- **Versi Baru (`DO_Analyzer.gs` + `do_analyzer.py`):**
  - **Lahirnya GAS API**: Menghitung slope anjloknya DO, butuh kincir angin berapa HP, dan level bahaya sekarang, **100% dipindahkan ke Google Apps Script (GAS)**.
  - **Kesadaran Waktu (Time-of-day Awareness)**: Sistem matematis ini kini mengenali jam saat diakses. Ia bisa membedakan mana *Penurunan DO Wajar di Malam Hari (karena respirasi/hewan & tumbuhan bernafas)* dan mana *Penurunan DO Bahaya di Siang Hari (karena mendung atau plankton mati massal / plankton crash)*—mendapatkan hasil ini **tanpa memerlukan koneksi ke AI**.

### B. Fitur Kalkulator Pakan (Feed Calculator)
- **Versi Lama:** Python membaca tab `Sampling` (buat cari berat ikan terakhir) dan mengaplikasikan hitungannya secara manual.
- **Versi Baru (`Feed_Calculator.gs`):**
  - Kalkulasi pemberian pakan berdasarkan berat badan terbaru, hitungan estimasi biomassa, jadwal otomatis pemberian pakan (jam 07, 12, 17), dan estimasi biaya harian langsung ditarik dari *Awan (Google Apps Script)* sehingga super ringan, bebas gagal karena API `gspread` putus asa.

### C. Konteks AI Cerdas (AI Memory Injector)
- **Fungsi Baru (`API_Endpoint.gs --> _generateAiContext`)**:
  Google Apps Script telah diajari untuk berperan sebagai "Suster" yang merangkum *Rekam Medis* kolam seminggu terakhir (10 Data Air terakhir, 5 Kematian terakhir, 5 Pakan terakhir).
- Data rekam medis inilah yang akan disuntik diam-diam ke otak Gemini. Membuat Bot Copilot jauh lebih interaktif karena **menjawab berdasarkan sejarah pola data (tidak lagi halusinasi).**

---

## 🔄 2. Workflow (Alur Kerja) Chatbot Terbaru

Alur kerja Chatbot saat menggunakan menu **Oksigen**, **Pakan**, atau **Analisa** sekarang dibagi menjadi 2 Tahap (*Tier*). Hal ini untuk menyiasati mahalnya kuota API Gemini dan memastikan Bot selalu aktif *(Fail-Safe)*.

### Tahap 1: Cek Rutin Penuh / Standard Math (Gratis & Kuota 0)
*Berlaku untuk user menekan angka `6` (Aerasi) atau `7` (Pakan).*
1. **User Request**: User mengetik pesan "aerasi".
2. **Ping ke GAS**: Python *tidak membaca/mendownload sheet!* Tapi Python mengirimkan surat perintah HTTP ke Google Script (`action: get_aeration`).
3. **Cloud Processing**: Server Google membaca Sheets sebelahnya murni cuma 0.1 detik, melakukan Regresi Kolam, lalu menyusun jawabannya ke format JSON matang.
4. **Respon Cepat (Whatsapp)**: Python melempar hasil JSON itu ke WA pengguna (*"Status DO Menurun 0.3 mg/L... Pakai kincir 2.5 HP"*).
5. ***Fallback System***: Kalau *API Google-nya mati / Error*, Python otomatis pakai cara lama mengunduhnya sendiri pelan-pelan. **Bot Tidak Akan Crash!**

### Tahap 2: Konsultasi Interaktif / Copilot AI (Gunakan Quota AI)
*Berlaku jika user menekan tombol `tanya ai` dari dalam menu Aerasi / Analisa.*
1. **Panggilan Panik**: User bingung melihat hasil hitungan, "tanya ai".
2. **Kumpul Dokumen**: Python tidak menghitung lagi, tapi menyerahkan paket lengkap hitungan sebelumnya (termasuk *Rekam Medis GAS*) dan memberikannya kepada Gemini-2.0.
3. **AI Menjawab**: Copilot memahami data secara ilmiah lalu meramal dengan bahasa manusia. *"Ohh DO bapak turun di siang hari padahal kincir nyala, awas Pak ini indikasi Crash Plankton yang mendadak mati."*
4. Chatbot siap ngobrol bebas (Sesi Copilot) hingga user mengetik `"Menu"`.

---

## 🏆 Kesimpulan & Keunggulan V2
- Server Lokal (Python / Laptop) menjadi **sangat ringan (Hanya API / WhatsApp Router)**.
- Aplikasi sudah bergaya **Microservices** dan *Scalable* sehingga tidak masalah meski meladeni ribuan kolom data dari Spreadsheet.
- Ketergantungan pada GeminiAI dipotong **hingga 80%**, karena peringatan kritis sudah dapat dikeluarkan oleh rumusan biologi murni (Tanpa menggunakan LLM).
- **Semua Bug 429 Quota Exceeded (AI Limit)** hanya akan terjadi di saat User meminta konsultasi manual, bukan lagi terjadi pada pemrosesan latar belakang bot harian.
