# Dokumentasi Sistem Webhook Real-time & Notifikasi Sensor

Dokumen ini mencatat perubahan sistem yang dilakukan untuk memungkinkan pembaruan aturan diagnosa secara real-time dan notifikasi otomatis saat sensor ESP32 mengirim data, menggunakan kombinasi Google Apps Script dan Webhook Python.

## 1. Konsep Utama
Sistem ini menggunakan **Webhook** untuk menghubungkan Google Spreadsheet (Sumber Data) dengan Aplikasi Python (Otak Bot).

1.  **Arah Data**: Spreadsheet -> Google Apps Script -> Ngrok (Internet) -> Python Server.
2.  **Keuntungan**:
    *   **Real-time Config Update**: Mengubah aturan diagnosa di Spreadsheet langsung berlaku di bot detik itu juga.
    *   **Live Sensor Notification**: Setiap kali ESP32 mengirim data, bot langsung memberitahu via WhatsApp tanpa menunggu jadwal cron job.
    *   **Efisiensi Tinggi**: Cache aturan ditingkatkan menjadi 24 jam karena pembaruan sudah ditangani oleh webhook, menghemat kuota API Google.

---

## 2. Perubahan pada Aplikasi Python

### `app.py` (Main Server)
*   **Endpoint Baru**: `/webhook/config-update`
    *   **Fungsi**: Menerima sinyal dari Spreadsheet bahwa aturan diagnosa telah diubah.
    *   **Aksi**: Memanggil `force_reload_config()` untuk menghapus cache dan memuat ulang aturan baru seketika.
*   **Endpoint Baru**: `/webhook/sensor-update`
    *   **Fungsi**: Menerima sinyal bahwa ada data baru masuk di tab `Water Quality` atau `Farm Control`.
    *   **Aksi**:
        1.  Mengambil data baris terakhir dari Spreadsheet (menggunakan `get_latest_sensor_data`).
        2.  Mengirim notifikasi WhatsApp berisi data mentah (DO, pH, Suhu, Timestamp) ke pakar.
        3.  Memberikan opsi "Balas 'diagnosa' untuk analisa lengkap".

### `diagnosis_engine.py` (Logika Diagnosa)
*   **Peningkatan Cache**: `config_ttl_minutes` diubah dari 5 menit menjadi **1440 menit (24 jam)**.
    *   *Alasan*: Webhook sudah menangani update instan, jadi tidak perlu polling rutin yang boros API.
*   **Fungsi Baru**: `get_latest_sensor_data()`
    *   Mengambil baris paling bawah dari tab `Water Quality` untuk keperluan notifikasi cepat.
    *   **Fitur Filter Cerdas**:
        *   Jika kolom `Source ID` (Kolom C) berisi nomor HP (dimulai dengan `+`), data **DIABAIKAN** (dianggap input manual via WA).
        *   Jika berisi lain (misal `ESP_Bioflok_01`), notifikasi **DIKIRIM**.

---

## 3. Google Apps Script (Jembatan)
Script ini dipasang di Google Spreadsheet (Extensions > Apps Script) pada file `Server.gs`. Tugasnya mendeteksi perubahan (`onChange`) dan menembak webhook ke server Python.

**Kode Final `Server.gs`:**

```javascript
/* ==========================================
   ROBOT PENGINTIP SPREADSHEET (APPS SCRIPT)
   ==========================================
   Tugas: Lapor ke Bot Python tiap ada perubahan.
   PENTING: Ganti URL NGROK setiap kali restart server!
*/
var NGROK_URL = "https://ginny-accomplished-sarina.ngrok-free.dev"; 

// === Helper Kirim Webhook ===
function sendWebhook(endpoint, payload) {
  var url = NGROK_URL + endpoint;
  try {
    var options = {
      'method' : 'post',
      'contentType': 'application/json',
      'payload' : JSON.stringify(payload),
      'muteHttpExceptions': true
    };
    UrlFetchApp.fetch(url, options); // Fire and Forget
    Logger.log("✅ Webhook sent to " + endpoint);
  } catch (e) {
    Logger.log("❌ Bot unreachable: " + e);
  }
}

// === LOGIKA UTAMA (Dipanggil Trigger OnChange) ===
function notifyBot(e) {
  // Logic deteksi nama sheet yang lebih robust untuk API update
  var sheetName = "Unknown";
  if (e && e.source) {
    sheetName = e.source.getActiveSheet().getName();
  }
  
  Logger.log("📝 Detected Change in: " + sheetName);

  // 1. UPDATE CONFIG (Edit Rules/Matrix)
  if (sheetName == "Diagnosis_Rules" || sheetName == "Matrix Diagnosis") {
     sendWebhook("/webhook/config-update", {});
  }
  
  // 2. DATA SENSOR MASUK (Water Quality / Farm Control)
  // Logic: ESP32 melakukan update via API
  else if (sheetName.indexOf("Water") > -1 || sheetName.indexOf("Control") > -1) {
     sendWebhook("/webhook/sensor-update", {"sheet": sheetName});
  }
  
  // 3. FALLBACK (Jika Google gagal deteksi nama sheet API)
  // Kita asumsikan update misterius ini update sensor -> paksa cek
  else {
     Logger.log("⚠️ Sheet tidak jelas, paksa cek sensor.");
     sendWebhook("/webhook/sensor-update", {"sheet": "Unknown-Force-Check"});
  }
}
```

---

## 4. Cara Mengaktifkan Kembali (SOP Restart)
Karena menggunakan **Ngrok Free**, URL akan berubah setiap kali sesi dimulai ulang. Ikuti langkah ini saat memulai coding lagi:

1.  **Jalankan Ngrok**:
    ```bash
    ngrok http 5000
    ```
2.  **Salin URL Baru**:
    Contoh: `https://a1b2-c3d4.ngrok-free.dev` (yang https).
3.  **Update Google Apps Script**:
    *   Buka Spreadsheet > Extensions > Apps Script.
    *   Buka file `Server.gs`.
    *   Ganti baris `var NGROK_URL = "..."` dengan URL baru.
    *   **Simpan (Ctrl+S)**.
4.  **Jalankan Server Python**:
    ```bash
    python app.py
    ```

Sistem sekarang siap:
*   Edit Rules -> Otomatis Update.
*   ESP32 Kirim Data -> Otomatis Notif WA.
