/**
 * =========================================================================
 * âš™ï¸ DIAGNOSIS ENGINE (DUAL-BRAIN AI) - GOOGLE APPS SCRIPT EDITION V2
 * =========================================================================
 * Arsitektur "Satu Otak, Dua Wajah"
 * Pintu 1: Sensor & Alarm (Batas Aman/Anomali)
 * Pintu 2: Rule Engines (Decision Tree & Bayesian Log-Odds)
 * Pintu 3: Shannon Entropy (Value of Information ID3)
 */

function _getConfig(ss) {
  const config = {
    algo_mode: "eff",
    false_alarm_rate: 0.05,
    min_confidence_alert: 70,
    sensor_timeout_min: 30,
    manual_timeout_min: 1440,
    python_webhook_url: ""
  };
  const sheet = ss.getSheetByName("Konfigurasi Bot");
  if(sheet) {
    const data = sheet.getDataRange().getValues();
    for(let i=1; i<data.length; i++) {
       const key = data[i][0];
       let val = data[i][1];
       if(!key) continue;
       if(key === "false_alarm_rate" || key === "min_confidence_alert" || key === "sensor_timeout_min" || key === "manual_timeout_min") val = parseFloat(val);
       if(val === "TRUE") val = true;
       if(val === "FALSE") val = false;
       config[key] = val;
    }
  }
  return config;
}

function _fetchLatestValue(ss, tabName, keyword, config) {
  const sheet = ss.getSheetByName(tabName);
  if(!sheet) return {value: null, status: "N/A", ageMin: 9999, displayVal: "N/A"};
  const data = sheet.getDataRange().getValues();
  if(data.length < 2) return {value: null, status: "N/A", ageMin: 9999, displayVal: "N/A"};
  
  const headers = data[0];
  let colIdx = -1;
  let timestampColIdx = 0;
  const keywordLower = keyword.toLowerCase().trim();

  // Cari kolom berdasarkan nama PERSIS dari Diagnosis_Rules (case-insensitive)
  for(let i = 0; i < headers.length; i++) {
    const h = headers[i].toString().toLowerCase().trim();
    if(h === keywordLower) colIdx = i;
    if(h.includes("time") || h.includes("stamp") || h.includes("waktu")) timestampColIdx = i;
  }

  Logger.log(`[DEBUG] Tab="${tabName}" Keyword="${keyword}" â†’ kolomIdx=${colIdx}, header="${colIdx>=0?headers[colIdx]:'TIDAK ADA'}"`);

  if(colIdx === -1) return {value: null, status: "N/A", ageMin: 9999, displayVal: "N/A"};
  
  for(let r = data.length-1; r>=1; r--) {
    const val = data[r][colIdx];
    if(val !== undefined && val.toString().trim() !== "") {
       const ts = data[r][timestampColIdx];
       let ageMin = 0;
       if(ts instanceof Date) {
         ageMin = (new Date().getTime() - ts.getTime()) / 60000;
       } else if(ts) {
          const d = new Date(ts.toString().replace(/-/g, "/"));
          if(!isNaN(d)) ageMin = (new Date().getTime() - d.getTime()) / 60000;
       }
       
       let timeout = config.sensor_timeout_min;
       if(tabName.toUpperCase().includes("SAMPLING") || tabName.toUpperCase().includes("MANUAL") || tabName.toUpperCase().includes("DEAD")) {
           timeout = config.manual_timeout_min;
       }
       
       if(ageMin > timeout) {
         return {value: val, status: "N/A", ageMin: ageMin, displayVal: `N/A (Basi > ${timeout}m)`};
       }
       return {value: val, status: "FRESH", ageMin: Math.round(ageMin), displayVal: val.toString()};
    }
  }
  return {value: null, status: "N/A", ageMin: 9999, displayVal: "N/A"};
}

// =========================================================================
// PINTU 1: VALIDASI SENSOR & ALARM (KONDISI AMAN / NORMAL)
// =========================================================================
function _checkSensorAlarms(ss, config) {
  const sheet = ss.getSheetByName("Sensor & Alarm");
  // Jika tab kosong / tidak ada â†’ semua aman, diagnosis tetap jalan
  if(!sheet) return {isSafe: true, alarms: [], sensorWarnings: [], rawDataCache: {}};
  
  const data = sheet.getDataRange().getValues();
  // Cek apakah ada baris data setelah header
  const dataRows = data.slice(1).filter(r => r[0] && r[0].toString().trim() !== "");
  if(dataRows.length === 0) return {isSafe: true, alarms: [], sensorWarnings: [], rawDataCache: {}};
  
  const alarms = [];        // â† Nilai MELEWATI batas aman (anomali nyata)
  const sensorWarnings = []; // â† Sensor mati/basi (catatan, bukan pemblokir)
  const rawDataCache = {};
  
  for(let i=0; i<dataRows.length; i++) {
    const row = dataRows[i];
    const name = row[0];
    const tabName = row[1];
    const keyword = row[2];
    const amanMin = row[3];
    const amanMax = row[4];
    const alarmMsg = row[6];
    
    if(!tabName || !keyword) continue;

    const tabKey = `${tabName}_${keyword}`;
    if(!rawDataCache[tabKey]) {
        rawDataCache[tabKey] = _fetchLatestValue(ss, tabName, keyword, config);
    }
    const valObj = rawDataCache[tabKey];
    
    // Sensor mati: catat sebagai sensorWarnings BUKAN alarms
    // (tidak memblokir diagnosis, hanya dicatat di JSON output)
    if(valObj.status === "N/A") {
      sensorWarnings.push(`âš ï¸ ${name}: Data tidak ada/basi (>${config.sensor_timeout_min} mnt)`);
      continue;
    }
    
    // Cek apakah nilai melewati batas aman â†’ ini barulah ALARM NYATA
    if(valObj.value !== null && amanMin !== "" && amanMax !== "") {
      const numMin = parseFloat(amanMin);
      const numMax = parseFloat(amanMax);
      if(!isNaN(numMin) && !isNaN(numMax)) {
        const num = parseFloat(valObj.value.toString().replace(",", "."));
        if(!isNaN(num) && (num < numMin || num > numMax)) {
          alarms.push(`âŒ ${name}: ${num} (Batas Aman: ${numMin}-${numMax}) â†’ ${alarmMsg}`);
        }
      } else {
        // Perbandingan teks (misal: Blower ON/OFF)
        if(valObj.value.toString().trim().toUpperCase() !== amanMin.toString().toUpperCase()) {
          alarms.push(`ðŸš¨ ${name}: ${valObj.value} (Harusnya: ${amanMin}) â†’ ${alarmMsg}`);
        }
      }
    }
  }
  
  // isSafe = true HANYA ketika:
  // 1. Tab Sensor & Alarm kosong (belum dikonfigurasi)
  // 2. SEMUA sensor FRESH (tidak basi) DAN SEMUA dalam batas aman
  //
  // Jika ada data BASI â†’ status tidak pasti â†’ lemparkan ke mesin VOI untuk memandu petambak!
  const isSafe = (alarms.length === 0 && sensorWarnings.length === 0);
  const isMissingData = (sensorWarnings.length > 0);
  
  return {isSafe, isMissingData, alarms, sensorWarnings, rawDataCache};
}

