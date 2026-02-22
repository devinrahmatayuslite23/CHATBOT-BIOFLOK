var NGROK_URL = "https://ginny-accomplished-sarina.ngrok-free.dev"; 

function sendWebhook(endpoint, payload) {
  var url = NGROK_URL + endpoint;
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
     sendWebhook("/webhook/sensor-update", {"sheet": sheetName});
  }
  
  // 3. FALLBACK: Jika Google gagal deteksi nama sheet saat API update
  // Kita asumsikan update dari API itu biasanya data Sensor, jadi kita paksa cek sensor
  else {
     Logger.log("⚠️ Nama sheet tidak jelas, asumsi update sensor.");
     sendWebhook("/webhook/sensor-update", {"sheet": "Unknown-Force-Check"});
  }
}
