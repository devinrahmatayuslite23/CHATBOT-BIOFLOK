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
