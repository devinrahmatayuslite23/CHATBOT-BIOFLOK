/**
 * ------------------------------------------------------------------------
 * 🛠️ MENU UTAMA GOOGLE SHEETS (CENTRAL HUB)
 * ------------------------------------------------------------------------
 * File ini bertindak sebagai pusat pembuatan Menu UI pada Google Sheets.
 * Seluruh tombol dari berbagai file GS yang berbeda (Rule2Matrix, FCR, Simulator)
 * digabungkan dan dipanggil di sini agar tidak terjadi bentrok 'onOpen()'.
 */

function onOpen() {
  const ui = SpreadsheetApp.getUi();
  
  // -------------------------------------------------------------
  // SATU MENU SENTRAL: 🐟 BIOFLOK SYSTEM
  // -------------------------------------------------------------
  ui.createMenu('🐟 BIOFLOK SYSTEM')
  
      // SECTION 1: DASHBOARD & REPORTING
      .addItem('📊 Buka Dashboard Pakan & FCR', 'openFcrDashboardUI')
      .addItem('🔄 Sync Data (Tarik Laporan Terakhir)', 'syncDataDariBot')
      
      .addSeparator()
      
      // SECTION 2: DIAGNOSA & AI
      .addItem('▶️ Jalankan Diagnosa Manual (Test)', 'testManualDiagnosis')
      .addItem('🌳 Lihat Peta Pohon Keputusan (Visual)', 'showTreeVisualizer')
      .addItem('💻 Buka Layar AI Simulator', 'openSimulatorUI')
      
      .addSeparator()
      
      // SECTION 3: DATABASE & PENGATURAN
      .addItem('🗃️ Buka Database Manager (Matrix)', 'openDatabaseManager') 
      .addItem('📥 Tarik Import Matrix ke Rules', 'syncRulesFromMatrix')
      .addItem('📤 Tembakan Data Rules ke Matrix', 'syncMatrixFromRules')
      .addItem('🔧 Segarkan Semua Dropdown', 'refreshAllDropdowns')
      .addItem('🔗 Setup Keyword 2 & 3 dari Tab Logic', 'setupKeyword2Dropdowns')
      .addItem('🏷️ Pasang Header Kolom Logic (G-O)', 'setupLogicHeaders')
      .addItem('🪄 Buat Template "FCR TRACKER"', 'generateMasterTemplate')
      .addItem('🔁 Sinkronisasi Header Diagnosis History', 'rebuildHistoryHeaders')
      .addItem('🗑️ Reset & Rebuild Diagnosis History', 'resetHistoryTab')
      
      .addToUi();
}

/**
 * ⚡ Test Manual Diagnosa — Buka HTML Popup bergaya WA
 */
function testManualDiagnosis() {
  const ui = SpreadsheetApp.getUi();
  try {
    runDiagnosisAndStore(); // Jalankan diagnosa, simpan result ke ScriptProperties
    const html = HtmlService.createHtmlOutputFromFile('DiagnosisPopup')
      .setWidth(780).setHeight(750)
      .setTitle('🐟 BIOFLOK Diagnostic Result');
    ui.showModalDialog(html, '🐟 BIOFLOK Diagnostic Result');
  } catch (e) {
    ui.alert("❌ Error saat Diagnosa:\n" + e.message);
  }
}

/**
 * 🌳 Buka Pop-up HTML untuk me-render Canvas Tree Mermaid
 */
function showTreeVisualizer() {
  const ui = SpreadsheetApp.getUi();
  const html = HtmlService.createHtmlOutputFromFile('TreeVisualPopup')
    .setWidth(1400).setHeight(850);
  ui.showModalDialog(html, '🌳 Peta Pohon AI Premium (Optimizer Visualizer)');
}

/**
 * Jalankan diagnosa & simpan hasilnya ke ScriptProperties
 * Dipanggil dari HTML popup via google.script.run
 */
