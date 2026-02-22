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
  // 1. MENU: DIAGNOSA MATRIX (Dari file Rule2Matrix.gs)
  // -------------------------------------------------------------
  ui.createMenu('⚙️ Sync Diagnosa')
      .addItem('🗃️ Buka Database Manager', 'openDatabaseManager') 
      .addSeparator() 
      .addItem('📥 Tarik Import Matrix ke Rules', 'syncRulesFromMatrix')
      .addItem('📤 Tembakan Data Rules ke Matrix', 'syncMatrixFromRules')
      .addItem('🔧 Segarkan Semua Dropdown', 'refreshAllDropdowns')
      .addToUi();

  // -------------------------------------------------------------
  // 2. MENU: SIMULATOR AI (Dari file Simulator.gs)
  // -------------------------------------------------------------
  ui.createMenu('🧪 AI Simulator')
      .addItem('💻 Buka Layar Simulasi Mapped', 'openSimulatorUI')
      .addToUi();
      
  // -------------------------------------------------------------
  // 3. MENU: DASHBOARD FCR (Dari file FCR_Dashboard.gs)
  // -------------------------------------------------------------
  ui.createMenu('🐟 BIOFLOK SYSTEM')
      .addItem('📊 Buka Dashboard Pakan & FCR', 'openFcrDashboardUI')
      .addSeparator()
      .addItem('🔄 Sync Data (Tarik Data Bot Laporan Terakhir)', 'syncDataDariBot')
      .addSeparator()
      .addItem('🪄 BUAT TEMPLATE "FCR TRACKER"', 'generateMasterTemplate')
      .addToUi();
}
