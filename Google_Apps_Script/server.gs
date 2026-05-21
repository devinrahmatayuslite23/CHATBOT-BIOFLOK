function sendWebhook(endpoint, payload) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const config = _getConfig(ss);
  var url = (config.python_webhook_url || "") + endpoint;
  try {
    var options = {
      'method' : 'post',
      'contentType': 'application/json',
      'payload' : JSON.stringify(payload),
      'muteHttpExceptions': true
    };
    UrlFetchApp.fetch(url, options);
  } catch (e) {
    Logger.log("Err: " + e);
  }
}

// TRIGGER ON CHANGE
function notifyBot(e) {
  // CARA DETEKSI SHEET YANG LEBIH AKURAT UNTUK API
  var sheetName = "Unknown";
  
  if (e && e.source) {
    // Coba ambil sheet aktif (biasanya benar untuk manual edit)
    sheetName = e.source.getActiveSheet().getName();
  }
  
  Logger.log("Detected Change in: " + sheetName);

  // 1. Jika Rules/Matrix -> Config Webhook
  if (sheetName == "Diagnosis_Rules" || sheetName == "Matrix Diagnosis") {
     sendWebhook("/webhook/config-update", {});
  }
  
  // 2. Jika Water Quality -> Sensor Webhook
  // [MODIFIKASI] Kita buat lebih longgar, jika mengandung kata "Water" atau "Quality"
  else if (sheetName.indexOf("Water") > -1 || sheetName.indexOf("Control") > -1) {
     
     // 🚀 JALANKAN DIAGNOSIS OFFLINE DI GOOGLE SHEETS DULU (Bypass Python)
     try {
       // Cek apakah tabel/engine sudah diload
       if (typeof runCombinedDiagnosis === 'function') {
         var result = runCombinedDiagnosis(false);
         if (result && result.topDiag) {
            // Tulis hasil diagnosa ke sheet jika diperlukan (Optional untuk nanti)
            Logger.log("✅ Auto Diagnosa GAS Selesai.");
         }
       }
     } catch (err) {
       Logger.log("❌ Gagal jalankan diagnosa GAS: " + err);
     }
     
     // Tetap kirim webhook ke Python untuk keperluan WhatsApp dll
     sendWebhook("/webhook/sensor-update", {"sheet": sheetName});
  }
  
  // 3. FALLBACK: Jika Google gagal deteksi nama sheet saat API update
  // Kita asumsikan update dari API itu biasanya data Sensor, jadi kita paksa cek sensor
  else {
     Logger.log("⚠️ Nama sheet tidak jelas, asumsi update sensor.");
     
     // 🚀 JALANKAN DIAGNOSIS OFFLINE DI GOOGLE SHEETS DULU
     try {
       if (typeof runCombinedDiagnosis === 'function') {
         runCombinedDiagnosis(false);
       }
     } catch (err) { Logger.log("Error fallback: " + err); }
     
     sendWebhook("/webhook/sensor-update", {"sheet": "Unknown-Force-Check"});
  }
}
