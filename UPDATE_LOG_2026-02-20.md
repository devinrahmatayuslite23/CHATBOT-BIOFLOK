# 🚀 UPDATE LOG: Migrasi SDK Gemini AI (20 Februari 2026)

## 📌 Ringkasan Pembaruan
Sistem Chatbot Smart Aquaculture baru saja mendapatkan pembaruan penting pada inti pemrosesan AI. 
Library `google.generativeai` (yang telah berstatus *deprecated* / dihentikan dukungannya oleh Google) **telah resmi diganti** dengan SDK terbaru yaitu `google-genai`.

**Apa yang berubah secara teknis?**
1. **Requirements**: Package `google-generativeai` diganti menjadi `google-genai` (versi 1.64.0 atau terbaru).
2. **Inisialisasi Client**: Konfigurasi lama (`genai.configure`) diganti dengan sistem *Client-based* (`client = genai.Client(api_key=...)`).
3. **Pemanggilan Model Target**: Sinkronisasi pemanggilan model menggunakan parameter `client.models.generate_content(model='gemini-2.5-flash', contents=...)` di dalam `ai_helper.py` dan `diagnosis_engine.py` untuk memastikan koneksi yang lebih stabil dan respons AI yang lebih akurat.

Pembaruan ini memastikan bahwa:
- Peringatan (Warning) *deprecated* di terminal Python sudah sepenuhnya hilang.
- Fitur AI seperti *Copilot Aerasi* dan *Analisa Diagnosa Kolam* tetap berjalan lancar tanpa terblokir masalah kuota/error akibat SDK lama.

---

## 🛠️ Persiapan Awal (Workflow Setup)
Sebelum mulai menggunakan sistem Chatbot Bioflok pasca-update, pastikan Anda telah menyiapkan hal-hal berikut:

### 1. Update Dependencies (Wajib!)
Jika Anda baru saja menarik kode (*pull*) dari GitHub atau memindahkan *source code*, pastikan environment Python Anda sudah diperbarui agar mengunduh versi Gemini yang baru:
```bash
pip install -r requirements.txt
```

### 2. Menyiapkan Akses Google Cloud (Service Account & OAuth)
Sistem ini menggunakan sinkronisasi canggih ke Google Workspace. Berikut adalah cara menyiapkan file rahasianya:

**A. Membuat Service Account (`credentials.json`) — Untuk Database Google Sheets**
*Service Account* berfungsi sebagai "robot perantara" untuk mengisi baris/menulis data di Google Sheets selama 24 jam nonstop secara sekejap.
1. Buka [Google Cloud Console](https://console.cloud.google.com/).
2. Buat Project baru (misal: "bioflokchatbot") atau pilih *project* lama Anda.
3. Cari **"Google Sheets API"** dan **"Google Drive API"** di kotak pencarian atas, lalu klik tombol **Enable** pada keduanya.
4. Buka menu samping, pilih **IAM & Admin** > **Service Accounts** > **Create Service Account**.
5. Setelah dibuat, klik alamat email akun servis tersebut > tab **Keys** > **Add Key** > **Create New Key** > pilih **JSON**.
6. Ganti nama file unduhan tersebut menjadi `credentials.json` dan letakkan di dalam folder *chatbot* Anda.
*(PENTING: Salin alamat email Service Account itu (berakhiran `.iam.gserviceaccount.com`). Lalu buka Spreadsheet Anda, klik **Share**, dan masukkan email tersebut sebagai "Editor" agar bot bisa menulis di tab Anda).*

**B. Membuat Kredensial OAuth (`oauth_credentials.json`) — Untuk Media Google Drive**
Untuk mengakali pembatasan ruang penyimpanan (*storage limit*) bagi bot, fitur *upload* media foto/video bot disalurkan secara *OAuth* memakai dompet memori 15 GB di akun Google reguler Anda:
1. Kembali ke Google Cloud halaman **APIs & Services** > **OAuth consent screen**.
2. Pilih mode **External** > lengkapi *App name* dan *User support email*. Tepat di langkah bertajuk **Test users**, ketikkan dan daftarkan email pribadi/Google yang sama > klik Save.
3. Pindah tab ke **Credentials** > **Create Credentials** > **OAuth client ID**.
4. Pada label *Application Type*, pilih opsi **Desktop app**.
5. Tekan tombol _Download_ JSON. Masukkan ke folder bot Anda dan ganti namanya wajib menjadi `oauth_credentials.json`.

### 3. Konfigurasi Variabel Server (`.env`)
Pastikan file `.env` Anda sudah terisi dan me-referensikan file kredensial Google tersebut dengan benar. Parameter baru `google-genai` tetap membaca format API Gemini lama:
```bash
# Gateway Chatbot WhatsApp (Twilio)
TWILIO_ACCOUNT_SID=xxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_PHONE_NUMBER=whatsapp:+14155238886

# Kredensial Akses Google yang Dibuat di Langkah-2
GOOGLE_APPLICATION_CREDENTIALS=credentials.json
GOOGLE_DRIVE_FOLDER_ID=xxx
SPREADSHEET_ID=xxx

# Kunci Eksekusi AI Gemini
GEMINI_API_KEY=xxx

# Konfigurasi Port Server
PORT=5000
```

### 4. Eksekusi Autentikasi OAuth Drive
Bagi pengguna *fresh* atau jika Anda baru mengganti *email Test Users*, Anda **harus membangun kunci final** ke media Drive (berupa file _cache_ sandi `token.pickle`). Lakukan ritual skrip sekali seumur hidup berikut lewat terminal Anda:
```bash
python oauth_authorize.py
```
*(Akan membuka Browser Google Chrome > Login Email > Bila ada layar peringatan "Google hasn't verified this app" klik **Lanjutkan (Continue) / Advanced > Go to Bioflok** > Centang kotak otoritas Drive > Lalu biarkan perintah tertutup sendirinya)*.

---

## 🌊 Workflow Chatbot (Cara Pengoperasian)

Setelah persiapan di atas dipastikan aman, ini adalah alur kerja (workflow) harian untuk mulai mengoperasikan sistem:

### 1. Menyalakan Aplikasi
Buka dua terminal / Command Prompt (atau dua *tab* terminal di VS Code).
- **Terminal 1** (Menjalankan inti aplikasi Flask):
  ```bash
  python app.py
  ```
- **Terminal 2** (Menjalankan *tunneling* agar server di komputer Anda bisa "ditengok" dari WhatsApp):
  ```bash
  ngrok http 5000
  ```

### 2. Mengaitkan Webhook Twilio
Setiap kali ngrok dinyalakan, URL internetnya bisa berubah (jika menggunakan versi gratis).
- Ambil alamat URL sementara dari terminal ngrok (contoh: `https://abcd-123.ngrok.app`).
- Masukkan URL tersebut ke **Dashboard Twilio** > navigasi ke **WhatsApp Sandbox Settings**. 
- Pada baris isian **"When a message comes in"**, cantumkan URL tersebut dan akhiri dengan kata `/whatsapp` (contoh: `https://abcd-123.ngrok.app/whatsapp`). **Klik Save**.

### 3. Interaksi Chatbot via HP (Go-Live!)
Sistem sudah siap menerima pesan. Silakan ambil HP Anda:
- **Kirim kata sandi Twilio** (seperti `join <nama-bot>`) jika Anda baru pertama kali memakai sandbox.
- **Kirim "Menu"**: Bot akan langsung merespons dengan navigasi utama.
- **Laporan Harian Praktis**: Alih-alih melewati menu panjang, Anda bisa langsung mengetik parameter lengkap. Contoh: `do 5.5 ph 7.2` (Bisa disertakan dengan pengiriman foto dari galeri HP). Bot akan langsung membaca pola datanya lewat Regex!
- **Fitur AI Copilot Aerasi (Opsi 6)**: Jika diakses, server bot akan memanggil SDK `google-genai` terbaru dan memulai *chat history* sehingga Anda dapat saling berbalas pesan tentang solusi pengadaan kincir air atau masalah oksigen.
- **Fitur Analisa AI Cerdas (Diagnosa Kolam)**: Ketik opsi `9`, lalu balas kembali dengan perintah `"analisa"`. Bot akan bekerja layaknya konsultan tambak profesional untuk membaca status matriks spreadsheet Anda secara seketika!