// =========================================================================
// PINTU 2: RULE ENGINE & DECISION TREE (Mencari PASS/FAIL/ N/A)
// =========================================================================
function _fetchRules(ss) {
  const sheet = ss.getSheetByName("Diagnosis_Rules");
  if(!sheet) return [];
  const rows = sheet.getDataRange().getValues();
  const rules = [];
  for(let i=1; i<rows.length; i++) {
    const row = rows[i];
    if(!row[0] || !row[2]) continue;
    rules.push({
      param:      row[0].toString().trim(),
      keyword:    row[1].toString().trim(),
      tab_source: row[2].toString().trim(),
      operator:   row[3].toString().trim(),
      value:      row[4] !== undefined ? row[4].toString().trim() : "",
      logic:      row[5] ? row[5].toString().trim() : "",
      desc:       row[15] ? row[15].toString().trim() : "" // Kolom deskripsi rule
    });
  }
  return rules;
}

function _evaluateRules(ss, rules, config, rawDataCache) {
  const snapshot = {};
  const dataValues = {};
  const missingParams = [];
  const paramToKeyword = {};
  
  for(let rule of rules) {
    paramToKeyword[rule.param] = rule.keyword;
    const tabKey = `${rule.tab_source}_${rule.keyword}`;
    let valObj = rawDataCache[tabKey];
    if(!valObj) {
      valObj = _fetchLatestValue(ss, rule.tab_source, rule.keyword, config);
      rawDataCache[tabKey] = valObj;
    }
    
    let status = "FAIL";
    let mathStr = "";
    
    if(valObj.status === "N/A") {
       status = "N/A";
       if(!missingParams.includes(rule.param)) missingParams.push(rule.param);
       mathStr = `(Data Kosong / Basi)`;
    } else {
       const op = rule.operator;
       let passed = false;
       try {
         const numVal = parseFloat(valObj.value.toString().replace(",", "."));
         const numThresh = parseFloat(rule.value.replace(",", "."));
         if(!isNaN(numVal) && !isNaN(numThresh)) {
            if(op === "<") passed = numVal < numThresh;
            else if(op === ">") passed = numVal > numThresh;
            else if(op === "<=") passed = numVal <= numThresh;
            else if(op === ">=") passed = numVal >= numThresh;
            else if(op === "=" || op === "==") passed = numVal === numThresh;
            mathStr = `(Real: ${numVal} ${op} Target: ${numThresh})`;
         } else {
            if(op === "=" || op === "==") passed = valObj.value.toString().toUpperCase() === rule.value.toString().toUpperCase();
            mathStr = `(Real: ${valObj.value} ${op} Target: ${rule.value})`;
         }
       } catch(e) { passed = false; }
       status = passed ? "PASS" : "FAIL";
    }
    
    snapshot[rule.param] = status;
    dataValues[rule.param] = {
      value: valObj.value,
      status: status,
      mathStr: mathStr,
      ageMin: valObj.ageMin || 0,   // â† umur data dalam menit
      desc: rule.desc || mathStr
    };
  }
  
  return {snapshot, dataValues, missingParams, paramToKeyword};
}

// =========================================================================
// PILAR 2: BAYESIAN INFERENCE (LOG-ODDS)
// =========================================================================
function _fetchSOPMatrix(ss) {
  const sheet = ss.getSheetByName("SOP Tindakan");
  if(!sheet) return {};
  const rows = sheet.getDataRange().getValues();
  const sopMap = {};
  for(let i=1; i<rows.length; i++) {
     const diag = rows[i][0] ? rows[i][0].toString().trim() : "";
     if(!diag) continue;
     sopMap[diag] = {
       level: rows[i][1] || "INFO",
       waktu: rows[i][2] || "-",
       tindakan: [rows[i][3], rows[i][4], rows[i][5], rows[i][6]].filter(Boolean)
     };
  }
  return sopMap;
}

// =========================================================================
// ðŸ“– BACA PANDUAN CEK MANUAL DARI SOP TINDAKAN (Kolom I & J)
// Layout: | H(pemisah) | I: Nama Parameter | J: Cara Cek Manual |
// =========================================================================
function _fetchManualCheckGuide(ss) {
  const sheet = ss.getSheetByName("SOP Tindakan");
  if(!sheet) return {};
  const rows = sheet.getDataRange().getValues();
  const guide = {};
  for(let i = 1; i < rows.length; i++) {
    const paramName = rows[i][8]; // Kolom I (index 8)
    const caraCek   = rows[i][9]; // Kolom J (index 9)
    if(paramName && paramName.toString().trim() !== '') {
      guide[paramName.toString().trim()] = caraCek ? caraCek.toString().trim() : '';
    }
  }
  return guide;
}

