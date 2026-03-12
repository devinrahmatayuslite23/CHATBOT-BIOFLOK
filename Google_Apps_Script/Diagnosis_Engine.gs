/**
 * =========================================================================
 * ⚙️ DIAGNOSIS ENGINE (GOOGLE APPS SCRIPT EDITION)
 * =========================================================================
 * Logika ini merupakan replica 1:1 dari diagnosis_engine.py (GitHub versi asli).
 * Mengambil data dari Diagnosis_Rules dan Matrix Diagnosis secara dinamis.
 * 
 * CATATAN: Konstan TAB_RULES ("Diagnosis_Rules") dan TAB_MATRIX ("Matrix Diagnosis")
 * sudah dideklarasikan di file Rule2Matrix.gs sehingga tidak dideklarasikan ulang di sini.
 */

const SCORING_DATA_WEIGHT = 0.7;
const SCORING_PRIOR_WEIGHT = 0.3;
const DEPTH_CAP = 6;

/**
 * TRIGGER UTAMA: Dijalankan otomatis atau dipanggil manual.
 * Mengembalikan result object, atau null jika kondisi Normal.
 * ✅ MENYIMPAN ke Diagnosis History.
 */
function runAutoDiagnosis() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const rules = _fetchRules(ss);
  const matrixData = _fetchMatrix(ss);
  if (!rules || !matrixData || rules.length === 0) {
    Logger.log("❌ Rules atau Matrix kosong.");
    return null;
  }
  const tabData = _fetchTabData(ss, rules);
  const evalResult = _evaluateRules(rules, tabData);
  const snapshot = evalResult.snapshot;
  const dataValues = evalResult.dataValues;
  const results = _matchMatrix(snapshot, matrixData);

  if (results && results.length > 0) {
    const topResult = results[0];
    const resultObj = { topDiag: topResult, allResults: results, snapshot, dataValues };
    Logger.log(`🚨 Diagnosa: ${topResult.diagnosis} (${topResult.final_score.toFixed(1)}%)`);
    _saveDiagnosisHistory(ss, resultObj);
    return resultObj;
  } else {
    Logger.log("✅ Diagnosa: Kondisi Normal.");
    _saveDiagnosisHistory(ss, { topDiag: { diagnosis: "Normal", final_score: 100, matched: 0, total: 0 }, snapshot, dataValues });
    return null;
  }
}

/**
 * Sama seperti runAutoDiagnosis tapi TIDAK menyimpan ke Diagnosis History.
 * Digunakan oleh endpoint get_diagnosis_detail (read-only).
 */
function runAutoDiagnosisNoSave() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const rules = _fetchRules(ss);
  const matrixData = _fetchMatrix(ss);
  if (!rules || !matrixData || rules.length === 0) return null;

  const tabData = _fetchTabData(ss, rules);
  const evalResult = _evaluateRules(rules, tabData);
  const snapshot = evalResult.snapshot;
  const dataValues = evalResult.dataValues;
  const results = _matchMatrix(snapshot, matrixData);

  if (results && results.length > 0) {
    const topResult = results[0];
    return { topDiag: topResult, allResults: results, snapshot, dataValues };
  }
  return null;
}


// =========================================================================
// 🔹 STEP 1: BACA RULES
// =========================================================================
function _fetchRules(ss) {
  const sheet = ss.getSheetByName(TAB_RULES);
  if (!sheet) return null;

  const rows = sheet.getDataRange().getValues();
  if (rows.length < 2) return [];

  // Baris 0 = header, mulai dari baris 1
  const rules = [];
  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    if (!row[0]) continue; // Skip baris kosong

    // Kolom: [0]=param, [1]=keyword, [2]=tab_source, [3]=operator, [4]=value, [5]=logic
    const tabSrc = row[2] ? row[2].toString().trim() : "";
    if (!tabSrc || tabSrc.toUpperCase() === "UNKNOWN") continue;

    rules.push({
      param: row[0].toString().trim(),
      keyword: row[1].toString().trim(),
      tab_source: tabSrc,
      operator: row[3] ? row[3].toString().trim() : "",
      value: row[4] !== undefined ? row[4].toString().trim() : "",
      logic: row[5] ? row[5].toString().trim() : ""
    });
  }
  return rules;
}


// =========================================================================
// 🔹 STEP 2: BACA MATRIX
// =========================================================================
function _fetchMatrix(ss) {
  const sheet = ss.getSheetByName(TAB_MATRIX);
  if (!sheet) return null;
  return sheet.getDataRange().getValues();
}


