/**
 * =========================================================================
 * ⚙️ FCR DASHBOARD HYBRID (1-TAB MASTER + BACA DARI TAB MENTAH PYTHON)
 * =========================================================================
 * Script ini menggabungkan 3 Tab Pangan jadi 1 (FCR Tracker), TETAPI
 * tetap mengambil data mentah kematian & bobot dari tab "Bio - Dead Fish"
 * dan "Sampling" buatan Bot Python Anda.
 */

const TAB_MASTER = "FCR Tracker";
const TAB_MATI = "Bio - Dead Fish";
const TAB_SAMPLING = "Sampling";



/**
 * =========================================================================
 * 1. FUNGSI SINKRONISASI (Menarik Data dari Wilayah Python)
 * =========================================================================
 * Fungsi ini yang mengintip "Tab Dead Fish" & "Sampling" lalu memasukannya
 * ke Papan Tulis / Tab FCR Tracker agar Rumus Excel jalan.
 */
function syncDataDariBot() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetMaster = ss.getSheetByName(TAB_MASTER);
  const sheetMati = ss.getSheetByName(TAB_MATI);
  const sheetSampling = ss.getSheetByName(TAB_SAMPLING);
  
  if (!sheetMaster) {
      SpreadsheetApp.getUi().alert("Buat Template FCR Tracker dulu!");
      return;
  }
  
  // Ambil Tanggal Tebar Awal sebagai Acuan Minggu (Disimpan di Cell G1)
  const tglTebarVal = sheetMaster.getRange("G1").getValue();
  if (!tglTebarVal || !(tglTebarVal instanceof Date)) {
      SpreadsheetApp.getUi().alert("Harap isi 'Tanggal Tebar' di Sel G1 (Tab FCR Tracker) dengan format kalender yang benar agar sistem bisa menghitung umur berdasar minggu.");
      return;
  }
  const tglTebar = new Date(tglTebarVal).getTime();
  
  // --- A. OLAH DATA KEMATIAN DARI PYTHON ---
  let rekapMatiPerMinggu = {}; // Format: { 1: 50, 2: 10, ... }
  if (sheetMati) {
     const dataMati = sheetMati.getDataRange().getValues();
     for (let i = 1; i < dataMati.length; i++) { // Baris 1 biasanya Headers
        let tgl = new Date(dataMati[i][0]).getTime(); // Asumsi kolom A = Timestamp
        let count = parseFloat(dataMati[i][2]); // Asumsi kolom C = Count Mati
        if (tgl && !isNaN(count)) {
           // Hitung ini masuk minggu ke berapa sejak tebar
           let selisihHari = (tgl - tglTebar) / (1000 * 3600 * 24);
           let mingguKe = Math.floor(selisihHari / 7) + 1;
           if (mingguKe < 1) mingguKe = 1;
           
           if (!rekapMatiPerMinggu[mingguKe]) rekapMatiPerMinggu[mingguKe] = 0;
           rekapMatiPerMinggu[mingguKe] += count;
        }
     }
  }

  // --- B. OLAH DATA SAMPLING BERAT DARI PYTHON ---
  let rekapBeratPerMinggu = {}; // Format: { 1: 15.9, 2: 21.5, ... } (Ambil yg terbaru tiap mgg)
  if (sheetSampling) {
     const dataSampling = sheetSampling.getDataRange().getValues();
     for (let i = 1; i < dataSampling.length; i++) {
        let tgl = new Date(dataSampling[i][0]).getTime(); // Asumsi kolom A = Timestamp
        let berat = parseFloat(dataSampling[i][2]); // Asumsi kolom C = Avg Weight
        if (tgl && !isNaN(berat)) {
           let selisihHari = (tgl - tglTebar) / (1000 * 3600 * 24);
           let mingguKe = Math.floor(selisihHari / 7) + 1;
           if (mingguKe < 1) mingguKe = 1;
           
           // Kita selalu ambil update berat *terakhir/terbesar* di minggu tersebut
           rekapBeratPerMinggu[mingguKe] = berat;
        }
     }
  }

  // --- C. MASUKKAN HASIL REKAP KE TAB FCR TRACKER ---
  // Loop baris FCR Tracker (Baris 8 sampai 23)
  for (let i = 8; i <= 23; i++) {
     let m = sheetMaster.getRange(i, 1).getValue(); // Kolom A = Minggu Ke
     if (typeof m !== 'number') continue;
     
     // Jika ada data mati di minggu 'm' ini, tulis di Kolom E
     if (rekapMatiPerMinggu[m] !== undefined) {
         sheetMaster.getRange(i, 5).setValue(rekapMatiPerMinggu[m]);
     }
     // Jika ada data sampling berat di minggu 'm' ini, tulis di Kolom B
     if (rekapBeratPerMinggu[m] !== undefined) {
         sheetMaster.getRange(i, 2).setValue(rekapBeratPerMinggu[m]);
     }
  }
  
  // UI Pemberitahuan jika dipanggil manual
  SpreadsheetApp.getActiveSpreadsheet().toast("Data Mati & Sampling dari Python berhasil disinkronkan ke FCR Tracker!", "Sinkronisasi Sukses", 3);
}