function _calculateBayesianScore(snapshot, matrixData, config, sopMap) {
  const headers = matrixData[0];
  const rows = matrixData.slice(1);
  const falseAlarm = config.false_alarm_rate || 0.05; // P(T=Fail | F=Absent)
  
  // â”€â”€ Prior: Frekuensi total (identik dgn client) â”€â”€
  let allFreq = [];
  for(let r of rows) {
    if(!r[2] || r[2].toString().toUpperCase().startsWith("COST") || r[2]==="-") continue;
    allFreq.push(parseFloat(r[1]) || 1);
  }
  const totalFreq = allFreq.reduce((a,b)=>a+b, 0) || 1;
  const results = [];
  
  for(let row of rows) {
    const diagName = row[2] ? row[2].toString().trim() : "";
    if(!diagName || diagName.toUpperCase().startsWith("COST") || diagName==="-") continue;
    
    const freq = parseFloat(row[1]) || 1;
    const prior = freq / totalFreq; // P(H)
    let logOdds = Math.log(prior / (1 - prior)); // Base Prior Log Odds
    
    let totalCond = 0;
    const matchedParams    = [];
    const mismatchedParams = [];
    const missedRules      = [];
    const reqMap           = {};
    
    // â”€â”€ Likelihood Update (identik dgn client runBayesianInference) â”€â”€
    // Untuk setiap parameter di Matrix:
    //   Matrix val â†’ sensitivity (nullâ†’0.5, 1â†’0.99, 0â†’0.01)
    //   obs FAIL â†’ LR+ = sens / falseAlarm
    //   obs PASS â†’ LR- = (1-sens) / (1-falseAlarm)
    for(let i=3; i<headers.length; i++) {
       const param = headers[i].toString().trim();
       if(!param) continue;
       const matrixVal = row[i].toString().trim().toUpperCase();
       if(matrixVal === "?" || matrixVal === "" || matrixVal === "-") continue;
       
       reqMap[param] = matrixVal;
       totalCond++;
       
       const currentVal = snapshot[param];
       
       if(currentVal === "N/A" || !currentVal) {
         // Data N/A â†’ skip, tidak update logOdds (identik dgn client: obs === null)
         missedRules.push(param);
         continue;
       }
       
       // â”€â”€ Sensitivity dari Matrix (identik dgn client) â”€â”€
       // Client: sens = row.vals[hIdx]
       //   if (sens === null) sens = 0.5
       //   else if (sens === 1) sens = 0.99
       //   else if (sens === 0) sens = 0.01
       //
       // PENTING: sens di client = P(T=Fail | Fault=Present)
       //   sens=0.99 artinya: jika matrix=1(PASS), maka P(Fail|Present)=0.99
       //   sens=0.01 artinya: jika matrix=0(FAIL), maka P(Fail|Present)=0.01
       let sens;
       if(matrixVal === "PASS" || matrixVal === "1" || matrixVal === "TRUE") {
         sens = 0.99; // matrix=1 â†’ sens = 0.99
       } else if(matrixVal === "FAIL" || matrixVal === "0" || matrixVal === "FALSE" || matrixVal === "-1" || matrixVal === "2") {
         sens = 0.01; // matrix=0 â†’ sens = 0.01
       } else {
         sens = 0.5;  // matrix=null â†’ no info
       }
       
       let p_fail_given_absent = falseAlarm;
       
       // â”€â”€ Observation (IDENTIK dgn client line 1511-1523) â”€â”€
       if(currentVal === "FAIL") {
         // Client: obs === 0 (FAIL) â†’ num = sens, den = p_fail_given_absent
         let num = sens; // P(Fail | Present) = sens
         let den = p_fail_given_absent;
         if(den === 0) den = 0.001;
         logOdds += Math.log(num / den);
         
         // Match/mismatch tracking
         if(matrixVal === "FAIL" || matrixVal === "0" || matrixVal === "FALSE" || matrixVal === "-1" || matrixVal === "2") {
           matchedParams.push(param);
         } else {
           mismatchedParams.push(param);
         }
       } else if(currentVal === "PASS") {
         // Client: obs === 1 (PASS) â†’ num = 1 - sens, den = 1 - p_fail_given_absent
         let num = 1 - sens; // P(Pass | Present) = 1 - sens
         let den = 1 - p_fail_given_absent;
         if(den === 0) den = 0.001;
         logOdds += Math.log(num / den);
         
         // Match/mismatch tracking
         if(matrixVal === "PASS" || matrixVal === "1" || matrixVal === "TRUE") {
           matchedParams.push(param);
         } else {
           mismatchedParams.push(param);
         }
       }
    }
    
    if(totalCond === 0) continue;
    
    // â”€â”€ Sigmoid: LogOdds â†’ Probability (identik dgn client) â”€â”€
    const prob = 1 / (1 + Math.exp(-logOdds));
    
    const sop = sopMap[diagName] || {level: 'WARNING', tindakan: ['SOP Belum Dibuat']};
    
    results.push({
       diagnosis: diagName,
       final_score: parseFloat((prob * 100).toFixed(1)),
       matchedParams: matchedParams,
       mismatchedParams: mismatchedParams,
       reqMap: reqMap,
       total: totalCond,
       missedData: missedRules,
       level: sop.level,
       sopList: sop.tindakan
    });
  }

  if(results.length === 0) return [];

  // â”€â”€ TIDAK ada penalti N/A coverage (identik dgn client) â”€â”€
  // Client langsung sort tanpa scale-down.

  // Sort dari kemungkinan terkuat
  results.sort((a, b) => b.final_score - a.final_score);
  return results;
}