// =========================================================================
// 🔹 STEP 3: BACA DATA SENSOR DARI TIAP TAB (SELALU FRESH)
// =========================================================================
function _fetchTabData(ss, rules) {
  const tabNames = new Set(rules.map(r => r.tab_source));
  const tabData = {};

  tabNames.forEach(tabName => {
    const sheet = ss.getSheetByName(tabName);
    if (sheet) {
      tabData[tabName] = sheet.getDataRange().getValues();
    } else {
      tabData[tabName] = [];
    }
  });

  return tabData;
}


// =========================================================================
// 🔹 STEP 4: EVALUASI RULES → SNAPSHOT PASS/FAIL
// Logika ini adalah replica dari Python _evaluate_rules()
// =========================================================================
function _evaluateRules(rules, tabData) {
  const snapshot = {};   // { "param_name": "PASS" / "FAIL" }
  const dataValues = {}; // { "param_name": { value, column, tab } }

  for (let rule of rules) {
    const tabName = rule.tab_source;
    const data = tabData[tabName] || [];

    if (!data || data.length < 2) {
      snapshot[rule.param] = "FAIL";
      continue;
    }

    const tabHeaders = data[0]; // Row 0 = headers
    const tabRows = data.slice(1);

    // Cari kolom di header tab berdasarkan rule.keyword (PARTIAL MATCH)
    // Sama persis dengan cara Python: `if rule["keyword"].lower() in h.lower()`
    let colIdx = -1;
    let matchedCol = null;
    for (let idx = 0; idx < tabHeaders.length; idx++) {
      if (rule.keyword.toLowerCase().includes(tabHeaders[idx].toString().toLowerCase().trim()) ||
          tabHeaders[idx].toString().toLowerCase().trim().includes(rule.keyword.toLowerCase())) {
        colIdx = idx;
        matchedCol = tabHeaders[idx];
        break;
      }
    }

    if (colIdx === -1) {
      snapshot[rule.param] = "FAIL";
      continue;
    }

    // Ambil nilai terbaru (dari bawah ke atas, cari yang tidak kosong)
    let latestVal = null;
    for (let ri = tabRows.length - 1; ri >= 0; ri--) {
      const row = tabRows[ri];
      if (colIdx < row.length && row[colIdx].toString().trim() !== "") {
        latestVal = row[colIdx].toString().trim();
        break;
      }
    }

    if (latestVal === null) {
      snapshot[rule.param] = "FAIL";
      continue;
    }

    // Evaluasi nilai vs threshold
    let passed = false;
    try {
      const numVal = parseFloat(latestVal.replace(",", "."));
      const numThreshold = parseFloat(rule.value.replace(",", "."));
      const op = rule.operator;

      if (!isNaN(numVal) && !isNaN(numThreshold)) {
        if (op === "<") passed = numVal < numThreshold;
        else if (op === ">") passed = numVal > numThreshold;
        else if (op === "<=") passed = numVal <= numThreshold;
        else if (op === ">=") passed = numVal >= numThreshold;
        else if (op === "=" || op === "==") passed = numVal === numThreshold;
        else passed = false;
      } else {
        // String comparison
        if (op === "=" || op === "==") {
          passed = latestVal.toLowerCase() === rule.value.toLowerCase();
        } else passed = false;
      }
    } catch (e) {
      passed = false;
    }

    const status = passed ? "PASS" : "FAIL";
    snapshot[rule.param] = status;
    dataValues[rule.param] = {
      value: latestVal,
      column: matchedCol || rule.keyword,
      tab: tabName
    };
  }

  return { snapshot, dataValues };
}