function runDiagnosisAndStore() {
  const result = runCombinedDiagnosis(false);
  PropertiesService.getScriptProperties()
    .setProperty('latest_diagnosis_result', JSON.stringify(result));
  return result;
}

/**
 * Ambil hasil diagnosa terakhir yang tersimpan
 * Dipanggil dari HTML popup via google.script.run
 */
function getStoredDiagnosisResult() {
  const json = PropertiesService.getScriptProperties()
    .getProperty('latest_diagnosis_result');
  if (!json) return runDiagnosisAndStore(); // fallback kalau belum ada
  return JSON.parse(json);
}

/**
 * Simpan nilai VOI yang diinput user ke tab sumber data.
 * Strategi: COPY baris terakhir yang ada, UPDATE kolom target, lalu APPEND.
 * Ini mencegah baris kosong yang merusak pembacaan sensor lain.
 */
function submitVoiFeedback(paramName, value) {
  const ss      = SpreadsheetApp.getActiveSpreadsheet();
  const rules   = _fetchRules(ss);

  // Cari rule yang cocok
  const rule = rules.find(r => r.param === paramName || r.keyword === paramName);
  if (!rule) throw new Error(`Parameter "${paramName}" tidak ditemukan di Diagnosis_Rules.`);

  const tabName = rule.tab_source;
  const keyword = rule.keyword;

  if (!tabName || tabName === 'undefined') {
    throw new Error(`Tab sumber untuk "${paramName}" belum diisi di Diagnosis_Rules (kolom C).`);
  }

  const sheet = ss.getSheetByName(tabName);
  if (!sheet) throw new Error(`Tab "${tabName}" tidak ditemukan di Spreadsheet.`);

  const lastRow  = sheet.getLastRow();
  const lastCol  = sheet.getLastColumn();
  if (lastCol < 1) throw new Error(`Tab "${tabName}" kosong.`);
  const headers  = sheet.getRange(1, 1, 1, lastCol).getValues()[0];

  // Cari colIdx untuk keyword (same logic as _fetchLatestValue)
  const keyLower = keyword.toLowerCase().trim();
  let colIdx = -1;
  let tsColIdx = 0;
  for (let i = 0; i < headers.length; i++) {
    const h = headers[i].toString().toLowerCase().trim();
    if (h === keyLower) colIdx = i;
    if (h.includes('time') || h.includes('stamp') || h.includes('waktu')) tsColIdx = i;
  }

  if (colIdx < 0) {
    throw new Error(`Kolom header "${keyword}" tidak ditemukan di tab "${tabName}". Cek ejaan di Diagnosis_Rules kolom B.`);
  }

  // ✅ Ambil baris terakhir yang ada (copy seluruh nilainya)
  let baseRow;
  if (lastRow >= 2) {
    baseRow = sheet.getRange(lastRow, 1, 1, lastCol).getValues()[0];
  } else {
    baseRow = new Array(lastCol).fill('');
  }

  // ✅ Buat baris baru = salinan baris terakhir + update kolom target + update timestamp
  const newRow = baseRow.slice(); // copy
  newRow[tsColIdx] = new Date(); // timestamp terbaru
  newRow[colIdx]   = value;      // nilai VOI yang diinput user

  sheet.appendRow(newRow);
  Logger.log(`[VOI FEEDBACK] ${paramName} = "${value}" → ${tabName}[${keyword}] (colIdx=${colIdx})`);
  return true;
}


/**
 * 🔁 Rebuild / Sinkronisasi Header Kolom di Diagnosis History
 */

