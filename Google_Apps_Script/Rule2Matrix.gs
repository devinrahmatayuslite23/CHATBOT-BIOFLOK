/**
 * =========================================================================
 * 💫 PUSAT KENDALI OTOMASI MATRIX DIAGNOSA & RULES (V4 ULTIMATE PRO)
 * + ALL-IN-ONE Database Manager (UI Modal HTML, Add/Delete Item, & Export!)
 * =========================================================================
 */

const TAB_RULES = "Diagnosis_Rules";
const TAB_MATRIX = "Matrix Diagnosis";
const START_ROW_RULES = 2; 
const COL_PARAMETER = 1;   
const COL_KEYWORD = 2;     
const COL_TAB_SOURCE = 3;  
const COL_OPERATOR = 4;    
const MATRIX_START_COL = 4; 

function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('⚙️ Sync Diagnosa')
    .addItem('🗃️ Buka Database Manager', 'openDatabaseManager') 
    .addSeparator() 
    .addItem('📥 Tarik Import Matrix ke Rules', 'syncRulesFromMatrix')
    .addItem('📤 Tembakan Data Rules ke Matrix', 'syncMatrixFromRules')
    .addItem('🔧 Segarkan Semua Dropdown', 'refreshAllDropdowns')
    .addToUi();
    
  ui.createMenu('🧪 AI Simulator')
    .addItem('💻 Buka Layar Simulasi Mapped', 'openSimulatorUI')
    .addToUi();
}

/**
 * =========================================================================
 * FITUR EKSKLUSIF: 🗃️ DATABASE MANAGER (TAMPILAN WEB ALL-IN-ONE)
 * =========================================================================
 */