// =========================================================================
// 🔹 STEP 5: COCOKKAN SNAPSHOT KE MATRIX DIAGNOSIS
// Logika ini adalah replica dari Python _match_matrix()
// =========================================================================
function _matchMatrix(snapshot, matrixData) {
  const headers = matrixData[0];
  const rows = matrixData.slice(1);

  // diag_col = 2, freq_col = 1 (sama seperti Python)
  const DIAG_COL = 2;
  const FREQ_COL = 1;

  // Peta kolom header yang sesuai dengan snapshot keys
  const paramCols = {};
  for (let i = 0; i < headers.length; i++) {
    const h = headers[i].toString().trim();
    if (h in snapshot) {
      paramCols[h] = i;
    }
  }

  // Kumpulkan frekuensi untuk prior calculation
  let allFreq = [];
  for (let row of rows) {
    if (row.length <= DIAG_COL) continue;
    const d = row[DIAG_COL].toString().trim();
    if (d.toUpperCase().startsWith("COST") || d === "-" || !d) continue;
    const f = parseFloat(row[FREQ_COL]);
    allFreq.push(isNaN(f) ? 0 : f);
  }
  const totalFreq = allFreq.length > 0 ? allFreq.reduce((a, b) => a + b, 0) : 1;

  // Hitung score tiap diagnosis
  const results = [];
  for (let row of rows) {
    if (row.length <= DIAG_COL) continue;
    const diagName = row[DIAG_COL].toString().trim();
    if (diagName.toUpperCase().startsWith("COST") || diagName === "-" || !diagName) continue;

    const freqNum = parseFloat(row[FREQ_COL]) || 0;

    let totalCond = 0;
    let matchedCond = 0;
    const missedParams = [];

    for (let paramName in paramCols) {
      const colIdx = paramCols[paramName];
      if (colIdx >= row.length) continue;
      const matrixVal = row[colIdx].toString().trim().toUpperCase();
      if (matrixVal === "?" || matrixVal === "" || matrixVal === "-") continue;

      const currentVal = snapshot[paramName] || "FAIL";
      totalCond++;
      if (matrixVal === currentVal) {
        matchedCond++;
      } else {
        missedParams.push(paramName);
      }
    }

    if (totalCond === 0 || matchedCond === 0) continue;

    const matchRatio = matchedCond / totalCond * 100;
    const depthWeight = Math.min(totalCond, DEPTH_CAP) / DEPTH_CAP;
    const weightedScore = matchRatio * depthWeight;
    const prior = totalFreq > 0 ? freqNum / totalFreq : 0;
    const finalScore = (weightedScore * SCORING_DATA_WEIGHT) + (prior * 100 * SCORING_PRIOR_WEIGHT);

    results.push({
      diagnosis: diagName,
      final_score: finalScore,
      match_ratio: matchRatio,
      matched: matchedCond,
      total: totalCond,
      frequency: freqNum,
      missed: missedParams
    });
  }

  results.sort((a, b) => b.final_score - a.final_score);
  return results;
}