function rebuildHistoryHeaders() {
  const ui = SpreadsheetApp.getUi();
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const HISTORY_TAB = "Diagnosis History";
  const sheet = ss.getSheetByName(HISTORY_TAB);
  if (!sheet) {
    ui.alert("Tab 'Diagnosis History' belum ada. Jalankan Diagnosa Manual dulu.");
    return;
  }

  const rules = _fetchRules(ss);
  if (!rules || rules.length === 0) {
    ui.alert("Tidak ada data Rules yang ditemukan.");
    return;
  }

  const newParamKeys = rules.map(r => r.param);
  const lastCol = sheet.getLastColumn();
  const existingHeaders = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  const FIXED_COLS = 5;
  const oldRuleCols = existingHeaders.slice(FIXED_COLS);

  let changed = 0;
  for (let i = 0; i < Math.min(oldRuleCols.length, newParamKeys.length); i++) {
    if (oldRuleCols[i] !== newParamKeys[i]) {
      sheet.getRange(1, FIXED_COLS + 1 + i).setValue(newParamKeys[i]);
      changed++;
    }
  }

  for (let i = oldRuleCols.length; i < newParamKeys.length; i++) {
    const newCol = sheet.getLastColumn() + 1;
    sheet.getRange(1, newCol).setValue(newParamKeys[i])
      .setFontWeight("bold").setBackground("#1a73e8").setFontColor("#ffffff");
  }

  ui.alert(
    "✅ Header Berhasil Disinkronisasi!",
    `${changed} kolom berhasil diperbarui namanya.\n\nSekarang header sudah sesuai dengan Diagnosis_Rules terbaru.`,
    ui.ButtonSet.OK
  );
}

/**
 * 🗑️ Reset & Rebuild Diagnosis History
 */
function resetHistoryTab() {
  const ui = SpreadsheetApp.getUi();
  const confirm = ui.alert(
    '🗑️ Reset Tab Diagnosis History?',
    'Semua data history lama akan DIHAPUS dan tab dibuat ulang dari awal.\n\nLanjutkan?',
    ui.ButtonSet.YES_NO
  );
  if (confirm !== ui.Button.YES) return;

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const HISTORY_TAB = 'Diagnosis History';
  const oldSheet = ss.getSheetByName(HISTORY_TAB);
  if (oldSheet) ss.deleteSheet(oldSheet);

  try {
    runCombinedDiagnosis(false);
    ui.alert('✅ Berhasil!', "Tab 'Diagnosis History' sekarang sudah dibuat ulang dan menyesuaikan Arsitektur baru.", ui.ButtonSet.OK);
  } catch (e) {
    ui.alert('❌ Error saat rebuild: ' + e.message);
  }
}

/**
 * Setup dropdown Keyword 2 (Kolom G) dari Tab 2 (Kolom H) dan Keyword 3 (Kolom L) dari Tab 3 (Kolom M).
 * Jalankan dari menu setelah mengisi Kolom H (Tab 2).
 */
function setupKeyword2Dropdowns() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const r = ss.getSheetByName("Diagnosis_Rules");
  if (!r) return;

  const lastRow = r.getLastRow();
  if (lastRow < 2) return;

  let updated = 0;

  for (let row = 2; row <= lastRow; row++) {
    const tab2 = r.getRange(row, 8).getValue().toString().trim();
    if (tab2) {
      const tSheet = ss.getSheetByName(tab2);
      if (tSheet) {
        const headers = tSheet.getRange(1, 1, 1, tSheet.getLastColumn() || 1).getValues()[0].filter(h => h !== "");
        if (headers.length > 0) {
          r.getRange(row, 7).setDataValidation(
            SpreadsheetApp.newDataValidation().requireValueInList(headers, true).build()
          );
          updated++;
        }
      }
    }

    const tab3 = r.getRange(row, 13).getValue().toString().trim();
    if (tab3) {
      const tSheet3 = ss.getSheetByName(tab3);
      if (tSheet3) {
        const headers3 = tSheet3.getRange(1, 1, 1, tSheet3.getLastColumn() || 1).getValues()[0].filter(h => h !== "");
        if (headers3.length > 0) {
          r.getRange(row, 12).setDataValidation(
            SpreadsheetApp.newDataValidation().requireValueInList(headers3, true).build()
          );
          updated++;
        }
      }
    }
  }

  SpreadsheetApp.getActive().toast(`✅ ${updated} dropdown Keyword berhasil diperbarui!`, "Setup Selesai", 4);
}