// =========================================================================
// PILAR 3: TRUE VALUE OF INFORMATION (Shannon Entropy)
// =========================================================================
//
// Formula:
//   VOI(X) = H(D) âˆ’ E[H(D|X)]
//
// Dimana:
//   H(D) = Entropy distribusi penyakit saat ini (ketidakpastian)
//   E[H(D|X)] = Expected entropy SETELAH mengukur parameter X
//             = P(X=PASS) Ã— H(D|X=PASS) + P(X=FAIL) Ã— H(D|X=FAIL)
//
//   Posterior via Bayes:
//   P(D_i | X=obs) = P(X=obs | D_i) Ã— P(D_i) / P(X=obs)
//
// =========================================================================
function _calculateEntropyVOI(bayesResults, matrixData, missingParams) {
   if(missingParams.length === 0 || bayesResults.length === 0) return [];
   
   // â”€â”€ 1. Distribusi probabilitas penyakit saat ini â”€â”€
   const highProbIllnesses = [];
   for(let i = 0; i < bayesResults.length; i++) {
      const res = bayesResults[i];
      if((res.final_score > 5 || i < 3) && res.final_score > 0) {
         highProbIllnesses.push(res);
      }
   }
   if(highProbIllnesses.length === 0) return [];
   
   // Normalisasi ke distribusi probabilitas (sum = 1.0)
   const totalScore = highProbIllnesses.reduce((s, r) => s + r.final_score, 0);
   const probs = highProbIllnesses.map(r => r.final_score / totalScore);
   
   // â”€â”€ 2. Entropy saat ini H(D) â”€â”€
   let currentEntropy = 0;
   for(let p of probs) {
      if(p > 0) currentEntropy -= p * (Math.log(p) / Math.log(2));
   }
   
   // â”€â”€ 3. Baca requirement matrix & cost â”€â”€
   const headers = matrixData[0];
   const costMap = {};
   const matrixReqs = {}; // { "D23": { "Low DO": "PASS", "High pH": "FAIL", ... } }
   
   for(let row of matrixData.slice(1)) {
      const name = row[2] ? row[2].toString().trim() : "";
      if(!name || name === "-") continue;
      
      if(name.toUpperCase().startsWith("COST")) {
         for(let i = 3; i < headers.length; i++) {
            costMap[headers[i].toString().trim()] = parseFloat(row[i]) || 5;
         }
         continue;
      }
      
      matrixReqs[name] = {};
      for(let i = 3; i < headers.length; i++) {
         const param = headers[i].toString().trim();
         const val = row[i].toString().trim().toUpperCase();
         if(val === "1" || val === "PASS" || val === "TRUE") {
            matrixReqs[name][param] = "PASS";
         } else if(val === "0" || val === "2" || val === "FAIL" || val === "FALSE" || val === "-1") {
            matrixReqs[name][param] = "FAIL";
         } else {
            matrixReqs[name][param] = null; // Tidak relevan untuk penyakit ini
         }
      }
   }
   
   // â”€â”€ 4. Kumpulkan parameter N/A dari 2 sumber â”€â”€
   const universalMissingParams = new Set();
   for(let ill of highProbIllnesses) {
      for(let m of ill.missedData) {
         universalMissingParams.add(m);
      }
   }
   for(let mp of missingParams) {
      universalMissingParams.add(mp);
   }
   
   // â”€â”€ 5. Hitung TRUE VOI tiap parameter â”€â”€
   const voiScores = [];
   
   for(let param of universalMissingParams) {
      const cost = costMap[param] || 5;
      
      // Sensitivity per-penyakit:
      // Jika matrix bilang penyakit D_i expects PASS â†’ P(X=PASS | D_i) = 0.99
      // Jika matrix bilang penyakit D_i expects FAIL â†’ P(X=PASS | D_i) = 0.01
      // Jika null (tidak relevan)                    â†’ P(X=PASS | D_i) = 0.50
      const pPassGivenDi = [];
      for(let i = 0; i < highProbIllnesses.length; i++) {
         const ill = highProbIllnesses[i];
         const req = matrixReqs[ill.diagnosis] ? matrixReqs[ill.diagnosis][param] : null;
         
         if(req === "PASS")      pPassGivenDi.push(0.99);
         else if(req === "FAIL") pPassGivenDi.push(0.01);
         else                    pPassGivenDi.push(0.50);
      }
      
      // P(X=PASS) = Î£ P(D_i) Ã— P(X=PASS | D_i)
      let pObsPass = 0;
      for(let i = 0; i < probs.length; i++) {
         pObsPass += probs[i] * pPassGivenDi[i];
      }
      let pObsFail = 1 - pObsPass;
      
      // Guard terhadap edge (0 atau 1)
      if(pObsPass < 0.001) pObsPass = 0.001;
      if(pObsFail < 0.001) pObsFail = 0.001;
      
      // Posterior P(D_i | X=PASS) = P(X=PASS | D_i) Ã— P(D_i) / P(X=PASS)
      // H(D | X=PASS) = -Î£ posterior Ã— log2(posterior)
      let entropyIfPass = 0;
      for(let i = 0; i < probs.length; i++) {
         const post = (pPassGivenDi[i] * probs[i]) / pObsPass;
         if(post > 0 && post < 1) entropyIfPass -= post * (Math.log(post) / Math.log(2));
      }
      
      // Posterior P(D_i | X=FAIL) = P(X=FAIL | D_i) Ã— P(D_i) / P(X=FAIL)
      let entropyIfFail = 0;
      for(let i = 0; i < probs.length; i++) {
         const pFailGivenDi = 1 - pPassGivenDi[i];
         const post = (pFailGivenDi * probs[i]) / pObsFail;
         if(post > 0 && post < 1) entropyIfFail -= post * (Math.log(post) / Math.log(2));
      }
      
      // Expected Entropy setelah observasi
      const expectedEntropy = pObsPass * entropyIfPass + pObsFail * entropyIfFail;
      
      // VOI = pengurangan ketidakpastian
      let infoGain = currentEntropy - expectedEntropy;
      if(infoGain < 0) infoGain = 0; // Floating point guard
      
      // Sensor basi yang tidak relevan ke penyakit top: tetap tampil dgn skor minimum
      if(infoGain === 0 && missingParams.includes(param)) {
         infoGain = 0.01;
      }
      
      if(infoGain > 0) {
         const effCost = Math.max(0.01, cost);
         const voi = infoGain / effCost;
         voiScores.push({
            parameter: param,
            voi_score: voi,
            cost: cost,
            urgency_impact: parseFloat((infoGain * 100).toFixed(1)) // Skala % untuk display
         });
      }
   }
   
   voiScores.sort((a, b) => b.voi_score - a.voi_score);
   return voiScores;
}

