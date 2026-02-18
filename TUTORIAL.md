# 📘 TUTORIAL - Smart Aquaculture WhatsApp Chatbot

> **Chatbot WhatsApp untuk Monitoring Tambak Bioflok dengan AI Analysis**
> 
> Sistem terintegrasi dengan Google Sheets, Google Drive, dan Gemini AI untuk analisa kualitas air otomatis.

---

## 📋 Daftar Isi

1. [Overview Project](#overview-project)
2. [Arsitektur Sistem](#arsitektur-sistem)
3. [File-File Inti](#file-file-inti)
4. [Setup Tutorial](#setup-tutorial)
5. [Cara Penggunaan](#cara-penggunaan)
6. [Troubleshooting](#troubleshooting)

---

## 🎯 Overview Project

### Apa itu Chatbot Ini?

Chatbot WhatsApp otomatis untuk:
- ✅ **Input data harian** (DO, pH, suhu, ikan mati, pakan, dll)
- ✅ **Input data mingguan** (sampling ikan - berat & panjang)
- ✅ **Upload foto bukti** ke Google Drive
- ✅ **Analisa AI otomatis** dengan Gemini AI
- ✅ **Alert sistem** jika ada anomali kualitas air
- ✅ **Data logging** otomatis ke Google Sheets

### Teknologi yang Digunakan

| Komponen | Teknologi | Fungsi |
|----------|-----------|--------|
| **Backend** | Python + Flask | Server aplikasi |
| **Messaging** | Twilio API | WhatsApp gateway |
| **Database** | Google Sheets | Penyimpanan data terstruktur |
| **Storage** | Google Drive | Penyimpanan foto bukti |
| **AI Engine** | Google Gemini AI | Analisa & rekomendasi otomatis |
| **Tunnel** | ngrok | Expose local server ke internet |

---

## 🏗️ Arsitektur Sistem

```
┌─────────────┐
│  WhatsApp   │ ◄──► Twilio API ◄──► ngrok ◄──► Flask App
└─────────────┘                                      │
                                                     ├──► Google Sheets (Data)
                                                     ├──► Google Drive (Foto)
                                                     └──► Gemini AI (Analisa)
```

### Flow Penggunaan:

1. **User** kirim pesan via WhatsApp
2. **Twilio** forward pesan ke webhook (via ngrok)
3. **Flask App** proses pesan & jalankan logic
4. **Google Sheets** simpan data numerik
5. **Google Drive** simpan foto bukti
6. **Gemini AI** analisa data & beri rekomendasi
7. **Response** dikirim balik ke user via WhatsApp

---

## 📁 File-File Inti

### **1. `app.py` - Main Application** ⭐ CORE

**Fungsi:** Entry point utama aplikasi, mengatur routing WhatsApp, state management, dan flow conversational.

**Key Components:**
- `whatsapp_reply()`: Handler utama untuk semua pesan masuk
- `user_state`: In-memory storage untuk tracking state user
- Menu system: Routing ke daily/weekly form atau fitur lainnya

**Flow:**
```python
User sends message → app.py receives → Route to appropriate handler
                                      ├─ Daily form
                                      ├─ Weekly form
                                      ├─ AI analysis
                                      └─ Data retrieval
```

---

### **2. `drive.py` - Google Integration** ⭐ CORE

**Fungsi:** Manajemen koneksi ke Google Sheets & Google Drive, handle upload foto dan logging data.

**Key Components:**

#### **Authentication (Hybrid System):**
```python
# Priority 1: OAuth (untuk Drive uploads)
if os.path.exists('token.pickle'):
    use OAuth credentials (user account - 15GB quota)
else:
    fallback to Service Account (no Drive quota)
```

#### **Main Functions:**

**`upload_photo(field_name, phone, date, file_url)`**
- Download foto dari Twilio
- Upload ke Google Drive (pakai OAuth)
- Return permanent Google Drive URL
- Fallback ke Twilio URL jika gagal

**`log_reading(phone, data_dict)`**
- Log data harian ke Google Sheets
- Format: timestamp, DO, pH, temp, dead_fish, dll
- Auto-create headers jika belum ada

**`log_weekly(phone, data_dict)`**
- Log data mingguan (sampling 30 ikan)
- Format: timestamp, fish_N_length, fish_N_weight

**`get_latest_daily_data()`**
- Ambil data terakhir dari spreadsheet
- Digunakan untuk fitur "Cek Data Terakhir"

**`log_ai_analysis(category, input_data, analysis_text)`**
- Log hasil analisa AI ke tab khusus
- Untuk audit trail & tracking

---

### **3. `ai_helper.py` - AI Intelligence** ⭐ CORE

**Fungsi:** Analisa data kualitas air dengan Gemini AI, deteksi anomali, dan generate rekomendasi.

**Key Functions:**

**`check_out_of_range(data)`**
- Cek parameter di luar batas SOP (dari `thresholds.py`)
- Return dict anomali yang terdeteksi
- Skip nilai None/empty

**`generate_recommendations(alerts, lang="en")`**
- Kirim data anomali ke Gemini AI
- AI generate hipotesis & saran perbaikan
- Format ringkas untuk WhatsApp (max 800 char)

**Example:**
```python
data = {"do": 12.5, "ph": 6.0}
alerts = check_out_of_range(data)  # {'do': 12.5}
recommendations = generate_recommendations(alerts, "id")
# Output: 
# - DO tinggi: Kurangi aerasi
# - Risiko: Gas Bubble Disease
# - Action: Monitor setiap 1 jam
```

---

### **4. `scheduler.py` - Automation & Alerts**

**Fungsi:** Background jobs, auto-reminders, dan alert system.

**Key Functions:**

**`send_whatsapp_message(to, body)`**
- Kirim pesan WhatsApp via Twilio API
- Digunakan untuk reminders & alerts

**`notify_experts(sender, data)`**
- Deteksi anomali kualitas air
- Kirim alert ke pakar via WhatsApp
- Include analisa AI & rekomendasi

**`send_daily_reminder()`**
- Scheduled job: kirim reminder input data harian
- Default: Setiap hari jam 8 pagi & 5 sore

**`schedule_jobs()`**
- Setup semua scheduled jobs (APScheduler)
- Called saat startup server

---

### **5. `forms/` - Form Definitions**

#### **`daily_form.py`**
```python
daily_form_id = [
    {"key": "do", "name": "Oksigen Terlarut (DO)", ...},
    {"key": "ph", "name": "Tingkat Keasaman Air (pH)", ...},
    {"key": "temp", "name": "Suhu air", ...},
    ...
]
```

#### **`weekly_form.py`**
```python
generate_weekly_form(lang):
    # Generate form untuk 30 ikan
    # Setiap ikan: panjang + berat + foto
```

---

### **6. `thresholds.py` - SOP Parameters**

**Fungsi:** Definisi batas aman parameter kualitas air (Standard Operating Procedure).

```python
SOP_THRESHOLDS = {
    "do": {"min": 4.0, "max": 8.0},      # mg/L
    "ph": {"min": 6.5, "max": 8.5},      # pH scale
    "temperature": {"min": 26, "max": 32},  # Celsius
    "dead_fish": {"min": 0, "max": 5}    # ekor/hari
}
```

AI akan detect anomali jika nilai di luar range ini.

---

### **7. Configuration Files**

#### **`.env` - Environment Variables** 🔐 SECRET
```bash
# Twilio (WhatsApp Gateway)
TWILIO_ACCOUNT_SID=AC7aaec...
TWILIO_AUTH_TOKEN=204ccf...
TWILIO_PHONE_NUMBER=whatsapp:+14155238886

# Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=credentials.json
GOOGLE_DRIVE_FOLDER_ID=1FmwB3T-EX9eoDZXa9NPIVPENj0FIM2mu
SPREADSHEET_ID=1mRxH3sRqq_FsXa5KRyMJZLqMEIMBIjPf1U312me0TBA

# Gemini AI
GEMINI_API_KEY=AIzaSyA0Pv...

# Server
PORT=5000
```

#### **`credentials.json`** 🔐 SECRET
Google Cloud Service Account credentials (untuk Sheets API).

#### **`oauth_credentials.json`** 🔐 SECRET
OAuth 2.0 credentials (untuk Drive API dengan user quota).

#### **`token.pickle`** 🔐 SECRET
OAuth token hasil login (auto-generated, jangan share!).

---

## 🚀 Setup Tutorial

### Prerequisites

- ✅ Python 3.8+
- ✅ Google Account
- ✅ Twilio Account (free trial OK)
- ✅ Akses internet stabil
- ✅ ngrok installed

---

### Step 1: Clone & Install Dependencies

```bash
cd E:\BIOFLOK\fishfarmingchatbotisp-main
pip install -r requirements.txt
```

**Dependencies utama:**
- `flask` - Web framework
- `twilio` - WhatsApp API
- `gspread` - Google Sheets API
- `google-api-python-client` - Google Drive API
- `google-generativeai` - Gemini AI
- `APScheduler` - Background jobs

---

### Step 2: Setup Google Cloud Project

#### 2.1 Buat Project di Google Cloud Console

1. Buka: https://console.cloud.google.com/
2. Create New Project → Nama: "bioflokchatbot"
3. Enable APIs:
   - Google Sheets API
   - Google Drive API

#### 2.2 Buat Service Account (untuk Sheets)

1. IAM & Admin → Service Accounts → Create
2. Download JSON → simpan sebagai `credentials.json`

#### 2.3 Buat OAuth Credentials (untuk Drive)

1. APIs & Services → Credentials → Create OAuth 2.0 Client ID
2. Application type: **Desktop app**
3. Download JSON → simpan sebagai `oauth_credentials.json`

#### 2.4 Setup OAuth Consent Screen

1. OAuth consent screen → External
2. App name: "Bioflok Chatbot"
3. **Add Test Users** → masukkan email Anda
4. Save

---

### Step 3: Setup Google Sheets

1. Buat spreadsheet baru: "Lab Test Bioflok"
2. Buat 3 sheets:
   - `Daily Survey Input` (data harian)
   - `Weekly Survey Input` (data mingguan)
   - `AI Analysis Log` (log analisa AI)
3. Copy Spreadsheet ID dari URL
4. Share dengan service account email (dari credentials.json)

---

### Step 4: Setup Google Drive

1. Buat folder: "Foto Lab Test"
2. Copy Folder ID dari URL
3. Share dengan service account (Editor access)

---

### Step 5: Setup Twilio

1. Daftar: https://www.twilio.com/try-twilio
2. Get WhatsApp Sandbox number
3. Copy:
   - Account SID
   - Auth Token
   - WhatsApp number

---

### Step 6: Setup Gemini AI

1. Buka: https://makersuite.google.com/app/apikey
2. Create API key
3. Copy API key

---

### Step 7: Configure .env File

Edit file `.env`:

```bash
# Twilio
TWILIO_ACCOUNT_SID=<your_sid>
TWILIO_AUTH_TOKEN=<your_token>
TWILIO_PHONE_NUMBER=whatsapp:+14155238886

# Google
GOOGLE_APPLICATION_CREDENTIALS=credentials.json
GOOGLE_DRIVE_FOLDER_ID=<your_folder_id>
SPREADSHEET_ID=<your_sheet_id>

# Gemini
GEMINI_API_KEY=<your_api_key>

# Server
PORT=5000
```

---

### Step 8: OAuth Authorization (One-Time)

**PENTING:** Ini wajib dilakukan untuk enable Drive uploads!

```bash
python oauth_authorize.py
```

**Yang terjadi:**
1. Browser akan terbuka
2. Login dengan akun Google Anda
3. Klik "Allow" untuk berikan akses
4. Token tersimpan di `token.pickle`
5. **Selesai! Tidak perlu login lagi**

---

### Step 9: Start Server

#### Terminal 1: Flask App
```bash
python app.py
```

Output:
```
🔑 Using OAuth credentials for Drive...
 * Running on http://127.0.0.1:5000
```

#### Terminal 2: ngrok
```bash
ngrok http 5000
```

Output:
```
Forwarding  https://abc123.ngrok.io -> http://localhost:5000
```

---

### Step 10: Configure Twilio Webhook

1. Copy ngrok URL: `https://abc123.ngrok.io`
2. Twilio Console → WhatsApp Sandbox Settings
3. "WHEN A MESSAGE COMES IN" → `https://abc123.ngrok.io/whatsapp`
4. Save

---

### Step 11: Test WhatsApp Bot

1. Join sandbox: Kirim `join <keyword>` ke Twilio number
2. Kirim pesan: `Menu`
3. ✅ Bot akan balas dengan menu!

---

## 📱 Cara Penggunaan

### Menu Utama

Ketik `Menu` atau `Hi` untuk mulai:

```
🌊 Smart Aquaculture System Ready.
Silakan pilih aktivitas:

1️⃣ Input Laporan Harian
2️⃣ Laporan Mingguan
3️⃣ Cek Data Terakhir
4️⃣ Analisa AI Manual
5️⃣ 📂 Buka Database (Spreadsheet)
```

---

### 1️⃣ Input Laporan Harian

**Flow:**
1. Pilih `1`
2. Pilih parameter (1-9):
   - 1: DO (Oksigen Terlarut)
   - 2: pH
   - 3: Suhu air
   - 4: Ikan mati
   - 5: Frekuensi pemberian makan
   - 6: Berat pakan
   - 7: Frekuensi inverter saat makan
   - 8: Frekuensi inverter saat istirahat
   - 9: Video umum air
3. Input data:
   - **Kirim angka saja** (contoh: `7.5`)
   - **Atau kirim foto dengan caption angka** (contoh: foto meter DO dengan caption `7.5`)
4. Ulangi untuk parameter lain
5. Ketik `Selesai` untuk submit

**Hasil:**
- ✅ Data tersimpan di Google Sheets
- ✅ Foto tersimpan di Google Drive
- ✅ AI auto-analisa jika ada anomali
- ✅ Alert ke pakar jika critical

---

### 2️⃣ Laporan Mingguan

**Flow:**
1. Pilih `2`
2. Input data per ikan (1-30):
   - Panjang (cm)
   - Berat (gram) + foto timbangan
3. Bisa `Skip` untuk lewati ikan tertentu
4. Ketik `Selesai` untuk submit lebih awal

**Tips:**
- Bisa submit partial data (tidak harus 30 ikan)
- Foto timbangan wajib untuk validasi

---

### 3️⃣ Cek Data Terakhir

Menampilkan data harian terakhir yang tersimpan.

---

### 4️⃣ Analisa AI Manual

Jalankan analisa AI manual terhadap data terakhir.

**Output:**
- Status kualitas air (AMAN/ANOMALI)
- Hipotesis jika ada masalah
- Rekomendasi tindakan

---

### 5️⃣ Buka Database

Mendapatkan link langsung ke Google Sheets.

---

## 🔧 Troubleshooting

### Problem 1: Error 404 saat POST /whatsapp

**Cause:** Route tidak ditemukan atau server belum running.

**Solution:**
```bash
# Cek apakah app.py running
# Cek route di app.py ada @app.route("/whatsapp")
# Restart server
```

---

### Problem 2: Upload foto gagal (Status 401)

**Cause:** Twilio credentials salah atau expired.

**Solution:**
```bash
# Cek .env
TWILIO_ACCOUNT_SID=<harus benar>
TWILIO_AUTH_TOKEN=<harus benar>

# Test credentials
python check_service_account.py
```

---

### Problem 3: Upload foto gagal (Status 403 - Service Account quota)

**Cause:** Service Account tidak punya storage quota.

**Solution:**
```bash
# Setup OAuth (sudah dijelaskan di tutorial)
python oauth_authorize.py

# Pastikan token.pickle ter-generate
ls token.pickle

# Restart app
python app.py
```

---

### Problem 4: AI Analysis error (TypeError: float() argument)

**Cause:** Data None tidak di-handle dengan benar.

**Solution:**
Sudah diperbaiki di `ai_helper.py`:
```python
if val is None or val == '' or val == '-':
    continue
```

---

### Problem 5: Twilio message limit (50/day)

**Cause:** Trial account terbatas.

**Solution:**
- Upgrade ke Twilio paid account ($20/bulan)
- Atau disable auto-notifications sementara

---

### Problem 6: ngrok URL berubah setiap restart

**Cause:** ngrok free tier generate random URL.

**Solution:**
- Upgrade ke ngrok paid (static domain)
- Atau update Twilio webhook setiap restart ngrok

---

## 📊 Data Flow Diagram

```
User sends "Menu" via WhatsApp
        ↓
Twilio receives message
        ↓
Twilio POST to webhook: https://abc123.ngrok.io/whatsapp
        ↓
ngrok forwards to localhost:5000
        ↓
Flask app.py receives POST /whatsapp
        ↓
app.whatsapp_reply() processes message
        ↓
Check user_state[sender]
        ↓
Route to appropriate handler:
├─ Menu → Show main menu
├─ "1" → Daily form flow
├─ "2" → Weekly form flow
├─ "3" → Get latest data
└─ "4" → AI analysis
        ↓
Process & save data:
├─ drive.log_reading() → Google Sheets
├─ drive.upload_photo() → Google Drive
└─ ai_helper.generate_recommendations() → Gemini AI
        ↓
Response sent back to user
```

---

## 🎓 Advanced Topics

### Custom Thresholds

Edit `thresholds.py`:
```python
SOP_THRESHOLDS = {
    "do": {"min": 5.0, "max": 7.0},  # Custom range
    ...
}
```

### Add New Parameters

1. Edit `forms/daily_form.py`:
```python
daily_form_id.append({
    "key": "ammonia",
    "name": "Ammonia (mg/L)",
    "prompt": "Masukkan kadar ammonia..."
})
```

2. Edit `thresholds.py`:
```python
SOP_THRESHOLDS["ammonia"] = {"min": 0, "max": 0.02}
```

3. Update spreadsheet headers di `drive.py`

---

### Scheduled Reminders

Edit `scheduler.py`:
```python
def schedule_jobs():
    scheduler.add_job(
        send_daily_reminder,
        'cron',
        hour=8,  # Jam 8 pagi
        minute=0,
        id='morning_reminder'
    )
```

---

## 📝 Maintenance Checklist

### Daily
- ✅ Cek ngrok masih running
- ✅ Monitor error logs di terminal

### Weekly
- ✅ Backup Google Sheets
- ✅ Review AI analysis logs
- ✅ Cek storage quota Drive

### Monthly
- ✅ Update dependencies: `pip install -r requirements.txt --upgrade`
- ✅ Refresh OAuth token (auto, tapi cek jika ada issue)
- ✅ Review & optimize thresholds

---

## 🆘 Support & Contact

**Project by:** Bioflok Research Team

**Issues?** 
- Check logs di terminal
- Review file `TUTORIAL.md` ini
- Test dengan `check_service_account.py`

---

## 📄 License

Private project for aquaculture research.

---

**Last Updated:** 27 Januari 2026
**Version:** 2.0 (OAuth-enabled)
