# ðŸ Ÿ BIOFLOK SYSTEM: Dual-Brain Diagnosis Engine

Bioflok System adalah platform manajemen kualitas air dan diagnostik pintar untuk budidaya ikan (lele/nila) bersistem Bioflok. Sistem ini menggunakan arsitektur **Dual-Brain AI (Bayesian Probability + Decision Tree)** yang ditanamkan langsung pada **Google Sheets / Apps Script** dan dihubungkan ke asisten virtual melalui **Python Chatbot**.

---

## âš™ï¸  Arsitektur Sistem Utama (Core System)

Otak utama dari AI analisis data berjalan sepenuhnya di dalam **Google Apps Script**. Data parameter air kolam dikumpulkan secara *real-time*, dievaluasi secara matematis, lalu kesimpulannya dikirimkan ke petambak.

### ðŸ“‚ Struktur File Google Apps Script (Inti Sistem)

Berikut adalah penjelasan fungsi dari masing-masing file skrip yang menggerakkan sistem:

1. **`Diagnosis_Engine.gs` (Mesin AI Utama)**
   - Merupakan jantung dan otak utama dari aplikasi ini.
   - Bertugas memproses data kolam dengan 3 tahap evaluasi (Pintu Keamanan):
     - **Pintu 1 (Threshold Alarm):** Mengecek batas kritis tiap parameter dan mendeteksi sensor mati/basi (kalkulasi *Value of Information* / VOI).
     - **Pintu 2 (Bayesian Inference):** Menghitung probabilitas (persentase) kemungkinan masalah/penyakit berdasarkan kecocokan data empiris dengan *Matrix SOP*.
     - **Pintu 3 (Decision Tree C4.5):** Menghasilkan jalur pohon keputusan logis untuk menghasilkan kesimpulan diagnosa final (skenario apa yang sedang terjadi di kolam).
   - Mencetak log laporan berformat emoji rapi untuk dikirim ke Chatbot (WA/Telegram).

2. **`API_Endpoint.gs` (Jembatan Komunikasi / Webhook)**
   - Bertindak sebagai jembatan (API) yang menerima perintah HTTP (GET/POST) dari server luar (Python Chatbot).
   - Memastikan bahwa saat *chatbot* meminta laporan, fungsi `runCombinedDiagnosis()` di Engine Utama dipanggil secara aman.

3. **`server.gs` (Trigger \u0026 Konfigurasi push-notification)**
   - Menyimpan logika konfigurasi webhook (seperti Ngrok URL) yang digunakan Google Sheets untuk **menembak balik (Push)** hasil diagnosis ke Python server secara otomatis, misal jika dipicu oleh *cronjob*.
   - Mengatur fungsi `onEdit` yang memantau perubahan langsung dari sel di Google Sheet.

4. **`Rule2Matrix.gs` (Database Manager \u0026 Sinkronisasi SOP)**
   - Skrip yang bertugas "menerjemahkan" SOP bahasa manusia di tab `Diagnosis_Rules` menjadi format matriks matematika (0, 1, null) di tab `Matrix Diagnosis`.
   - Mengelola pembaruan *header*, kolom, baris, dan pengolahan *Import/Export CSV* agar pengguna (petambak) bisa meracik aturan penyakit baru tanpa perlu koding.

5. **`DiagnosticTree.gs` (Mesin Struktur Jalur Data)**
   - Mesin algoritma struktural untuk menyusun simpul (*nodes*) pohon keputusan berdasarkan *Information Gain*.
   - Mampu mengekstraksi logika internal AI menjadi teks berformat *MermaidJS* agar dapat divisualisasikan secara visual (transparansi AI / *Explainable AI*).

6. **`Menu_Utama.gs` (Pusat Navigasi UI)**
   - Menggabungkan seluruh tombol fungsionalitas dan meletakkannya di *Menu Bar* atas Google Sheets (Menu "ðŸ Ÿ BIOFLOK SYSTEM").
   - Menghubungkan klik tombol dengan fungsi pemanggilan UI (*Dashboard, Test Diagnosa, Sync Matrix, dll*).

7. **`Setup.gs`**
   - File pendukung untuk instalasi pertama kali, membantu membuat Trigger waktu (Time-driven) atau mereset properti rahasia (*ScriptProperties*).

### ðŸ–¥ï¸  File Antarmuka Pop-up (HTML)
File HTML ini dipanggil oleh *Menu_Utama.gs* untuk memunculkan antarmuka visual di dalam layar Google Sheets:
- **`DiagnosisPopup.html`**: Layar hasil simulasi diagnosa yang dimodelkan menyerupai gelembung *chat* WhatsApp, lengkap dengan SOP dan peringatan VOI.
- **`TreeVisualPopup.html`**: Dasbor *visualizer* interaktif canggih yang merender grafik pohon keputusan secara *real-time* dan interaktif (dapat diekspor ke PDF).

---

## ðŸ  Komponen Server Python (Bot Eksternal)

*(Bagian ini dikelola di komputer server lokal / Heroku untuk menghubungkan Sheets ke antarmuka aplikasi pesan)*

### File Utama Python
- **`app.py` / `diagnosis_engine.py`**: Melakukan inisialisasi webhook Ngrok dan berfungsi menangkap respon (payload JSON) dari `API_Endpoint.gs` Google Sheets.
- **`daily_form.py` \u0026 `weekly_form.py`**: Definisi *form* dialog yang ditanyakan ke pengguna (petambak).
- **`ai_helper.py`**: Konfigurasi parameter sensor dan penentuan ambang batas nilai peringatan.
- **`scheduler.py`**: Mesin pewaktu (*cronjob*) Python yang mengirimkan alarm harian/mingguan.

### Deployment Instructions (Python/Heroku)

**One-Time Setup**
```bash
heroku create
heroku buildpacks:set heroku/python
heroku config:set $(cat .env | xargs)
git push heroku main
```

**Redeploy After Changes**
```bash
git add .
git commit -m "Update konfigurasi"
git push origin main
git push heroku main
```

---
*Dokumentasi ini otomatis diperbarui sejalan dengan arsitektur V2 AI.*