function openDatabaseManager() {
  const htmlString = `
    <!DOCTYPE html>
    <html>
    <head>
      <base target="_top">
      <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 12px; background: #f4f6f9; color: #202124; margin: 0; }
        h2 { color: #1a73e8; border-bottom: 2px solid #e8eaed; padding-bottom: 6px; font-size: 15px; margin-top: 5px; margin-bottom: 10px; font-weight: 600;}
        .card { background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.12); padding: 15px; margin-bottom: 15px; }
        .list-group { list-style: none; padding: 0; margin: 0; max-height: 160px; overflow-y: auto; border: 1px solid #f1f3f4; border-radius: 4px;}
        .list-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; border-bottom: 1px solid #f1f3f4; font-size: 13px; }
        .list-item:nth-child(even) { background-color: #f8f9fa; }
        .list-item:last-child { border-bottom: none; }
        .b-name { color: #3c4043; font-weight: 500; }
        .btn-del { background: #ea4335; color: white; border: none; border-radius: 4px; padding: 4px 8px; cursor: pointer; font-size: 11px; font-weight: bold; transition: 0.2s;}
        .btn-del:hover { background: #d33426; }
        .btn-dl { background: #0f9d58; color: white; border: none; border-radius: 6px; padding: 12px 15px; cursor: pointer; font-size: 14px; font-weight: bold; width: 100%; text-align: center; transition: 0.2s; box-shadow: 0 2px 4px rgba(0,0,0,0.2);}
        .btn-dl:hover { background: #0b8043; }
        .input-group { display: flex; margin-bottom: 10px; }
        .t-prop { flex: 1; padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px 0 0 4px; outline: none; font-size: 13px; }
        .t-prop:focus { border-color: #1a73e8; }
        .btn-add { background: #1a73e8; color: white; border: none; border-radius: 0 4px 4px 0; padding: 8px 15px; cursor: pointer; font-size: 13px; font-weight: bold; transition: 0.2s;}
        .btn-add:hover { background: #1557b0; }
        #loader { text-align: center; padding: 60px 20px; color: #5f6368; font-size: 15px; font-style: italic; font-weight: 500;}
        /* Scrollbar cantik */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-thumb { background-color: #dadce0; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background-color: #bdc1c6; }
      </style>
    </head>
    <body>
      <div id="loader">⏳ Memindai Isi Database Spreadsheet...<br>Mohon tunggu.</div>
      <div id="content" style="display:none;">
        
        <div class="card">
          <h2>🧬 Seting Parameter Sensor</h2>
          <div class="input-group">
             <input type="text" id="newParam" class="t-prop" placeholder="Ketik nama Parameter baru (cth: TDS)...">
             <button class="btn-add" onclick="addItem('parameter')">➕ Tambah</button>
          </div>
          <ul class="list-group" id="paramsList"></ul>
        </div>
        
        <div class="card">
          <h2>🦠 Seting Daftar Penyakit (Diagnosa)</h2>
          <div class="input-group">
             <input type="text" id="newDiag" class="t-prop" placeholder="Ketik nama Penyakit baru...">
             <button class="btn-add" onclick="addItem('diagnosis')">➕ Tambah</button>
          </div>
          <ul class="list-group" id="diagList"></ul>
        </div>
        
        <div class="card">
          <h2>💾 Eksport Database (Backup CSV)</h2>
          <button class="btn-dl" onclick="downloadCSV('matrix')" id="dlbtnMatrix" style="margin-bottom:8px; background:#f4b400;">⬇️ Download Matrix Diagnosa (.CSV)</button>
          <button class="btn-dl" onclick="downloadCSV('rules')" id="dlbtnRules" style="background:#0f9d58;">⬇️ Download Aturan Sensor (.CSV)</button>
        </div>
        
      </div>

      <script>
        google.script.run.withSuccessHandler(populateUI).getDatabaseData();

        function populateUI(data) {
          document.getElementById('loader').style.display = 'none';
          document.getElementById('content').style.display = 'block';
          
          const pList = document.getElementById('paramsList');
          pList.innerHTML = '';
          data.parameters.forEach(p => {
             const li = document.createElement('li');
             li.className = 'list-item';
             li.innerHTML = \`<span class="b-name">\${p}</span> <button class="btn-del" onclick="deleteItem('parameter', '\${p}')">❌ Hapus</button>\`;
             pList.appendChild(li);
          });
          if(data.parameters.length===0) pList.innerHTML = "<div style='padding:10px;text-align:center;color:#80868b;'><i><small>Belum ada parameter terdaftar.</small></i></div>";

          const dList = document.getElementById('diagList');
          dList.innerHTML = '';
          data.diagnoses.forEach(d => {
             const li = document.createElement('li');
             li.className = 'list-item';
             li.innerHTML = \`<span class="b-name">\${d}</span> <button class="btn-del" onclick="deleteItem('diagnosis', '\${d}')">❌ Hapus</button>\`;
             dList.appendChild(li);
          });
          if(data.diagnoses.length===0) dList.innerHTML = "<div style='padding:10px;text-align:center;color:#80868b;'><i><small>Belum ada daftar penyakit.</small></i></div>";
        }

        function deleteItem(type, name) {
          const typeName = type === 'parameter' ? 'Kolom Parameter & Sensor' : 'Baris Penyakit';
          if(confirm("PERINGATAN!\\n\\nYakin MENGHAPUS secara TOTAL " + typeName + " : '" + name + "' ?\\nData yang dihapus akan seketika tercabut dari semua tabel (Matrix maupun Rules)!")) {
             document.getElementById('loader').innerHTML = "🗑️ Sedang memusnahkan '" + name + "' dari akar Matrix...<br>Jangan tutup layar ini.";
             document.getElementById('loader').style.display = 'block';
             document.getElementById('content').style.display = 'none';
             
             google.script.run.withSuccessHandler(function() {
                document.getElementById('loader').innerHTML = "✅ Sukses dihapus! Memuat ulang...";
                google.script.run.withSuccessHandler(populateUI).getDatabaseData();
             }).deleteDatabaseItem(type, name);
          }
        }

        function addItem(type) {
          const inputId = type === 'parameter' ? 'newParam' : 'newDiag';
          const val = document.getElementById(inputId).value.trim();
          if(!val) { alert("⚠️ Nama tidak boleh kosong!"); return; }
          
          const typeName = type === 'parameter' ? 'Parameter' : 'Penyakit';
          document.getElementById('loader').innerHTML = "⏳ Sedang menanamkan " + typeName + " '" + val + "' ke dalam Matrix...<br>Jangan tutup layar ini.";
          document.getElementById('loader').style.display = 'block';
          document.getElementById('content').style.display = 'none';
          
          google.script.run.withSuccessHandler(function() {
             document.getElementById(inputId).value = ''; // Kosongkan Input
             document.getElementById('loader').innerHTML = "✅ Sukses ditambahkan! Memuat ulang...";
             google.script.run.withSuccessHandler(populateUI).getDatabaseData();
          }).addDatabaseItem(type, val);
        }

        function downloadCSV(type) {
          const btn = type === 'matrix' ? document.getElementById('dlbtnMatrix') : document.getElementById('dlbtnRules');
          const oriText = btn.innerText;
          const oriBg = btn.style.background;
          
          btn.innerText = "⏳ Sedang Merangkum CSV...";
          btn.style.background = "#5f6368";
          
          google.script.run.withSuccessHandler(function(csvStr) {
             btn.innerText = "✅ Download Berhasil!";
             btn.style.background = "#1a73e8";
             
             const blob = new Blob([csvStr], {type: "text/csv;charset=utf-8;"});
             const url = window.URL.createObjectURL(blob);
             const a = document.createElement("a");
             a.href = url;
             const fileName = type === 'matrix' ? "Matrix_Diagnosa" : "Diagnosis_Rules";
             a.download = fileName + "_" + new Date().toISOString().split('T')[0] + ".csv";
             a.click();
             window.URL.revokeObjectURL(url);
             
             setTimeout(() => { 
                btn.innerText = oriText; 
                btn.style.background = oriBg;
             }, 3000);
          }).generateCSVPayload(type);
        }
      </script>
    </body>
    </html>
  `;
  const htmlOutput = HtmlService.createHtmlOutput(htmlString).setWidth(430).setHeight(680);
  SpreadsheetApp.getUi().showModalDialog(htmlOutput, '🗃️ BIOFLOK DATABASE MANAGER');
}

