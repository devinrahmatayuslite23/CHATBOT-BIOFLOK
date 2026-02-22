/**
 * =========================================================================
 * 🧪 AI DIAGNOSIS SIMULATOR (OFFLINE BAYESIAN ENGINE)
 * =========================================================================
 * This script runs entirely in Google Sheets and provides a realtime
 * toggle-based UI to test the Matrix Diagnosis logic and check Bayesian scores.
 */

function openSimulatorUI() {
  const htmlString = `
    <!DOCTYPE html>
    <html>
    <head>
      <base target="_top">
      <style>
        * { box-sizing: border-box; }
        body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; background-color: #f7f9fc; color: #334155; }
        h4 { color: #64748b; font-size: 13px; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 12px; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;}
        
        .layout { display: flex; height: 100vh; overflow: hidden; }
        .pane-left { width: 45%; padding: 20px; overflow-y: auto; background: white; border-right: 1px solid #e2e8f0; }
        .pane-right { width: 55%; padding: 20px; overflow-y: auto; background: #f8fafc; }
        
        /* Obs Item */
        .obs-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border: 1px solid #f1f5f9; margin-bottom: 6px; border-radius: 6px; }
        .obs-item:hover { background: #f8fafc; }
        .obs-label { font-size: 13px; font-weight: 600; color: #0f172a; }
        
        /* Buttons */
        .btngrp { display: flex; border: 1px solid #cbd5e1; border-radius: 4px; overflow: hidden; }
        .btn-t { flex: 1; padding: 4px 12px; border: none; background: white; font-weight: bold; font-size: 12px; cursor: pointer; color: #94a3b8; outline: none; transition: 0.2s;}
        .btn-t.p { border-right: 1px solid #cbd5e1; }
        .btn-t.f { border-right: 1px solid #cbd5e1; }
        
        .btn-t.p.active { background: #10b981; color: white; }
        .btn-t.f.active { background: #ef4444; color: white; }
        .btn-t.x.active { background: #e2e8f0; color: #475569; }

        /* Score & Bars */
        .result-item { margin-bottom: 15px; }
        .r-header { display: flex; justify-content: space-between; font-size: 13px; font-weight: 600; color: #334155; margin-bottom: 4px;}
        .r-score { color: #4f46e5; }
        .bar-bg { background: #e2e8f0; height: 8px; border-radius: 4px; overflow: hidden; position: relative;}
        .bar-fill { background: #6366f1; height: 100%; transition: width 0.3s ease; }
        
        /* Log Panel */
        .log-box { background: white; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; margin-top: 20px; font-family: monospace; font-size: 12px; color: #334155; }
        .log-title { font-weight: 700; color: #4f46e5; margin-bottom: 10px; font-size: 13px; font-family: 'Inter', sans-serif;}
        .log-good { color: #10b981; }
        .log-bad { color: #ef4444; }
        
        #loader { text-align: center; margin-top: 50px; font-weight: 600; color: #64748b; }
      </style>
    </head>
    <body>
      <div id="loader">⏳ Memuat Matrix & Sensosr dari Spreadsheet...</div>
      
      <div class="layout" id="mainLayout" style="display:none;">
        <div class="pane-left">
          <h4>SENSOR OBSERVATIONS (MAPPED)</h4>
          <div id="obsList"></div>
        </div>
        
        <div class="pane-right">
          <h4>LIKELY FAULTS ANALYSIS</h4>
          <div id="resultsList"></div>
          
          <div class="log-box" id="calcLog">
             <div class="log-title">CALCULATION LOG</div>
             <div id="logContent">Pilih parameter di sebelah kiri untuk melihat simulasi kalkulasi Matrix AI secara langsung.</div>
          </div>
        </div>
      </div>

      <script>
        let db = { parameters: [], diseases: [], totalFreq: 1 };
        let states = {}; // holds 'P', 'F', 'x'

        // Load Data
        google.script.run.withSuccessHandler(data => {
            db = data;
            db.parameters.forEach(p => states[p] = 'x'); // default to 'x'
            document.getElementById('loader').style.display = 'none';
            document.getElementById('mainLayout').style.display = 'flex';
            renderControls();
            runSimulation();
        }).getMatrixLogicForSimulator();

        function renderControls() {
            const list = document.getElementById('obsList');
            list.innerHTML = '';
            
            db.parameters.forEach(p => {
                const item = document.createElement('div');
                item.className = 'obs-item';
                item.innerHTML = \`
                    <div class="obs-label">\${p}</div>
                    <div class="btngrp">
                        <button class="btn-t p \${states[p]==='P'?'active':''}" onclick="toggle('\${p}', 'P')">P</button>
                        <button class="btn-t f \${states[p]==='F'?'active':''}" onclick="toggle('\${p}', 'F')">F</button>
                        <button class="btn-t x \${states[p]==='x'?'active':''}" onclick="toggle('\${p}', 'x')">x</button>
                    </div>
                \`;
                list.appendChild(item);
            });
        }

        function toggle(param, state) {
            states[param] = state;
            renderControls();
            runSimulation();
        }

        function runSimulation() {
            // Snapshot mapping: P=PASS, F=FAIL, x=?
            let snapshot = {};
            let snapshotText = [];
            db.parameters.forEach(p => {
                const s = states[p];
                snapshot[p] = s === 'P' ? 'PASS' : (s === 'F' ? 'FAIL' : '?');
                if(s !== 'x') snapshotText.push(\`\${p}=\${snapshot[p]}\`);
            });

            const DEPTH_CAP = 6;
            const W_DATA = 0.7;
            const W_PRIOR = 0.3;

            let results = [];

            db.diseases.forEach(d => {
                let totalCond = 0;
                let matchedCond = 0;
                let logs = [];

                for (let param in d.reqs) {
                    let reqVal = d.reqs[param];
                    if (reqVal === 'PASS' || reqVal === 'FAIL') {
                        totalCond++;
                        if (snapshot[param] === reqVal) {
                            matchedCond++;
                            // Hitungan kasar matematika untuk tampilan log per item
                            let pointEstim = (100 * W_DATA) / Math.max(totalCond, 1); 
                            logs.push(\`<div class="log-good">✓ [\${param}] MATCH (\${reqVal})  (+\${pointEstim.toFixed(2)})</div>\`);
                        } else {
                            logs.push(\`<div class="log-bad">✗ [\${param}] MISS (Harusnya \${reqVal})</div>\`);
                        }
                    }
                }

                if (totalCond > 0) {
                    let matchRatio = (matchedCond / totalCond) * 100;
                    let depthWeight = Math.min(totalCond, DEPTH_CAP) / DEPTH_CAP;
                    let weightedScore = matchRatio * depthWeight;
                    
                    let prior = d.freq / db.totalFreq;
                    let priorScore = prior * 100;
                    
                    let finalScore = (weightedScore * W_DATA) + (priorScore * W_PRIOR);

                    results.push({
                        name: d.name,
                        score: finalScore,
                        basePrior: priorScore * W_PRIOR,
                        weighted: weightedScore * W_DATA,
                        freq: d.freq,
                        logs: logs
                    });
                }
            });

            // URUTKAN DESCENDING
            results.sort((a,b) => b.score - a.score);

            // RENDER JENDELA KANAN
            const rList = document.getElementById('resultsList');
            rList.innerHTML = '';
            
            // Render Progress Bars (Top 5)
            results.slice(0, 5).forEach(r => {
                rList.innerHTML += \`
                    <div class="result-item">
                        <div class="r-header">
                            <span>\${r.name}</span>
                            <span class="r-score">\${r.score.toFixed(1)}%</span>
                        </div>
                        <div class="bar-bg">
                            <div class="bar-fill" style="width: \${r.score}%"></div>
                        </div>
                    </div>
                \`;
            });

            // RENDER LOG DETAILS (Top 1)
            const logPanel = document.getElementById('logContent');
            if(results.length > 0) {
               const top = results[0];
               let logHTML = \`
                 <div style="margin-bottom:10px; color:#64748b;">
                   <b>SIMULATION START</b><br>
                   Active Observations: \${snapshotText.length > 0 ? snapshotText.join(', ') : 'None'}
                 </div>
                 <hr style="border:0; border-top:1px dashed #cbd5e1; margin:10px 0;">
                 <div class="log-title">TOP CANDIDATE ANALYSIS</div>
                 <div style="font-weight:bold; margin-bottom:5px;">"\${top.name}"</div>
                 <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                    <span>Base Prior (Freq: \${top.freq})</span>
                    <span>+\${top.basePrior.toFixed(2)}</span>
                 </div>
                 \${top.logs.join('')}
                 <hr style="border:0; border-top:1px dashed #cbd5e1; margin:10px 0;">
                 <div style="display:flex; justify-content:space-between; font-weight:bold;">
                    <span>TOTAL BAYESIAN CONFIDENCE:</span>
                    <span style="color:#4f46e5;">\${top.score.toFixed(2)}%</span>
                 </div>
               \`;
               logPanel.innerHTML = logHTML;
            } else {
               logPanel.innerHTML = "Tidak ada kalkulasi tersedia.";
            }
        }
      </script>
    </body>
    </html>
  `;
  const htmlOutput = HtmlService.createHtmlOutput(htmlString).setWidth(1100).setHeight(650);
  SpreadsheetApp.getUi().showModalDialog(htmlOutput, '🧪 BIOFLOC AI SIMULATOR');
}