// =========================================================================
// FITUR PENYIMPANAN HISTORY KE SPREADSHEET (MIGRASI DARI V1)
// =========================================================================
function _saveDiagnosisHistoryV2(ss, resultObj, snapshot, dataValues) {
  const HISTORY_TAB = "Diagnosis History";
  let sheet = ss.getSheetByName(HISTORY_TAB);
  const paramKeys = snapshot ? Object.keys(snapshot) : [];

  if (!sheet) {
    sheet = ss.insertSheet(HISTORY_TAB);
    const initHeader = ["Timestamp", "Status Sistem", "Penyakit Top 1", "Confidence (%)", "Tindakan Top SOP"].concat(paramKeys);
    sheet.appendRow(initHeader);
    const hRange = sheet.getRange(1, 1, 1, initHeader.length);
    hRange.setFontWeight("bold").setBackground("#1a73e8").setFontColor("#ffffff");
    sheet.setFrozenRows(1);
  }

  const lastCol = sheet.getLastColumn();
  const finalHeaders = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  
  // Make sure new params are appended if rules increased (Like V1 logic, simplified here for speed)
  for(let param of paramKeys) {
      if(!finalHeaders.includes(param)) {
          const nc = sheet.getLastColumn() + 1;
          sheet.getRange(1, nc).setValue(param).setFontWeight("bold").setBackground("#1a73e8").setFontColor("#ffffff");
          finalHeaders.push(param);
      }
  }

  const pad = n => String(n).padStart(2, '0');
  const now = new Date();
  const tsStr = `${pad(now.getDate())}/${pad(now.getMonth()+1)}/${now.getFullYear()} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
  
  let newRow = new Array(finalHeaders.length).fill("");
  newRow[0] = tsStr;
  newRow[1] = resultObj.status;
  
  if(resultObj.status === "NORMAL" || !resultObj.bayesian_ranking || resultObj.bayesian_ranking.length === 0) {
     newRow[2] = "Aman Terkendali";
     newRow[3] = "100%";
     newRow[4] = "Tidak ada tindakan";
  } else {
     const top1 = resultObj.bayesian_ranking[0];
     newRow[2] = top1.diagnosis;
     newRow[3] = top1.confidence;
     newRow[4] = top1.sop ? top1.sop.join(", ") : "-";
  }

  const bgColors = new Array(finalHeaders.length).fill("#ffffff");
  const fontColors = new Array(finalHeaders.length).fill("#000000");

  for (let param in snapshot) {
    const status = snapshot[param];
    const info   = dataValues[param] || {};
    const colIdx = finalHeaders.indexOf(param);
    if (colIdx === -1) continue;

    // Hitung waktu kapan data sensor tersebut dibaca
    const ageMin   = info.ageMin || 0;
    const dataTime = new Date(now.getTime() - ageMin * 60000);
    const timeTag  = `${pad(dataTime.getDate())}/${pad(dataTime.getMonth()+1)}/${dataTime.getFullYear()} ${pad(dataTime.getHours())}:${pad(dataTime.getMinutes())}`;


    // Format: [STATUS] nilai (Real: nilai op Target: threshold) @DD/MM HH:MM
    let cellText = '';
    if (status === 'N/A') {
      const lastVal = (info.value !== null && info.value !== undefined) ? info.value : '?';
      cellText = `[N/A] ${lastVal} (Basi @${timeTag})`;
    } else {
      // Ambil mathStr tapi bersihkan: "(Real: 4 > Target: 6)" â†’ "Real: 4 > Target: 6"
      const detail = info.mathStr ? info.mathStr.replace(/[()]/g, '').trim() : '';
      cellText = `[${status}] ${info.value} ${detail} @${timeTag}`;
    }

    newRow[colIdx] = cellText;

    if (status === 'PASS') {
      bgColors[colIdx] = '#d9ead3'; fontColors[colIdx] = '#274e13';
    } else if (status === 'FAIL') {
      bgColors[colIdx] = '#f4cccc'; fontColors[colIdx] = '#660000';
    } else {
      bgColors[colIdx] = '#efefef'; fontColors[colIdx] = '#666666'; // N/A
    }

  }


  const newRowNum = sheet.getLastRow() + 1;
  const dataRange = sheet.getRange(newRowNum, 1, 1, finalHeaders.length);
  dataRange.setValues([newRow]);
  dataRange.setBackgrounds([bgColors]);
  dataRange.setFontColors([fontColors]);
}

// =========================================================================
// ðŸ“Š SIMPAN DECISION TREE & VOI KE TAB "Tree Diagnosis Result"
// =========================================================================
function _saveTreeResult(ss, payload, evalResult) {
  const TREE_TAB = "Tree Diagnosis Result";
  let sheet = ss.getSheetByName(TREE_TAB);
  if(!sheet) {
    sheet = ss.insertSheet(TREE_TAB);
    sheet.setFrozenRows(1);
  }
  
  const pad = n => String(n).padStart(2,'0');
  const now = new Date();
  const ts = `${pad(now.getDate())}/${pad(now.getMonth()+1)}/${now.getFullYear()} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
  
  // Kolom 1-5: Base Data
  let topDiag = "Skenario Normal", topConf = 100, topLevel = "SAFE";
  if(payload.status !== "NORMAL" && payload.bayesian_ranking && payload.bayesian_ranking.length > 0) {
    const t = payload.bayesian_ranking[0];
    topDiag  = t.diagnosis;
    topConf  = t.confidence;
    topLevel = t.level;
  }
  
  const treeSteps = payload.decision_tree || [];
  const depth = treeSteps.length;
  
  // Array final: [Timestamp, Diagnosa, Conf (%), Depth, Level/Cost, Step 1, Step 2, ...]
  const newRow = [ts, topDiag, topConf, depth, topLevel].concat(treeSteps);
  const rowNum = sheet.getLastRow() + 1;
  
  // Cek dan timpa header agar selalu rapi sesuai jumlah langkah terbanyak
  const currentMaxCols = Math.max(sheet.getLastColumn() || 5, newRow.length);
  const headers = ["Timestamp", "Diagnosa", "Conf (%)", "Depth", "Level/Cost"];
  for(let i=0; i < currentMaxCols - 5; i++) {
     headers.push(`Step ${i+1}`);
  }
  
  // Tulis Header Baru
  sheet.getRange(1, 1, 1, headers.length)
       .setValues([headers])
       .setFontWeight("bold").setBackground("#333").setFontColor("#fff");
       
  // Tulis Data Baru
  sheet.getRange(rowNum, 1, 1, newRow.length).setValues([newRow]);
  
  // Warnai baris sesuai status
  const rowColor = payload.status === "NORMAL" ? "#d9ead3" : (topLevel === "CRITICAL" ? "#f4cccc" : "#fce8b2");
  sheet.getRange(rowNum, 1, 1, newRow.length).setBackground(rowColor);
  
  Logger.log(`[TREE RESULT] Tersimpan baris ${rowNum} â†’ ${topDiag} (${topConf}%) dengan ${depth} Langkah`);

}