/** 
 * Fungsi Penambah Fisik 
 */
function addDatabaseItem(type, name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  if (type === 'parameter') {
     const rulesSheet = ss.getSheetByName(TAB_RULES);
     const data = rulesSheet.getRange("A:A").getValues();
     let insertRow = START_ROW_RULES;
     for(let i = data.length - 1; i >= 0; i--) {
        if (data[i][0] && data[i][0].toString().trim() !== "") {
           insertRow = i + 2; break;
        }
     }
     rulesSheet.getRange(insertRow, 1).setValue(name);
     syncMatrixFromRules(); 
     return "OK";
  } 
  else if (type === 'diagnosis') {
     const mapSheet = ss.getSheetByName(TAB_MATRIX);
     const data = mapSheet.getRange("C:C").getValues();
     let insertRow = 3; 
     for(let i = data.length - 1; i >= 0; i--) {
        if (data[i][0] && data[i][0].toString().trim() !== "" && !data[i][0].toString().toUpperCase().includes("COSTS")) {
           insertRow = i + 2; break;
        }
     }
     mapSheet.getRange(insertRow, 1).setValue(insertRow - 2); 
     mapSheet.getRange(insertRow, 2).setValue(1); 
     mapSheet.getRange(insertRow, 3).setValue(name); 
     applyMatrixDropdown(mapSheet); 
     return "OK";
  }
}

/** 
 * Fungsi Penghapus Fisik dari Modal 
 */
function deleteDatabaseItem(type, name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const rSheet = ss.getSheetByName(TAB_RULES);
  const mSheet = ss.getSheetByName(TAB_MATRIX);
  
  if (type === 'parameter') {
     const pData = rSheet.getRange("A:A").getValues();
     for(let i=pData.length-1; i>=0; i--) { 
        if(pData[i][0] && pData[i][0].toString().trim() === name) rSheet.deleteRow(i + 1);
     }
     const maxCol = mSheet.getLastColumn();
     if(maxCol > 0) {
        const hData = mSheet.getRange(1, 1, 1, maxCol).getValues()[0];
        for(let j=hData.length-1; j>=0; j--) {
           if(hData[j] && hData[j].toString().trim() === name) mSheet.deleteColumn(j + 1);
        }
     }
     return "OK";
  } 
  else if (type === 'diagnosis') {
     const dData = mSheet.getRange("C:C").getValues();
     for(let i=dData.length-1; i>=0; i--) {
        if(dData[i][0] && dData[i][0].toString().trim() === name) mSheet.deleteRow(i + 1);
     }
     return "OK";
  }
}