/**
 * =========================================================================
 * 2. FUNGSI PEMBUAT TEMPLATE (FORMAT KLIEN C-16)
 * =========================================================================
 */
function generateMasterTemplate() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(TAB_MASTER);
  if (sheet) {
    const ui = SpreadsheetApp.getUi();
    const res = ui.alert("Warning", "Tab 'FCR Tracker' sudah ada! Diteruskan akan me-RESET tabel lama. Yakin?", ui.ButtonSet.YES_NO);
    if (res !== ui.Button.YES) return;
    ss.deleteSheet(sheet);
  }
  
  sheet = ss.insertSheet(TAB_MASTER);
  
  // HEADER ATAS
  sheet.getRange("A1").setValue("Cara Menghitung Kebutuhan Pakan Ikan Nila Dalam Satu Siklus").setFontSize(14).setFontWeight("bold");
  sheet.getRange("A2:A6").setValues([["Padat tebar"], ["Volume"], ["Total Ikan"], ["Konsumsi Pakan Harian"], ["Jumlah Ekor di Awal"]]);
  sheet.getRange("D6").setValue("Benih");
  
  sheet.getRange("D2").setValue("120 ekor/m3");
  sheet.getRange("D3").setValue("94.5 m3");
  sheet.getRange("D4").setValue("11340 ekor");
  sheet.getRange("D5").setValue("2% dari bobot ikan");
  sheet.getRange("D6").setValue(11340); // Acuan Dasar Jumlah Ikan

  // TANGGAL TEBAR (Acuan Apps script mensinkronkan data Python)
  sheet.getRange("F1").setValue("TANGGAL TEBAR (Mulai):").setFontWeight("bold").setHorizontalAlignment("right");
  sheet.getRange("G1").setValue(new Date()).setNumberFormat("dd/MM/yyyy").setBackground("#fef08a");

  // HARGA PAKAN KANAN ATAS
  sheet.getRange("I3:I6").setValues([["Tinggi"],["Sedang"],["Rendah"],["Cost per kg"]]).setHorizontalAlignment("right");
  sheet.getRange("J2:L2").setValues([["P Irwan", "original", "Kemal"]]).setFontWeight("bold").setHorizontalAlignment("center");
  sheet.getRange("J3:L3").setValues([[18500, 14000, 18500]]).setBackground("#fce7f3");
  sheet.getRange("J4:L4").setValues([[11500, 10000, 11500]]).setBackground("#fef9c3");
  sheet.getRange("J5:L5").setValues([[11000, 8000, 7667]]).setBackground("#dcfce7");
  sheet.getRange("J3:L6").setNumberFormat("Rp#,##0");

  // HEADER TABEL (Baris 7)
  const headers = [
    "Umur (Minggu)", "Berat/gram", "Pakan %", "Jumlah Ikan", 
    "Total Kematian", "Total Ikan Hidup", "SR", "Gram", 
    "Kilogram", "Pakan Harian (kg)", "Pakan Mingguan",
    "Kualitas Pakan", "Harga Pakan", "Biaya Pakan Per Minggu",
    "PAKAN AKTUAL (Kg)", "FCR AKTUAL" // Tambahan FCR
  ];
  sheet.getRange(7, 1, 1, 16).setValues([headers]).setBackground("black").setFontColor("white").setFontWeight("bold").setHorizontalAlignment("center");
       
  // DATA PER MINGGU (Baris 8 - 23)
  const sopBerat = [8.5, 15.9, 21.5, 29.0, 38.2, 48.9, 62.6, 77.9, 94.3, 110.8, 126.3, 139.5, 147.7, 0, 0, 0];
  const sopPakan = [0.05, 0.05, 0.025, 0.025, 0.025, 0.025, 0.025, 0.025, 0.025, 0.025, 0.025, 0.025, 0.025, 0, 0, 0];
  const sopKualitas = ["Tinggi","Tinggi","Tinggi","Tinggi","Sedang","Sedang","Sedang","Sedang","Sedang","Sedang","Sedang","Rendah","Rendah","Rendah","Rendah","Rendah"];
  const sopHarga = [18500,18500,18500,18500,11500,11500,11500,11500,11500,11500,11500,11000,11000,11000,11000,11000];

  for (let i = 8; i <= 23; i++) {
     let m = i - 7;
     let idx = m - 1;
     sheet.getRange(i, 1).setValue(m); // A
     sheet.getRange(i, 2).setValue(sopBerat[idx] || ""); // B -> Akan ditimpa otomatis oleh Fungsi Sync Sampling
     sheet.getRange(i, 3).setValue(sopPakan[idx] || ""); // C
     
     sheet.getRange(i, 4).setFormula("=D$6"); // D
     if(i == 8) sheet.getRange(i, 5).setValue(0); // E -> Akan ditimpa otomatis oleh Fungsi Sync Dead Fish
     
     if (i == 8) sheet.getRange(i, 6).setFormula("=D8-E8"); // F
     else sheet.getRange(i, 6).setFormula(`=F${i-1}-E${i}`);
     
     sheet.getRange(i, 7).setFormula(`=F${i}/D${i}`); // G
     sheet.getRange(i, 8).setFormula(`=F${i}*B${i}`); // H
     sheet.getRange(i, 9).setFormula(`=H${i}/1000`);  // I
     sheet.getRange(i, 10).setFormula(`=I${i}*C${i}`); // J
     sheet.getRange(i, 11).setFormula(`=J${i}*7`); // K
     sheet.getRange(i, 12).setValue(sopKualitas[idx] || ""); // L
     sheet.getRange(i, 13).setValue(sopHarga[idx] || ""); // M
     sheet.getRange(i, 14).setFormula(`=M${i}*K${i}`); // N
     
     // O: Pakan Aktual (Bot Python nulis ke sini nanti)
     sheet.getRange(i, 15).setValue(0);
     
     // P: Rumus FCR (Pakan Aktual / Daging yg bertambah)
     if (i == 8) {
        sheet.getRange(i, 16).setValue(0);
     } else {
        // Menggunakan IFERROR agar terhindar dari #DIV/0! jika pertumbuhan ikan 0
        sheet.getRange(i, 16).setFormula(`=IFERROR(O${i}/(I${i}-I${i-1}), 0)`);
     }
  }
  
  // REKAP BAWAH
  sheet.getRange("B27:C31").setValues([
    ["Total Kematian Ikan", "=SUM(E8:E23)"], ["Total SR", "=1-(C27/D6)"], ["Total Hasil Panen", "=MAX(I8:I23)"], ["Total Target Pakan", "=SUM(K8:K23)"], ["Total FCR (Target)", "=C30/C29"]
  ]);
  sheet.getRange("G27:J31").setValues([
    ["Total Biaya Pakan", "", "", "=SUM(N8:N23)"], ["HPP", "", "", "=J27/C29"], ["Harga Jual/kg", "", "", 26000], ["Total Harga Jual", "", "", "=J29*C29"], ["Total Keuntungan", "", "", "=J30-J27"]
  ]);

  // STYLING
  sheet.getRange("C8:C23").setNumberFormat("0.0%"); sheet.getRange("G8:G23").setNumberFormat("0.00%");
  sheet.getRange("H8:J23").setNumberFormat("0.00"); sheet.getRange("K8:K23").setNumberFormat("0.00");
  sheet.getRange("M8:N23").setNumberFormat("Rp#,##0"); 
  sheet.getRange("O8:O23").setNumberFormat("0.00"); sheet.getRange("P8:P23").setNumberFormat("0.00");
  sheet.getRange("C28").setNumberFormat("0.00%"); sheet.getRange("C29:C31").setNumberFormat("0.00");
  sheet.getRange("J27:J31").setNumberFormat("Rp#,##0");
  sheet.getRange("O7:P23").setBackground("#e0f2fe"); // Biru penanda Aktual
  
  SpreadsheetApp.getUi().alert("SELESAI", "Template 'FCR Tracker' berhasil dibuat! Jangan lupa isi Sel G1 dengan Tanggal Mulai Tebar Benih.", SpreadsheetApp.getUi().ButtonSet.OK);
}