// =========================================================================
// ðŸ“„ SIMPAN LAPORAN DIAGNOSA TERFORMAT (= Format WhatsApp) ke "Hasil Diagnosa"
// =========================================================================
function _saveFormattedResult(ss, payload, snapshot, dataValues) {
  const RESULT_TAB = "Hasil Diagnosa";
  let sheet = ss.getSheetByName(RESULT_TAB);
  if(!sheet) sheet = ss.insertSheet(RESULT_TAB);

  // Bersihkan isi lama (selalu tampilkan diagnosa TERBARU)
  sheet.clearContents();
  sheet.clearFormats();
  sheet.setColumnWidth(1, 350);
  sheet.setColumnWidth(2, 350);

  const pad = n => String(n).padStart(2,'0');
  const now = new Date();
  const ts = `${pad(now.getDate())}/${pad(now.getMonth()+1)}/${now.getFullYear()} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
  let row = 1;

  const writeHeader = (text, bg='#1C2541', fg='#ffffff') => {
    sheet.getRange(row, 1, 1, 2).merge().setValue(text)
         .setBackground(bg).setFontColor(fg).setFontWeight('bold').setFontSize(12).setFontFamily('Courier New');
    row++;
  };
  const writeLine = (col1, col2, bg='#ffffff', fg='#000000') => {
    sheet.getRange(row, 1).setValue(col1).setBackground(bg).setFontColor(fg).setFontFamily('Courier New');
    sheet.getRange(row, 2).setValue(col2).setBackground(bg).setFontColor(fg).setFontFamily('Courier New');
    row++;
  };
  const writeMerge = (text, bg='#ffffff', fg='#000000', bold=false) => {
    sheet.getRange(row, 1, 1, 2).merge().setValue(text)
         .setBackground(bg).setFontColor(fg).setFontWeight(bold?'bold':'normal').setFontFamily('Courier New').setWrap(true);
    row++;
  };
  const writeSpacer = () => { sheet.getRange(row, 1, 1, 2).merge().setValue(''); row++; };

  // ==== JUDUL ====
  writeMerge(`ðŸŸ BIOFLOK DIAGNOSTIC RESULT â€” ${ts}`, '#0B132B', '#10B981', true);
  const statusOK = payload.status === 'NORMAL';
  writeMerge(
    statusOK ? 'âœ…  KONDISI AMAN TERKENDALI (Skenario 7)' : 'ðŸš¨  ANOMALI TERDETEKSI',
    statusOK ? '#d9ead3' : '#f4cccc',
    statusOK ? '#274e13' : '#660000', true
  );
  writeSpacer();

  // ==== SECTION 1: JALUR DIAGNOSA ====
  writeHeader('ðŸŒ¿  JALUR DIAGNOSA (Decision Tree)');
  const treeSteps = payload.decision_tree || [];
  if(treeSteps.length > 0) {
    treeSteps.forEach((step, i) => {
      const isPass = step.toUpperCase().includes('PASS');
      const isFail = step.toUpperCase().includes('FAIL');
      const resultLabel = isPass ? 'âœ… PASS' : (isFail ? 'âŒ FAIL' : 'â¬œ N/A');
      const bg = isPass ? '#d9ead3' : (isFail ? '#f4cccc' : '#f3f3f3');
      const fg = isPass ? '#274e13' : (isFail ? '#660000' : '#666666');
      const stepText = step.replace(/â†’.*PASS/i,'â†’').replace(/â†’.*FAIL/i,'â†’').replace(/â†’.*N\/A/i,'â†’').trim();
      writeLine(`Step ${i+1} â–º  ${stepText}`, resultLabel, bg, fg);
    });
  } else {
    writeMerge('(Tidak ada data decision tree)', '#f3f3f3', '#888888');
  }
  writeSpacer();

  // ==== SECTION 2: PROBABILITAS BAYES ====
  writeHeader('ðŸ§®  PROBABILITAS KECOCOKAN (Bayesian)');
  const ranking = payload.bayesian_ranking || [];
  if(!statusOK && ranking.length > 0) {
    ranking.forEach((b, i) => {
      const conf = b.confidence || 0;
      const filled = Math.round(conf / 10);
      const bar = 'â–ˆ'.repeat(filled) + 'â–‘'.repeat(10 - filled);
      const bgCard = i === 0 ? '#c9daf8' : (i === 1 ? '#d9ead3' : '#f8f9fa');
      const badge = i === 0 ? ' â† TOP' : '';
      writeMerge(`${i+1}. ${b.diagnosis.toUpperCase()}${badge}`, bgCard, '#000000', true);
      sheet.getRange(row-1, 2).setValue(`${bar} ${conf}%`).setFontWeight('bold').setFontFamily('Courier New').setBackground(bgCard);
      const allParams = Object.keys(snapshot || {});
      const missedSet = new Set(b.missed_rules || []);
      const matchedList = allParams.filter(k => !missedSet.has(k) && snapshot[k] !== undefined).join(', ') || '-';
      const missedList = (b.missed_rules || []).join(', ') || '-';
      writeLine('   ðŸŸ¢ Data Tersedia (MATCH):', matchedList, '#e6f4ea', '#274e13');
      writeLine('   ðŸ”´ Data Kosong / N/A:', missedList, '#fce8e6', '#7f0000');
      writeSpacer();
    });
  } else if(statusOK) {
    writeMerge('âœ… Tidak ada penyakit yang terdeteksi.', '#d9ead3', '#274e13');
    writeSpacer();
  } else {
    writeMerge('(Tidak ada data Bayesian â€” pastikan Matrix Diagnosis sudah terisi)', '#f3f3f3', '#888888');
    writeSpacer();
  }


  // ==== SECTION 3: KESIMPULAN FINAL ====
  writeHeader('ðŸŽ¯  KESIMPULAN FINAL');
  if(statusOK) {
    writeMerge('Semua sensor dalam batas aman.\nðŸ‘‰ Tambak terkendali. Lanjutkan monitoring.', '#d9ead3', '#274e13', true);
  } else if(ranking.length > 0) {
    const top = ranking[0];
    writeMerge(
      `Kedua engine (Tree & Bayes) sepakat menunjuk:\nðŸ‘‰ ${top.diagnosis.toUpperCase()}  (${top.confidence}%)`,
      '#c9daf8', '#1a237e', true
    );
    writeSpacer();

    // ==== SECTION 4: TINDAKAN DARURAT ====
    writeHeader('ðŸ“‹  TINDAKAN DARURAT');
    const levelBg = (top.level||'').toUpperCase() === 'CRITICAL' ? '#f4cccc' : '#fce8b2';
    const levelFg = (top.level||'').toUpperCase() === 'CRITICAL' ? '#660000' : '#7f4c00';
    writeMerge(`âš¡ Level: ${top.level || 'WARNING'} (respons secepatnya!)`, levelBg, levelFg, true);
    if(top.sop && top.sop.length > 0) {
      top.sop.forEach((s, i) => {
        writeMerge(`${i+1}. ðŸ”¹ ${s}`, i%2===0 ? '#fff3e0' : '#fffde7', '#000000');
      });
    } else {
      writeMerge('(SOP belum diisi di tab SOP Tindakan)', '#f3f3f3', '#888888');
    }
    writeSpacer();

    // ==== SECTION 5: SENSOR WARNINGS ====
    if((payload.sensor_warnings||[]).length > 0) {
      writeHeader('âš ï¸  SENSOR MATI / DATA BASI');
      (payload.sensor_warnings||[]).forEach(w => writeMerge(w, '#fff2cc', '#7f4c00'));
      writeSpacer();
    }

    // ==== SECTION 6: VOI ====
    const voi = payload.voi_recommendation || [];
    if(voi.length > 0) {
      writeHeader('ðŸ”¬  REKOMENDASI TES BERIKUTNYA (Value of Information)');
      voi.forEach(v => {
        writeMerge(
          `#${v.priority_rank} â†’ Ukur ${v.parameter}  (Dampak: ${v.urgency_impact}%, Gain: ${v.information_gain_score})`,
          v.priority_rank === 1 ? '#e8d5f5' : '#f5e8ff', '#37006e'
        );
      });
      writeSpacer();
    }
  }

  // Footer
  writeMerge(`Ketik *jelaskan* â†’ analisa AI lebih lanjut\nKetik *tes berikutnya* â†’ cek sensor mana yang perlu diukur`, '#efefef', '#666666');

  Logger.log(`[FORMATTED RESULT] Tab "${RESULT_TAB}" selesai diperbarui.`);
}