/** Fungsi Pencari Data untuk Modal */
function getDatabaseData() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const parameters = [];
  const rSheet = ss.getSheetByName(TAB_RULES);
  if (rSheet) {
    const pData = rSheet.getRange(START_ROW_RULES, COL_PARAMETER, rSheet.getLastRow() || 1, 1).getValues();
    for(let i=0; i<pData.length; i++){
       let val = pData[i][0].toString().trim();
       if(val !== "" && val.toLowerCase() !== "cost ($)") parameters.push(val);
    }
  }
  const diagnoses = [];
  const mSheet = ss.getSheetByName(TAB_MATRIX);
  if (mSheet && mSheet.getLastRow() >= 3) {
    const dData = mSheet.getRange(3, 3, mSheet.getLastRow(), 1).getValues(); 
    for(let i=0; i<dData.length; i++){
       let val = dData[i][0].toString().trim();
       if(val !== "" && val.toLowerCase() !== "costs:") diagnoses.push(val);
    }
  }
  return { parameters: parameters, diagnoses: diagnoses };
}

/** Fungsi Perangkum Data (Eksport ke CSV) */
function generateCSVPayload(type) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(type === 'matrix' ? TAB_MATRIX : TAB_RULES);
  if(!sheet) return "";
  
  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();
  if(lastRow === 0 || lastCol === 0) return "";
  
  const data = sheet.getRange(1, 1, lastRow, lastCol).getValues();
  let csvContent = "";
  
  for(let i=0; i<data.length; i++) {
     let rowContent = data[i].map(cell => {
         let cellStr = cell.toString().replace(/'=/, '='); // Bersihkan tanda apostrof operator
         if(cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\\n')) {
             cellStr = '"' + cellStr.replace(/"/g, '""') + '"'; // Antisipasi jika ada koma di text
         }
         return cellStr;
     });
     csvContent += rowContent.join(",") + "\\r\\n";
  }
  
  return csvContent;
}

// ==========================================
// FUNGSI INTI OTOMASI (ON EDIT TAB)
// ==========================================
function onEdit(e) {
  if (!e || !e.range) return;
  const sheet = e.range.getSheet();
  const editRow = e.range.getRow();
  const editCol = e.range.getColumn();
  if (sheet.getName() === TAB_RULES && editRow >= START_ROW_RULES) {
    if (editCol === COL_TAB_SOURCE) updateKeywordDropdown(sheet, e.range);
    if (editCol === COL_PARAMETER) syncMatrixFromRules();
  } else if (sheet.getName() === TAB_MATRIX) {
    if (editRow === 1 && editCol >= MATRIX_START_COL) syncRulesFromMatrix();
    else if (editCol === 3 && editRow >= 3) applyMatrixDropdown(sheet);
  } else if (editRow === 1) forceUpdateAllRelatedKeywords(sheet.getName());
}

function syncRulesFromMatrix() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const r = ss.getSheetByName(TAB_RULES);
  const m = ss.getSheetByName(TAB_MATRIX);
  if (!r || !m) return;
  const maxC = m.getLastColumn() < MATRIX_START_COL ? MATRIX_START_COL : m.getLastColumn();
  const mHead = m.getRange(1, MATRIX_START_COL, 1, maxC - MATRIX_START_COL + 1).getValues()[0];
  const mParams = mHead.map(x => x.toString().trim()).filter(x => x !== "" && !x.toLowerCase().includes("cost"));
  let oldData = r.getMaxRows() >= START_ROW_RULES ? r.getRange(START_ROW_RULES, 1, r.getMaxRows(), 6).getValues() : [];
  
  const newData = mParams.map(p => {
    let match = oldData.find(o => o[0] && o[0].toString().trim() === p);
    return match ? [p, match[1], match[2], match[3], match[4], match[5]] : [p, "", "", "", "", ""];
  });

  if(r.getMaxRows() >= START_ROW_RULES){
     r.getRange(START_ROW_RULES, 1, r.getMaxRows(), 6).clearContent();
     r.getRange(START_ROW_RULES, COL_KEYWORD, r.getMaxRows(), 1).clearDataValidations();
  }
  if(newData.length > 0) r.getRange(START_ROW_RULES, 1, newData.length, 6).setValues(newData);
  refreshAllDropdowns();
  
  newData.forEach((row, i) => {
     if(row[2].toString().trim() !== "") updateKeywordDropdown(r, r.getRange(START_ROW_RULES + i, COL_TAB_SOURCE));
  });

  for(let c=MATRIX_START_COL; c<=maxC; c++) {
     let title = m.getRange(1, c).getValue().toString().toLowerCase();
     if(!title.includes("cost") && m.getRange(2, c).getValue() === "") m.getRange(2, c).setValue(1);
  }
  applyMatrixDropdown(m);
}

