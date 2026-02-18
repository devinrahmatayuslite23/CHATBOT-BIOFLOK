# 📋 UPDATE LOG — 17-18 Februari 2026

## 🎯 Ringkasan Perubahan

### 1. ✅ Diagnosis Engine Terpadu (`diagnosis_engine.py`)
- Semua jalur diagnosa (manual input, menu "9", background) sekarang menggunakan **satu engine yang sama**
- Engine membaca **langsung dari tab sumber** (Water Quality, Farm Control, Bio, Sampling) — tidak ada dependency ke Dashboard
- Fungsi utama: `format_diagnosa_response()`, `format_diagnosa_detail()`, `generate_diagnosa_explanation()`

### 2. 🗑️ Dashboard Tab Dihapus
- Tab **DASHBOARD** di Google Sheets sudah dihapus
- `realtime_tab = get_worksheet("DASHBOARD", ...)` dihapus dari `drive.py`
- Semua kode yang menulis/membaca dari Dashboard sudah dibersihkan
- Menu 3 "Cek Data" sekarang baca dari tab **WATER QUALITY**
- Menu 4 "Analisa AI" tidak lagi pakai kolom "Current Diagnosis" dari Dashboard

### 3. 🔄 Background Sync Dihapus
- `auto_sync_job()` yang polling tiap 30 detik dihapus dari `scheduler.py`
- Diagnosis sekarang hanya jalan saat:
  - Data masuk (sensor/manual) → otomatis
  - User minta (ketik "9"/"diagnosa") → on-demand
- **Hemat API quota Google Sheets & Gemini**

### 4. 🧠 Fitur Analisa AI (Baru)
- Ketik **"analisa"** atau **"analisis"** di WhatsApp → AI Gemini menjelaskan diagnosa
- Penjelasan meliputi: MENGAPA diagnosa masuk akal, hubungan antar parameter, langkah konkrit
- **Hanya dipanggil manual** (hemat kuota Gemini free tier)
- Error handling rapi — kalau kuota habis, muncul pesan user-friendly, bukan dump error mentah

### 5. 💰 Optimasi Kuota API
- Gemini AI **tidak lagi dipanggil** saat background sync atau auto-diagnosis
- Gemini **hanya dipanggil** saat user ketik "4" atau "analisa"
- Background polling 30 detik dihapus → hemat Google Sheets API

### 6. 🔧 Perbaikan Error Handling
- Error Gemini 429 (quota exceeded) sekarang tampil pesan rapi: "⚠️ Kuota AI harian sudah habis"
- Tidak lagi menampilkan raw API error ke WhatsApp

---

## 📱 Keyword WhatsApp Aktif

| Ketik | Fungsi |
|:---|:---|
| `menu` / `halo` | Reset ke menu utama |
| `1` | Input Laporan Harian |
| `2` | Laporan Mingguan |
| `3` | Cek Data Terakhir (Water Quality) |
| `4` | Analisa AI Spesifik (Gemini) |
| `5` | Buka Database Spreadsheet |
| `6` | Cek Aerasi (DO Analysis) |
| `7` | Kalkulasi Pakan |
| `8` | Kalibrasi pH |
| `9` / `diagnosa` | Diagnosa Kolam (Engine) |
| `detail` | Breakdown Top 5 + semua rules |
| `analisa` | Penjelasan AI Gemini |

---

## 📁 File Inti Sistem

| File | Fungsi |
|:---|:---|
| `app.py` | WhatsApp webhook handler utama |
| `drive.py` | Google Sheets interaction + data logging |
| `diagnosis_engine.py` | Dynamic Matrix Diagnosis engine |
| `ai_helper.py` | Gemini AI integration |
| `scheduler.py` | Background jobs (reminder harian/mingguan) |
| `feed_calculator.py` | Kalkulasi pakan |
| `do_analyzer.py` | Analisis DO/Aerasi |
| `ph_drift_detector.py` | Kalibrasi & monitoring pH |
| `model_validator.py` | Validasi model prediksi |
| `thresholds.py` | Konfigurasi SOP thresholds |

---

## ⚙️ File yang Diperlukan (Config/Auth)

| File | Fungsi |
|:---|:---|
| `.env` | Environment variables |
| `credentials.json` | Google service account |
| `oauth_credentials.json` | OAuth user credentials |
| `token.pickle` | OAuth token cache |
| `oauth_authorize.py` | Script untuk refresh OAuth |
| `get_ngrok_url.py` | Helper untuk mendapatkan URL ngrok |
| `requirements.txt` | Python dependencies |
| `Procfile` | Heroku deployment config |