// =========================================================================
// ðŸš€ THE MASTER TRIGGER: EXECUTE ALL PILLARS 
// =========================================================================
function runCombinedDiagnosis(calledViaScript = false) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const config = _getConfig(ss);
  
  Logger.log("================= DIAGNOSIS STARTED =================");
  Logger.log("âœ… Starting Pintu 1: Sensor & Alarm Checks");
  const alarmCheck = _checkSensorAlarms(ss, config);
  const rawDataCache = alarmCheck.rawDataCache; // Re-use fetched values
  
  const rules = _fetchRules(ss);
  // Prepare a pre-evaluation step
  const evalResult = _evaluateRules(ss, rules, config, rawDataCache);
  
  // Jika Pintu 1 Aman, TIDAK ADA yang anomali, batalkan diagnosis penyakit
  if(alarmCheck.isSafe) {
     const resJson = {
         status: "NORMAL",
         msg: "Skenario 7: Kolam Aman Terkendali. Semua sensor dalam rentang normal.",
         alarms: [],
         sensor_warnings: [],
         decision_tree: [],
         bayesian_ranking: [],
         voi_recommendation: [],
         evaluated_data: Object.keys(evalResult.dataValues).map(k => ({
             parameter: k,
             keyword: evalResult.paramToKeyword[k] || k,
             status: evalResult.dataValues[k].status,
             value: evalResult.dataValues[k].value,
             desc: evalResult.dataValues[k].desc,
             ageMin: evalResult.dataValues[k].ageMin
         }))
     };
     
     _saveTreeResult(ss, resJson, evalResult);
     _saveDiagnosisHistoryV2(ss, resJson, evalResult.snapshot, evalResult.dataValues);
     _saveFormattedResult(ss, resJson, evalResult.snapshot, evalResult.dataValues);
     Logger.log('Skenario 7: Safe.');
     return resJson;
  }
  
  // ── DETEKSI OFFLINE ──
   // Jika SEMUA data bernilai N/A (Basi / Kosong)
   let isOffline = false;
   if(evalResult.missingParams.length >= rules.length && rules.length > 0) {
       isOffline = true;
       Logger.log("Sistem OFFLINE: Semua data basi / kosong. Tetap mengurutkan prior-based VOI.");
   }
  
  Logger.log(`âš ï¸ Anomali terdeteksi! Tembok Pintu 1 Jebol (${alarmCheck.alarms.length} Alarms). Memasuki Mesin Tree & Bayes (Pintu 2)...`);
  
  const matrixData = ss.getSheetByName("Matrix Diagnosis").getDataRange().getValues();
  const sopMap = _fetchSOPMatrix(ss);
  
  // Pilar 2: Hitung Persentase Probabilitas Matematis
  const bayesRank = _calculateBayesianScore(evalResult.snapshot, matrixData, config, sopMap);
  
  // Pilar 3: Kalkulus Prioritas Parameter tersumbat (N/A) + panduan cek manual
  const voiPriorities    = _calculateEntropyVOI(bayesRank, matrixData, evalResult.missingParams);
  const manualCheckGuide = _fetchManualCheckGuide(ss); // Panduan cara cek dari SOP Tindakan
  
  // Pilar 3.5: True Decision Tree Traversal (identik dgn diagnostic_optimizer.html)
  const treeData = getMatrixForTree(ss);
  const featureIdxs = [];
  for(let i=0; i<treeData.headers.length; i++) {
     featureIdxs.push(i);
  }
  const diagTree = buildDiagnosisTree(treeData.items, featureIdxs, treeData.headerPairs, treeData.headers, treeData.costs, config.algo_mode || "eff", 0, 0, []);
  const treeResult = traverseTree(diagTree, evalResult);
  const treeLog = treeResult.path;

  
  // Package JSON Payload (Top 5 Diagnosa)
  const payload = {
     timestamp: new Date().toISOString(),
     status: isOffline ? "OFFLINE" : "ANOMALY",
      msg: isOffline ? "Sistem offline (data sensor basi). Input pengukuran manual via Form VOI di bawah." : "Diagnosis Complete",
     alarms: alarmCheck.alarms,
     sensor_warnings: alarmCheck.sensorWarnings,
     evaluated_data: Object.keys(evalResult.dataValues).map(k => ({
         parameter: k,
         keyword: evalResult.paramToKeyword[k] || k,
         status: evalResult.dataValues[k].status,
         value: evalResult.dataValues[k].value,
         desc: evalResult.dataValues[k].desc,
         ageMin: evalResult.dataValues[k].ageMin
     })),
     decision_tree: isOffline ? [] : treeLog,
      bayesian_ranking: isOffline ? [] : bayesRank.filter(b => b.final_score > 0).slice(0, 5).map(b => {
         return {
             diagnosis: b.diagnosis,
             confidence: parseFloat(b.final_score.toFixed(1)),
             level: b.level,
             sop: b.sopList,
             matched_params: b.matchedParams || [],    // ðŸ”¥ Benar-benar COCOK dgn matrix
             mismatched_params: b.mismatchedParams || [], // âŒ Data ada tapi BEDA dgn matrix
             missed_rules: b.missedData || [],         // âšª Data Kosong / N/A
             req_map: b.reqMap || {}                   // ðŸ“‹ Parameter requirement definitions
         };
     }),

     // â”€â”€ VOI: Deduplikasi berdasarkan Keyword â”€â”€
     // "Low pH" dan "High pH" â†’ sama-sama keyword "pH", cukup tampil 1x "Ukur pH"
     voi_recommendation: (function() {
         const grouped = {};
         voiPriorities.forEach(function(v) {
             const kw = evalResult.paramToKeyword[v.parameter] || v.parameter;
             if(!grouped[kw]) {
                grouped[kw] = {
                   parameters: [],
                   keyword: kw,
                   voi_score: 0,
                   urgency_impact: 0,
                   cost: 0,
                   cara_cek: manualCheckGuide[kw] || manualCheckGuide[v.parameter] || ''
                };
             }
             grouped[kw].parameters.push(v.parameter);
             grouped[kw].voi_score = Math.max(grouped[kw].voi_score, v.voi_score);
             grouped[kw].urgency_impact = Math.max(grouped[kw].urgency_impact, v.urgency_impact);
             grouped[kw].cost = Math.max(grouped[kw].cost, v.cost);
         });
         return Object.values(grouped)
           .sort(function(a,b) { return b.voi_score - a.voi_score; })
           .slice(0, 3)
           .map(function(g, i) {
              return {
                 priority_rank: i + 1,
                 parameter: g.parameters[0],
                 keyword: g.keyword,
                 information_gain_score: parseFloat(g.voi_score.toFixed(2)),
                 urgency_impact: parseFloat(g.urgency_impact.toFixed(1)),
                 cara_cek: g.cara_cek
              };
           });
     })()
  };
  
  // Simpan history dan Hasil Diagnosa (Format WA)
  _saveTreeResult(ss, payload, evalResult);
  _saveDiagnosisHistoryV2(ss, payload, evalResult.snapshot, evalResult.dataValues);
  _saveFormattedResult(ss, payload, evalResult.snapshot, evalResult.dataValues);

  
  // TRIGGER PYTHON WEBHOOK IF (a) Called via Cronjob / script explicitly AND (b) URL is set
  if(calledViaScript && config.python_webhook_url && config.python_webhook_url.startsWith("http")) {
      Logger.log(`Tembak Webhook ke Python Ngrok: ${config.python_webhook_url}`);
      try {
        UrlFetchApp.fetch(config.python_webhook_url, {
           method: "post",
           contentType: "application/json",
           payload: JSON.stringify(payload)
        });
      } catch(e) {
        Logger.log("âŒ Gagal mengirim webhook ke Python: " + e.message);
      }
  }
  
  Logger.log("\n====== FINAL JSON PAYLOAD ======\n" + JSON.stringify(payload, null, 2));
  return payload; // Send native JS object back to UI or webhook Endpoint
}

