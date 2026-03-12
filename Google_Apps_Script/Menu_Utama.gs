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
      .addItem('💻 Buka Layar AI Simulator', 'openSimulatorUI')
      
      .addSeparator()
      
      // SECTION 3: DATABASE & PENGATURAN
      .addItem('🗃️ Buka Database Manager (Matrix)', 'openDatabaseManager') 
      .addItem('📥 Tarik Import Matrix ke Rules', 'syncRulesFromMatrix')
      .addItem('📤 Tembakan Data Rules ke Matrix', 'syncMatrixFromRules')
      .addItem('🔧 Segarkan Semua Dropdown', 'refreshAllDropdowns')
      .addItem('🪄 Buat Template "FCR TRACKER"', 'generateMasterTemplate')
      .addItem('🔁 Sinkronisasi Header Diagnosis History', 'rebuildHistoryHeaders')
      .addItem('🗑️ Reset & Rebuild Diagnosis History', 'resetHistoryTab')
      
      .addToUi();
}

/**
 * ⚡ Fungsi Wrapper untuk Test Manual Diagnosa dari Menu
 */
function testManualDiagnosis() {
  const ui = SpreadsheetApp.getUi();
  try {
    const result = runAutoDiagnosis();
    if (result) {
      ui.alert(
        "🚨 Diagnosa Selesai!",
        "Hasil Utama: " + result.topDiag.diagnosis + " (" + result.topDiag.final_score.toFixed(2) + "%)\n\n" +
        "Catatan sudah ditambahkan ke tab 'Diagnosis History'.",
        ui.ButtonSet.OK
      );
    } else {
      ui.alert(
        "✅ Diagnosa Selesai!",
        "Kondisi Normal. Tidak ada masalah krusial yang terdeteksi.\n\n" +
        "Catatan sudah ditambahkan ke tab 'Diagnosis History'.",
        ui.ButtonSet.OK
      );
    }
  } catch (e) {
    ui.alert("❌ Terjadi Error saat Test Manual:\n" + e.message);
  }
}
/**
 * 🔁 Rebuild / Sinkronisasi Header Kolom di Diagnosis History
 * Gunakan ini setelah mengganti nama parameter di Diagnosis_Rules.
 * Header kolom rule lama akan disesuaikan dengan yang terbaru (berdasarkan urutan).
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

  // Baca rules terbaru
  const rules = _fetchRules(ss);
  if (!rules || rules.length === 0) {
    ui.alert("Tidak ada data Rules yang ditemukan.");
    return;
  }

  const newParamKeys = rules.map(r => r.param);

  // Baca header yang ada
  const lastCol = sheet.getLastColumn();
  const existingHeaders = sheet.getRange(1, 1, 1, lastCol).getValues()[0];

  // Kolom fixed: [0]Timestamp [1]Diagnosa [2]Prob [3]Match [4]KemungkinanLain
  // Kolom rule mulai dari index 5
  const FIXED_COLS = 5;
  const oldRuleCols = existingHeaders.slice(FIXED_COLS); // kolom rule yang ada

  // Sinkronisasi: jika jumlah sama → rename kolom lama ke nama baru
  // Jika ada kolom extra → biarkan (data lama)
  let changed = 0;
  for (let i = 0; i < Math.min(oldRuleCols.length, newParamKeys.length); i++) {
    if (oldRuleCols[i] !== newParamKeys[i]) {
      sheet.getRange(1, FIXED_COLS + 1 + i).setValue(newParamKeys[i]);
      changed++;
    }
  }

  // Tambahkan kolom baru jika rules lebih banyak dari sebelumnya
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
 * Hapus tab lama dan buat ulang dari scratch berdasarkan Diagnosis_Rules terkini.
 * Kolom header akan sinkron 100% dengan Matrix Diagnosis kamu.
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
    runAutoDiagnosis();
    ui.alert('✅ Berhasil!', "Tab 'Diagnosis History' sekarang sudah sinkron dengan Diagnosis_Rules terkini.", ui.ButtonSet.OK);
  } catch (e) {
    ui.alert('❌ Error saat rebuild: ' + e.message);
  }
}

