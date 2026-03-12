/**
 * =========================================================================
 * 🌐 API ENDPOINT UNTUK CHATBOT PYTHON
 * =========================================================================
 * Script ini bertindak sebagai jembatan (API) agar Bot Python bisa meminta 
 * Google Sheets untuk menjalankan diagnosa dan mengembalikan hasilnya dalam
 * format JSON yang sesuai dengan yang diharapkan oleh diagnosis_engine.py.
 *
 * Actions:
 * - run_diagnosis         → Jalankan diagnosa + simpan ke Diagnosis History
 * - get_diagnosis_detail  → Jalankan diagnosa TANPA simpan ke History (read-only)
 */

function doPost(e) {
  return handleRequest(e);
}

function doGet(e) {
  return handleRequest(e);
}

function handleRequest(e) {
  try {
    let action = "";
    if (e.parameter && e.parameter.action) {
      action = e.parameter.action;
    } else if (e.postData && e.postData.contents) {
      const body = JSON.parse(e.postData.contents);
      action = body.action || "";
    }

    // ======================
    // ACTION: run_diagnosis (FULL - simpan ke History)
    // ======================
    if (action === "run_diagnosis") {
      const resultObj = runAutoDiagnosis(); // Jalankan + simpan ke History
      return _jsonResponse(_buildDiagnosisPayload(resultObj));
    }
    
    // ======================
    // ACTION: get_diagnosis_detail (READ-ONLY - TIDAK simpan ke History)
    // ======================
    if (action === "get_diagnosis_detail") {
      const resultObj = runAutoDiagnosisNoSave(); // Jalankan TANPA simpan
      return _jsonResponse(_buildDiagnosisPayload(resultObj));
    }

    // ======================
    // ACTION: get_ai_context (Fetch Data Historis untuk AI)
    // ======================
    if (action === "get_ai_context") {
      let type = "do";
      if (e.parameter && e.parameter.type) {
        type = e.parameter.type;
      } else if (e.postData && e.postData.contents) {
        const body = JSON.parse(e.postData.contents);
        type = body.type || type;
      }
      const ctx = _generateAiContext(type);
      return _jsonResponse(ctx);
    }

    // Fallback
    return _jsonResponse({ "status": "error", "error_message": "Unknown action: " + action });

  } catch (error) {
    return _jsonResponse({
      "status": "error",
      "error_message": error.toString()
    });
  }
}

/**
 * Buat JSON payload dari result object diagnosis.
 * Dipre-share oleh run_diagnosis dan get_diagnosis_detail.
 */
function _buildDiagnosisPayload(resultObj) {
  if (!resultObj) {
    return { "status": "normal", "message": "Kondisi Normal" };
  }

  // trigger_values: hanya parameter yang PASS, format "param: value"
  const triggerArr = [];
  if (resultObj.dataValues) {
    for (let param in resultObj.dataValues) {
      const status = resultObj.snapshot ? resultObj.snapshot[param] : "FAIL";
      if (status === "PASS") {
        const info = resultObj.dataValues[param];
        const val = info ? info.value : "N/A";
        triggerArr.push(`${param}: ${val}`);
      }
    }
  }

  // all_results: seluruh diagnosa terurut (untuk kemungkinan lain)
  const allResultsArr = (resultObj.allResults || []).map(r => ({
    diagnosis: r.diagnosis,
    final_score: r.final_score,
    matched: r.matched,
    total: r.total,
    frequency: r.frequency
  }));

  return {
    "status": "danger",
    "top_diagnosis": resultObj.topDiag.diagnosis,
    "final_score": resultObj.topDiag.final_score,
    "matched_conditions": resultObj.topDiag.matched,
    "total_conditions": resultObj.topDiag.total,
    "trigger_values": triggerArr,
    "snapshot": resultObj.snapshot || {},
    "all_results": allResultsArr
  };
}

function _jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * =========================================================================
 * 🔹 FUNGSI BANTU GENERATE AI CONTEXT (TREN DATA)
 * =========================================================================
 */
function _generateAiContext(type) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  if (type === "do") {
    const sheet = ss.getSheetByName("Water Quality");
    if (!sheet) return { status: "error", message: "Tab Water Quality missing" };
    
    // Convert to values
    const rows = sheet.getDataRange().getValues();
    const now = new Date();
    // Ambil window 24 jam terakhir (atau 48 jam jika perlu fallback)
    const cutoff = new Date(now.getTime() - (24 * 60 * 60 * 1000)); 
    let readings = [];
    
    for (let i = 1; i < rows.length; i++) {
        const row = rows[i];
        const tsMatch = row[0]; // Timestamp
        const doVal = row[3];
        if (!tsMatch || doVal === "" || doVal === "-") continue;
        
        let ts = new Date(tsMatch);
        if (ts.toString() === "Invalid Date") continue;
        
        if (ts >= cutoff || i > rows.length - 10) { 
            readings.push({
                timestamp: Utilities.formatDate(ts, Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm:ss"),
                do_value: parseFloat(doVal.toString().replace(",", ".")),
                device: row[2] || "Unknown",
                temperature: row[9] || "-"
            });
        }
    }
    
    readings.sort((a,b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
    const recentReadings = readings.slice(-24); // Maksimal 24 data point untuk menghemat token
    
    return {
        status: "success",
        context_type: "do",
        data: recentReadings
    };
  }
  
  if (type === "diagnosis") {
     const diagObj = runAutoDiagnosisNoSave();
     
     // 1. Get recent trends
     const waterSheet = ss.getSheetByName("Water Quality");
     let recentWater = [];
     if (waterSheet) {
         const rows = waterSheet.getDataRange().getValues();
         const lastRows = rows.slice(-10); // last 10 readings
         recentWater = lastRows.map(r => {
             let ts = new Date(r[0]);
             let tsStr = (ts.toString() !== "Invalid Date") ? Utilities.formatDate(ts, Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm:ss") : r[0];
             return {
                 time: tsStr,
                 do: r[3] !== undefined ? r[3] : "-",
                 ph: r[5] !== undefined ? r[5] : "-",
                 temp: r[9] !== undefined ? r[9] : "-",
                 tds: r[7] !== undefined ? r[7] : "-"
             };
         });
     }
     
     // 2. Get recent dead fish
     const deadSheet = ss.getSheetByName("Bio - Dead Fish");
     let recentDead = [];
     if (deadSheet) {
         const rows = deadSheet.getDataRange().getValues();
         const lastRows = rows.slice(-5);
         recentDead = lastRows.map(r => ({
             time: r[0],
             count: r[2] !== undefined ? r[2] : "-"
         }));
     }

     // 3. Get recent feed
     const feedSheet = ss.getSheetByName("Feed Tracker");
     let recentFeed = [];
     if (feedSheet) {
         const rows = feedSheet.getDataRange().getValues();
         const lastRows = rows.slice(-5);
         recentFeed = lastRows.map(r => ({
             date: r[0],
             feed_kg: r[2] !== undefined ? r[2] : "-"
         }));
     }
     
     return {
         status: "success",
         context_type: "diagnosis",
         diagnosis_result: diagObj ? _buildDiagnosisPayload(diagObj) : null,
         recent_water_quality: recentWater,
         recent_dead_fish: recentDead,
         recent_feed: recentFeed
     };
  }
  
  return { status: "error", message: "Unknown context type: " + type };
}

