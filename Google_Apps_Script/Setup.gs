/**
 * 🛠️ SETUP & INITIALIZATION
 * ------------------------------------------------------------------------
 * Run `initDiagnosticOptimizer()` once to create all necessary tabs.
 * ------------------------------------------------------------------------
 */

function initDiagnosticOptimizer() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // 1. Tab: SOP Tindakan
  let sopSheet = ss.getSheetByName("SOP Tindakan");
  if (!sopSheet) {
    sopSheet = ss.insertSheet("SOP Tindakan");
    // Table 1: Disease SOP
    sopSheet.getRange("A1:G1").setValues([["Nama Penyakit", "Level Bahaya", "Waktu Respons", "Tindakan 1", "Tindakan 2", "Tindakan 3", "Tindakan 4"]])
            .setFontWeight("bold").setBackground("#cfe2f3");
    
    // Table 2: Manual Check
    sopSheet.getRange("I1:J1").setValues([["Nama Parameter", "Cara Cek Manual"]])
            .setFontWeight("bold").setBackground("#d9ead3");
            
    // Add Placeholder Header for Table 2 logic
    sopSheet.getRange("H1").setValue(" | ").setHorizontalAlignment("center");
  }

  // --- NEW: Add Auto-Dropdown for SOP Tindakan ---
  const matrixSheet = ss.getSheetByName("Matrix Diagnosis");
  if (matrixSheet && sopSheet) {
    // 1. Dropdown for Penyakit (Kolom A)
    const lastRowMatrix = Math.max(3, matrixSheet.getLastRow()); // Diseases start at row 3
    const diagnoses = matrixSheet.getRange(3, 3, lastRowMatrix - 2, 1).getValues()
                                 .map(r => r[0]).filter(v => v && !v.toString().toUpperCase().includes("COST"));
    if (diagnoses.length > 0) {
      const diagValidation = SpreadsheetApp.newDataValidation().requireValueInList(diagnoses).build();
      sopSheet.getRange(2, 1, 100, 1).setDataValidation(diagValidation); // Apply to A2:A101
    }

    // 2. Dropdown for Parameter (Kolom I)
    const lastColMatrix = Math.max(4, matrixSheet.getLastColumn()); // Params start at col 4
    const parameters = matrixSheet.getRange(1, 4, 1, lastColMatrix - 3).getValues()[0]
                                  .filter(v => v && !v.toString().toUpperCase().includes("COST"));
    if (parameters.length > 0) {
      const paramValidation = SpreadsheetApp.newDataValidation().requireValueInList(parameters).build();
      sopSheet.getRange(2, 9, 100, 1).setDataValidation(paramValidation); // Apply to I2:I101
    }

    // 3. Dropdown for Level (Kolom B)
    const levelValidation = SpreadsheetApp.newDataValidation().requireValueInList(["CRITICAL", "WARNING", "INFO"]).build();
    sopSheet.getRange(2, 2, 100, 1).setDataValidation(levelValidation); // Apply to B2:B101
  }

  // 2. Tab: Konfigurasi Bot
  let configSheet = ss.getSheetByName("Konfigurasi Bot");
  if (!configSheet) {
    configSheet = ss.insertSheet("Konfigurasi Bot");
    configSheet.getRange("A1:C1").setValues([["Parameter", "Nilai", "Keterangan"]])
               .setFontWeight("bold").setBackground("#fce8b2");
    
    const defaultConfig = [
      ["algo_mode", "eff", "id3 / voi / eff"],
      ["false_alarm_rate", "0.05", "Toleransi kesalahan sensor (0-0.5)"],
      ["min_confidence_alert", "70", "Min % untuk kirim notif ke petambak"],
      ["notif_pakar_threshold", "85", "Min % untuk auto-notif pakar"],
      ["tree_max_depth", "6", "Batas kedalaman tree"],
      ["diagnosis_interval_min", "30", "Jeda menit antar auto-diagnosa"],
      ["enable_tree_mode", "TRUE", "TRUE/FALSE — tampilkan jalur tree"],
      ["enable_bayes_mode", "TRUE", "TRUE/FALSE — tampilkan probabilitas"],
      ["enable_sop", "TRUE", "TRUE/FALSE — tampilkan tindakan"],
      ["enable_voi_recommendation", "TRUE", "TRUE/FALSE — tampilkan rekomendasi tes"],
      ["sensor_timeout_min", "30", "Timeout sensor sebelum dianggap mati (menit)"],
      ["manual_timeout_min", "1440", "Timeout input manual (misal: ikan mati)"],
      ["python_webhook_url", "https://ngrok-anda.app/alert", "URL Webhook Server Python"],
      ["ai_provider", "gemini", "gemini / openai / claude"],
      ["ai_api_key", "AIzaSy...", "API Key Rahasia AI Gen"]
    ];
    configSheet.getRange(2, 1, defaultConfig.length, 3).setValues(defaultConfig);
  }

  // 3. Tab: Tree Diagnosis Result
  let treeResSheet = ss.getSheetByName("Tree Diagnosis Result");
  if (!treeResSheet) {
    treeResSheet = ss.insertSheet("Tree Diagnosis Result");
    const headers = ["Timestamp", "Diagnosa", "Conf (%)", "Depth", "Cost", "Step 1", "Step 2", "Step 3", "Step 4", "Step 5"];
    treeResSheet.getRange(1, 1, 1, headers.length).setValues([headers])
                .setFontWeight("bold").setBackground("#ead1dc");
  }

  // 4. Tab: Sensor & Alarm
  let sensorAlarmSheet = ss.getSheetByName("Sensor & Alarm");
  if (!sensorAlarmSheet) {
    sensorAlarmSheet = ss.insertSheet("Sensor & Alarm");
    const headers = ["Nama Tampilan Bot", "Lokasi Tab", "Teks Header (Keyword)", "Aman Min", "Aman Max", "Satuan", "Pesan Alarm Khusus"];
    sensorAlarmSheet.getRange(1, 1, 1, headers.length).setValues([headers])
                    .setFontWeight("bold").setBackground("#d9ead3");
    
    // Add default rows
    const defaultSensors = [
      ["Kadar Oksigen (DO)", "Water Quality", "DO", 4.0, 8.0, "mg/L", "⚠️ Aerasi bermasalah!"],
      ["Suhu Air", "Water Quality", "Temp", 26.0, 32.0, "°C", "⚠️ Suhu ekstrem!"],
      ["Kadar pH", "Water Quality", "pH", 6.5, 8.5, "", "⚠️ Air terlalu asam/basa!"],
      ["Pompa Blower", "Farm Control", "Blower", "ON", "ON", "", "🚨 Blower mati!"]
    ];
    sensorAlarmSheet.getRange(2, 1, defaultSensors.length, headers.length).setValues(defaultSensors);
  }

  SpreadsheetApp.getActive().toast("✅ BIOFLOK Diagnostic Tabs Initialized!", "Setup Success", 5);
}