// -------------------------------------------------------------
// TRIGGER UNTUK CRONJOB OTOMATIS (TIME-DRIVEN)
// Dijalankan setiap 30 menit (Sesuai settingan Google Trigger nantinya)
// -------------------------------------------------------------
function MUNCUL_CRONJOB_30_MENIT() {
   // Memberikan parameter True berarti ia memperbolehkan "Push Notification" ke Python Webhook
   runCombinedDiagnosis(true);
}

// -------------------------------------------------------------
// ENDPOINT UNTUK HTTP GET / POST (Dipanggil dari PYTHON Chatbot)
// Mengembalikan data mentah berbentuk string JSON
// -------------------------------------------------------------
function doGet(e) {
  const result = runCombinedDiagnosis(false); // False krn python sedang memanggil, tak perlu tembak balik webhook
  return ContentService.createTextOutput(JSON.stringify(result)).setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  const result = runCombinedDiagnosis(false);
  return ContentService.createTextOutput(JSON.stringify(result)).setMimeType(ContentService.MimeType.JSON);
}

/**
 * ðŸŽ¨ Dipanggil terpisah dari HTML Menu "Lihat Peta Pohon Keputusan"
 */
function getMermaidTreeData() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const config = _getConfig(ss);
  
  // Ambil struktur tree
  const treeData = getMatrixForTree(ss);
  const rules = _fetchRules(ss); // Ambil rule untuk cocokin key aktif
  
  const ruleParams = rules.map(r => r.param);
  const featureIdxs = [];
  for(let i=0; i<treeData.headers.length; i++) {
     featureIdxs.push(i);
  }
  
  const diagTree = buildDiagnosisTree(treeData.items, featureIdxs, treeData.headerPairs, treeData.headers, treeData.costs, config.algo_mode || "eff", 0, 0, []);
  
  return exportTreeToMermaid(diagTree);
}

/**
 * ðŸŽ¨ Mentransmisikan Data Mentah Spreadsheet ke UI HTML/CSS Klien Custom
 */
function getVisualTreeDataJSON() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const config = _getConfig(ss);
  
  const treeData = getMatrixForTree(ss);
  if(!treeData) return JSON.stringify({ error: "No Matrix Data" });
  
  return JSON.stringify({
    headers: treeData.headers,
    costs: treeData.costs,
    matrix: treeData.items,
    config: config
  });
}