/**
 * =========================================================================
 * 3. DASHBOARD UI (Sama Canggihnya)
 * =========================================================================
 */
function openFcrDashboardUI() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  if (!ss.getSheetByName(TAB_MASTER)) {
      SpreadsheetApp.getUi().alert("Tab 'FCR Tracker' belum ada."); return;
  }
  
  // PASTI-KAN DISINKRONISASI SEBELUM DIBUKA
  syncDataDariBot();

  const htmlString = `
    <!DOCTYPE html>
    <html>
    <head>
      <base target="_top">
      <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
      <style>
        * { box-sizing: border-box; font-family: 'Inter', sans-serif; }
        body { margin: 0; background-color: #f8fafc; color: #1e293b; padding-bottom: 20px;}
        .header { background: #1e293b; color: white; padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; }
        .header h2 { margin: 0; font-size: 18px; }
        .main-container { display: flex; flex-direction: row; gap: 20px; padding: 20px; max-width: 1200px; margin: 0 auto; }
        .col-left { flex: 1; min-width: 350px; }
        .col-right { flex: 2; min-width: 500px; display: flex; flex-direction: column; gap: 20px; }
        .card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); margin-bottom: 20px; }
        .card-title { font-size: 14px; font-weight: 700; color: #64748b; margin-bottom: 16px; text-transform: uppercase; border-bottom: 2px solid #f1f5f9; padding-bottom: 8px;}
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .stat-box { background: #f1f5f9; padding: 12px; border-radius: 8px; text-align: center;}
        .stat-val { font-size: 20px; font-weight: 800; color: #0f172a; }
        .stat-lbl { font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 600;}
      </style>
    </head>
    <body>
      <div class="header">
        <h2>🐟 DASHBOARD FCR (HYBRID AI)</h2>
        <div id="weekBadge" style="background:#3b82f6; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 13px;">Minggu Ke-?</div>
      </div>
      
      <div class="main-container">
        <!-- KIRI -->
        <div class="col-left">
          <div class="card">
             <div class="card-title">STATISTIK MINGGU INI (Tabel Klien)</div>
             <div class="stat-grid">
                <div class="stat-box"><div class="stat-val" id="stBiomassa">0 Kg</div><div class="stat-lbl">Biomassa (Kolom I)</div></div>
                <div class="stat-box" style="background:#d1fae5;"><div class="stat-val" style="color:#065f46" id="stTarget">0 Kg</div><div class="stat-lbl">Target SOP (Kolom K)</div></div>
                <div class="stat-box" style="background:#fee2e2;"><div class="stat-val" style="color:#991b1b" id="stAktual">0 Kg</div><div class="stat-lbl">Pakan Aktual (Kolom O)</div></div>
                <div class="stat-box"><div class="stat-val" id="stFcr">0.00</div><div class="stat-lbl">FCR Aktual (Kolom P)</div></div>
             </div>
             <p style="font-size: 12px; color: #475569; margin-top:15px; text-align:center;">
               ✅ Data Kematian & Sampling telah di-Sync 100% otomatis dari input Bot Python.
             </p>
          </div>
        </div>
        
        <!-- KANAN -->
        <div class="col-right">
          <div class="card">
             <div class="card-title">📈 TREN FCR AKTUAL VS TARGET (Mingguan)</div>
             <canvas id="fcrChart" height="100"></canvas>
          </div>
          <div class="card">
             <div class="card-title">📊 PAKAN TARGET (K) VS AKTUAL (O)</div>
             <canvas id="feedChart" height="60"></canvas>
          </div>
        </div>
      </div>

      <script>
        google.script.run.withSuccessHandler(initDashboard).getKalkulasiDashboard();

        function initDashboard(payload) {
          if(payload.error) { alert('ERROR: ' + payload.error); return; }
          const data = payload.data;
          let currentWeek = payload.currentWeek;
          
          document.getElementById('weekBadge').innerText = "Berjalan: Minggu Ke-" + currentWeek;
          
          // Data Baris Aktif
          let curRow = data.find(d => d.minggu === currentWeek);
          if(!curRow) curRow = data[data.length-1];

          document.getElementById('stBiomassa').innerText = (curRow.biomassa || 0).toFixed(1) + " Kg";
          document.getElementById('stTarget').innerText = (curRow.target_mingguan || 0).toFixed(1) + " Kg";
          document.getElementById('stAktual').innerText = (curRow.pakan_aktual || 0).toFixed(1) + " Kg";
          document.getElementById('stFcr').innerText = (curRow.fcr_aktual || 0).toFixed(2);

          renderCharts(data);
        }

        function renderCharts(dataArray) {
           const labels = dataArray.map(d => 'M-' + d.minggu);
           const pakanTarget = dataArray.map(d => d.target_mingguan);
           const pakanAktual = dataArray.map(d => d.pakan_aktual);
           const fcrAktual = dataArray.map(d => d.fcr_aktual);

           new Chart(document.getElementById('fcrChart').getContext('2d'), {
              type: 'line', data: { labels: labels, datasets: [{ label: 'FCR Aktual', data: fcrAktual, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', fill: true, tension: 0.3 }]},
              options: { responsive: true, plugins: { legend: { display:false } }}
           });

           new Chart(document.getElementById('feedChart').getContext('2d'), {
              type: 'bar', data: { labels: labels, datasets: [{ label: 'Target SOP (Kolom K)', data: pakanTarget, backgroundColor: '#cbd5e1' }, { label: 'Pakan Aktual (Kolom O)', data: pakanAktual, backgroundColor: '#3b82f6' }] },
              options: { responsive: true }
           });
        }
      </script>
    </body>
    </html>
  `;
  const view = HtmlService.createHtmlOutput(htmlString).setWidth(1200).setHeight(600);
  SpreadsheetApp.getUi().showModalDialog(view, 'Interactive Dashboard');
}

/**
 * =========================================================================
 * 4. FUNGSI PENARIK DATA KE CHART UI 
 * =========================================================================
 */
function getKalkulasiDashboard() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(TAB_MASTER);
  if (!sheet) return { error: "Tab 'FCR Tracker' tidak ada!" };

  try {
    const dataRange = sheet.getRange(8, 1, 16, 16).getValues(); 
    let historyData = [];
    let activeWeek = 1;

    for (let i = 0; i < dataRange.length; i++) {
        let row = dataRange[i];
        let w = parseFloat(row[0]);
        if (isNaN(w) || w <= 0) continue; 

        let pakanAktual = parseFloat(row[14]) || 0; 
        
        historyData.push({
           minggu: w, mati: parseFloat(row[4]) || 0, biomassa: parseFloat(row[8]) || 0,
           target_mingguan: parseFloat(row[10]) || 0, pakan_aktual: pakanAktual, fcr_aktual: parseFloat(row[15]) || 0
        });
        
        if (pakanAktual > 0) activeWeek = w;
    }
    return { data: historyData, currentWeek: activeWeek };
  } catch (err) {
    return { error: err.toString() };
  }
}