/** 
 * Fungsi Backend untuk Simulator
 * Menarik susunan Matrix dari Spreadsheet 
 */
function getMatrixLogicForSimulator() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const mSheet = ss.getSheetByName("Matrix Diagnosis");
  if (!mSheet) return { error: "Matrix not found" };
  
  const lastCol = mSheet.getLastColumn();
  const lastRow = mSheet.getLastRow();
  if (lastCol < 4 || lastRow < 3) return { parameters: [], diseases: [], totalFreq: 1 };
  
  // Baca nama parameter dari header Matrix (Baris 1)
  const headers = mSheet.getRange(1, 4, 1, lastCol - 3).getValues()[0].map(h => h.toString().trim());
  const parameters = headers.filter(h => h && !h.toLowerCase().includes("cost"));
  
  // Baca isi Matrix (Mulai baris 3)
  const data = mSheet.getRange(3, 1, lastRow - 2, lastCol).getValues();
  let diseases = [];
  let totalFreq = 0;
  
  data.forEach(row => {
     let diag = row[2].toString().trim();
     if (!diag || diag.startsWith("COST") || diag === "-") return;
     let freq = parseFloat(row[1]) || 0;
     totalFreq += freq; // Hitung Prior
     
     let reqs = {};
     headers.forEach((h, i) => {
        if (!h.toLowerCase().includes("cost")) {
           reqs[h] = row[3 + i].toString().trim().toUpperCase();
        }
     });
     
     diseases.push({ name: diag, freq: freq, reqs: reqs });
  });
  
  return { parameters: parameters, diseases: diseases, totalFreq: totalFreq || 1 };
}