function syncMatrixFromRules() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const r = ss.getSheetByName(TAB_RULES);
  const m = ss.getSheetByName(TAB_MATRIX);
  if (!r || !m) return;
  const rParams = r.getRange(START_ROW_RULES, 1, r.getLastRow() || 1, 1).getValues().map(x => x[0].toString().trim()).filter(x => x !== "");
  
  const maxC = m.getLastColumn() < MATRIX_START_COL ? MATRIX_START_COL : m.getLastColumn();
  const oldH = m.getRange(1, MATRIX_START_COL, 1, maxC - MATRIX_START_COL + 1).getValues()[0];
  let costData = null, costName = "Cost ($)";
  for(let i=0; i<oldH.length; i++){
     if(oldH[i].toString().toLowerCase().includes("cost")){
        costData = m.getRange(1, MATRIX_START_COL+i, m.getMaxRows(), 1).getValues(); 
        costName = oldH[i]; break;
     }
  }

  let tCol = MATRIX_START_COL;
  rParams.forEach(p => {
    m.getRange(1, tCol).setValue(p);
    if(m.getRange(2, tCol).getValue() === "") m.getRange(2, tCol).setValue(1);
    tCol++;
  });

  if(costData) m.getRange(1, tCol, costData.length, 1).setValues(costData);
  else m.getRange(1, tCol).setValue(costName);
  
  if(m.getLastColumn() > tCol) {
    m.getRange(1, tCol+1, m.getMaxRows(), m.getLastColumn()-tCol).clearContent().clearDataValidations();
  }
  applyMatrixDropdown(m);
}

function applyMatrixDropdown(m) {
   const maxC = m.getLastColumn() < MATRIX_START_COL ? MATRIX_START_COL : m.getLastColumn();
   const headers = m.getRange(1, MATRIX_START_COL, 1, maxC - MATRIX_START_COL + 1).getValues()[0];
   if(m.getMaxRows() >= 3) {
      const rule = SpreadsheetApp.newDataValidation().requireValueInList(["PASS", "FAIL", "?"], true).build();
      headers.forEach((h, i) => {
         let title = h.toString().toLowerCase();
         let cRange = m.getRange(3, MATRIX_START_COL+i, m.getMaxRows()-2, 1);
         cRange.clearDataValidations();
         if(title !== "" && !title.includes("cost")) cRange.setDataValidation(rule);
      });
   }
}

function updateKeywordDropdown(rSheet, ed) {
  const name = ed.getValue(), cell = rSheet.getRange(ed.getRow(), COL_KEYWORD);
  cell.clearDataValidations();
  if(!name) { cell.setValue(''); return; }
  const tSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(name);
  if(tSheet) {
    const valid = tSheet.getRange(1, 1, 1, tSheet.getLastColumn()||1).getValues()[0].filter(h => h !== "");
    if(valid.length > 0) cell.setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(valid, true).build());
    else cell.setValue('Kosong');
  } else cell.setValue('Tidak Ditemukan');
}

function refreshAllDropdowns() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const r = ss.getSheetByName(TAB_RULES);
  if(!r) return;
  const tn = ss.getSheets().map(s => s.getName()).filter(n => ![TAB_RULES, TAB_MATRIX, "TUTORIAL"].includes(n));
  const lr = r.getMaxRows();
  if(lr >= START_ROW_RULES){
     r.getRange(START_ROW_RULES, COL_TAB_SOURCE, lr, 1).setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(tn, true).build());
     const op = r.getRange(START_ROW_RULES, COL_OPERATOR, lr, 1);
     op.setNumberFormat('@');  
     op.setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList([">", "<", ">=", "<=", "'="], true).build());
  }
}

function forceUpdateAllRelatedKeywords(n) { 
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const r = ss.getSheetByName(TAB_RULES);
  const s = ss.getSheetByName(n);
  if (!r || !s) return;
  const valid = s.getRange(1, 1, 1, s.getLastColumn()||1).getValues()[0].filter(h => h !== "");
  if(valid.length === 0 || r.getMaxRows() < START_ROW_RULES) return;
  const rs = r.getRange(START_ROW_RULES, COL_TAB_SOURCE, r.getMaxRows(), 1).getValues();
  rs.forEach((src, i) => {
    if(src[0].toString().trim() === n) {
       let c = r.getRange(START_ROW_RULES + i, COL_KEYWORD);
       c.clearDataValidations();
       c.setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(valid, true).build());
    }
  });
}