// =========================================================================
// 🔹 SAVE: Simpan history ke tab "Diagnosis History"
// Format: Timestamp | Diagnosa | Prob | Match | [Rule1] | [Rule2] | ...
// Header kolom Rule diisi DINAMIS dari snapshot (tidak hardcode sama sekali!)
// =========================================================================
function _saveDiagnosisHistory(ss, resultObj) {
  const HISTORY_TAB = "Diagnosis History";
  let sheet = ss.getSheetByName(HISTORY_TAB);

  // Daftar param dari snapshot (urutan mengikuti Diagnosis_Rules)
  const paramKeys = resultObj.snapshot ? Object.keys(resultObj.snapshot) : [];

  // Buat tab baru jika belum ada
  if (!sheet) {
    sheet = ss.insertSheet(HISTORY_TAB);
    const initHeader = ["Timestamp", "Diagnosa Utama", "Probability (%)", "Match", "Kemungkinan Lain"].concat(paramKeys);
    sheet.appendRow(initHeader);
    const hRange = sheet.getRange(1, 1, 1, initHeader.length);
    hRange.setFontWeight("bold").setBackground("#1a73e8").setFontColor("#ffffff");
    sheet.setFrozenRows(1);
    sheet.setColumnWidth(1, 160); // Timestamp
    sheet.setColumnWidth(2, 220); // Diagnosa
    sheet.setColumnWidth(5, 250); // Kemungkinan Lain
  }

  // Baca header yang ada sekarang
  let lastCol = sheet.getLastColumn();
  const existingHeaders = lastCol > 0
    ? sheet.getRange(1, 1, 1, lastCol).getValues()[0]
    : [];

  // Kolom fixed: Timestamp, Diagnosa, Prob, Match, Kemungkinan Lain = 5 kolom
  const FIXED_COLS = 5;

  // Ambil kolom rule yang ada
  const existingRuleCols = existingHeaders.slice(FIXED_COLS);
  const existingRuleCount = existingRuleCols.length;
  const newParamCount = paramKeys.length;

  if (existingRuleCount === 0) {
    // Tab baru, tulis header rule dari scratch
    for (let i = 0; i < paramKeys.length; i++) {
      const col = FIXED_COLS + 1 + i;
      sheet.getRange(1, col).setValue(paramKeys[i])
        .setFontWeight("bold").setBackground("#1a73e8").setFontColor("#ffffff");
    }
    existingHeaders.splice(FIXED_COLS, 0, ...paramKeys);

  } else if (newParamCount === existingRuleCount) {
    // Jumlah rule SAMA → user mungkin cuma ganti nama → RENAME POSITIONAL
    for (let i = 0; i < paramKeys.length; i++) {
      if (existingRuleCols[i] !== paramKeys[i]) {
        sheet.getRange(1, FIXED_COLS + 1 + i).setValue(paramKeys[i])
          .setFontWeight("bold").setBackground("#1a73e8").setFontColor("#ffffff");
        existingHeaders[FIXED_COLS + i] = paramKeys[i];
      }
    }

  } else if (newParamCount > existingRuleCount) {
    // Rules BERTAMBAH → rename yang sama posisi, tambahkan yang baru
    for (let i = 0; i < existingRuleCount; i++) {
      if (existingRuleCols[i] !== paramKeys[i]) {
        sheet.getRange(1, FIXED_COLS + 1 + i).setValue(paramKeys[i])
          .setFontWeight("bold").setBackground("#1a73e8").setFontColor("#ffffff");
        existingHeaders[FIXED_COLS + i] = paramKeys[i];
      }
    }
    for (let i = existingRuleCount; i < newParamCount; i++) {
      const newCol = sheet.getLastColumn() + 1;
      sheet.getRange(1, newCol).setValue(paramKeys[i])
        .setFontWeight("bold").setBackground("#1a73e8").setFontColor("#ffffff");
      existingHeaders.push(paramKeys[i]);
    }
  }
  // Jika rules BERKURANG: biarkan kolom lama (supaya data history lama tetap terbaca)

  // Re-baca header final
  lastCol = sheet.getLastColumn();
  const finalHeaders = sheet.getRange(1, 1, 1, lastCol).getValues()[0];

  // Siapkan data baris baru
  const diagnosis = resultObj.topDiag ? resultObj.topDiag.diagnosis : "Unknown";
  const probability = resultObj.topDiag ? parseFloat(resultObj.topDiag.final_score.toFixed(2)) : 0;
  const matchStr = resultObj.topDiag
    ? `${resultObj.topDiag.matched || 0}/${resultObj.topDiag.total || 0}`
    : "0/0";

  // Susun teks "Kemungkinan Lain" dari runner-up (index 1 ke atas)
  let otherDiagStr = "-";
  if (resultObj.allResults && resultObj.allResults.length > 1) {
    const others = resultObj.allResults.slice(1, 5); // Max 4 runner-up
    otherDiagStr = others
      .map((r, i) => `${i + 2}. ${r.diagnosis} (${parseInt(r.final_score)}%)`)
      .join("\n");
  }

  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  const tsStr = `${pad(now.getDate())}/${pad(now.getMonth()+1)}/${now.getFullYear()} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  const newRow = new Array(lastCol).fill("");
  newRow[0] = tsStr;
  newRow[1] = diagnosis;
  newRow[2] = probability;
  newRow[3] = matchStr;
  newRow[4] = otherDiagStr; // Kolom ke-5 = Kemungkinan Lain

  // Warna sel per kolom
  const bgColors = new Array(lastCol).fill("#ffffff");
  const fontColors = new Array(lastCol).fill("#000000");

  // Isi tiap kolom rule
  for (let param in (resultObj.snapshot || {})) {
    const status = resultObj.snapshot[param];
    const info = resultObj.dataValues ? resultObj.dataValues[param] : null;
    const val = info ? info.value : "N/A";
    const colIdx = finalHeaders.indexOf(param);
    if (colIdx !== -1) {
      newRow[colIdx] = `${val} → ${status}`;
      if (status === "PASS") {
        bgColors[colIdx] = "#d9ead3"; fontColors[colIdx] = "#274e13";
      } else if (status === "FAIL") {
        bgColors[colIdx] = "#f4cccc"; fontColors[colIdx] = "#660000";
      } else {
        bgColors[colIdx] = "#efefef"; fontColors[colIdx] = "#666666";
      }
    }
  }

  // Tulis baris data sekaligus dengan warna
  const newRowNum = sheet.getLastRow() + 1;
  const dataRange = sheet.getRange(newRowNum, 1, 1, lastCol);
  dataRange.setValues([newRow]);
  dataRange.setBackgrounds([bgColors]);
  dataRange.setFontColors([fontColors]);
}


// =========================================================================
// 🔸 WRAPPER: Dipanggil dari Menu_Utama.gs (testManualDiagnosis)
// =========================================================================
function runAutoDiagnosisWrapper() {
  return runAutoDiagnosis();
}
