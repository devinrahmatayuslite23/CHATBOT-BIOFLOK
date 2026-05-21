/**
 * 🌳 DIAGNOSTIC TREE ENGINE
 * ------------------------------------------------------------------------
 * 1:1 Port dari diagnostic_optimizer.html (Client Tools)
 * Semua formula, stop-condition, dan pair-exclusion IDENTIK.
 * ------------------------------------------------------------------------
 */

function getMatrixForTree(ss) {
  const sheet = ss.getSheetByName("Matrix Diagnosis");
  const data = sheet.getDataRange().getValues();
  
  const headers = [];
  const costs = [];
  const caraCek = [];
  
  for(let i=3; i<data[0].length; i++) {
    headers.push(data[0][i].toString().trim());
    costs.push(parseFloat(data[1][i]) || 1);
    caraCek.push(data[2][i] ? data[2][i].toString() : "");
  }
  
  const items = [];
  for (let i = 3; i < data.length; i++) {
    const row = data[i];
    if (!row[2] || row[2].toString().trim().toUpperCase() === "COSTS:") continue;
    
    const vals = [];
    for(let k=3; k<row.length; k++) {
       const valStr = row[k].toString().trim().toUpperCase();
       if (valStr === '1' || valStr === 'PASS' || valStr === 'TRUE') vals.push(1);
       else if (valStr === '0' || valStr === '2' || valStr === 'FAIL' || valStr === 'FALSE' || valStr === '-1') vals.push(0);
       else vals.push(null);
    }
    
    items.push({
      decision: row[2].toString().trim(),
      vals: vals,
      freq: parseFloat(row[1]) || 1 
    });
  }
  
  // ── Pair detection (identik dengan detectHeaderPairs() di client) ──
  const headerPairs = {};
  const pairMap = {};
  headers.forEach(function(h, i) {
    const match = h.match(/^(Low|High)\s+(.*)$/i);
    if (match) {
      const type = match[1].toLowerCase();
      const suffix = match[2].toLowerCase().trim();
      if (!pairMap[suffix]) pairMap[suffix] = {};
      if (type === 'low') pairMap[suffix].low = i;
      else if (type === 'high') pairMap[suffix].high = i;
    }
  });
  for (const suffix in pairMap) {
    if (pairMap[suffix].low !== undefined && pairMap[suffix].high !== undefined) {
      headerPairs[pairMap[suffix].low] = pairMap[suffix].high;
      headerPairs[pairMap[suffix].high] = pairMap[suffix].low;
    }
  }
  
  return { headers, costs, caraCek, items, headerPairs };
}

// ── Freq & Distribution (identik dgn client: freq || 0, freqWeight = 1.0) ──
function _getEffectiveFreq(freq) { return Math.pow(freq || 0, 1.0); }
function _getTotalFreq(items) { return items.reduce((sum, item) => sum + _getEffectiveFreq(item.freq), 0); }
function _getWeightedDistribution(items) { 
  const c = {}; 
  items.forEach(i => { const f = _getEffectiveFreq(i.freq); c[i.decision] = (c[i.decision] || 0) + f; }); 
  return c; 
}

// ── Entropy (identik dgn client) ──
function calculateEntropy(items) { 
  const t = _getTotalFreq(items); 
  if (t === 0) return 0; 
  const c = _getWeightedDistribution(items); 
  let e = 0; 
  for (let k in c) { 
    const p = c[k] / t; 
    if (p > 0) e -= p * Math.log2(p); 
  } 
  return e; 
}

// ── Cost-Sensitive Gain (identik dgn client: costWeight=1.0, confidenceWeight=0.0) ──
function calculateCostSensitiveGain(items, fIdx, fName, cost, algo) {
  const tW = _getTotalFreq(items); 
  const cH = calculateEntropy(items);
  
  const pass = items.filter(i => i.vals[fIdx] === 1); 
  const fail = items.filter(i => i.vals[fIdx] === 0); 
  
  if (pass.length === 0 && fail.length === 0) return { score: -1, nullsTo: 0 };
  
  const calcGain = (pSet, fSet) => {
    let wH = 0; 
    if (tW > 0) {
       wH = ((_getTotalFreq(pSet) / tW) * calculateEntropy(pSet)) + ((_getTotalFreq(fSet) / tW) * calculateEntropy(fSet));
    }
    return Math.max(0, cH - wH);
  };
  
  const nulls = items.filter(i => i.vals[fIdx] === null);
  const gA = calcGain([...pass, ...nulls], fail); 
  const gB = calcGain(pass, [...fail, ...nulls]);
  const rG = Math.max(gA, gB); 
  
  const effCost = Math.max(0.01, cost);
  // confidenceWeight = 0.0 → confMult selalu 1.0 (identik dgn client default)
  const confMult = 1.0; 
  
  let eff;
  if (algo === 'id3') eff = rG * confMult;
  else if (algo === 'voi') eff = (rG / effCost) * confMult;
  else eff = ((rG * rG) / Math.pow(effCost, 1.0)) * confMult; // costWeight = 1.0
  
  return { score: eff, rawGain: rG, nullsTo: gA >= gB ? 1 : 0 };
}

/**
 * Build Tree — IDENTIK dengan buildTree() di diagnostic_optimizer.html
 * 
 * Stop condition client: decs.length === 1 || feats.length === 0
 * (TIDAK ada maxDepth — pohon tumbuh sampai leaf murni)
 * 
 * Pair exclusion: headerPairs[bestF] → filter out pair index
 */
function buildDiagnosisTree(items, featureIdxs, headerPairs, headers, costs, algo, depth, cost, path) {
  const counts = _getWeightedDistribution(items); 
  const decs = Object.keys(counts);
  
  // ── Stop condition (identik dgn client) ──
  // Client: if (decs.length === 1 || feats.length === 0)
  if (decs.length === 1 || featureIdxs.length === 0) {
    let winner = decs[0]; let maxF = -1; 
    for (let d in counts) if (counts[d] > maxF) { maxF = counts[d]; winner = d; }
    return { decision: winner, path: path || [] };
  }
  
  let maxS = -Infinity; 
  let bestF = -1; 
  let bestN = 0;
  
  featureIdxs.forEach(function(idx) {
    const r = calculateCostSensitiveGain(items, idx, headers[idx], costs[idx], algo);
    if (r.score > maxS) { 
      maxS = r.score; 
      bestF = idx; 
      bestN = r.nullsTo; 
    }
  });
  
  // ── No valid split (identik dgn client: bestF === -1 || maxS <= 0.000001) ──
  if (bestF === -1 || maxS <= 0.000001) {
    let winner = decs[0]; let maxF = -1; 
    for (let d in counts) if (counts[d] > maxF) { maxF = counts[d]; winner = d; }
    return { decision: winner, path: path || [] };
  }
  
  const fName = headers[bestF];
  
  // ── Pair exclusion (identik dgn client: headerPairs[bestF]) ──
  const pair = headerPairs[bestF];
  let nextF = featureIdxs.filter(function(f) { return f !== bestF; });
  if (pair !== undefined) nextF = nextF.filter(function(f) { return f !== pair; });
  
  // ── Null-routing (identik dgn client) ──
  const passI = items.filter(function(i) { return i.vals[bestF] === 1 || (i.vals[bestF] === null && bestN === 1); });
  const failI = items.filter(function(i) { return i.vals[bestF] === 0 || (i.vals[bestF] === null && bestN === 0); });
  
  const majorityClass = (function() { let w = decs[0]; let m = -1; for (let d in counts) if (counts[d] > m) { m = counts[d]; w = d; } return w; })();
  
  return {
    feature: fName,
    decision: majorityClass,
    pass: passI.length > 0 ? buildDiagnosisTree(passI, nextF, headerPairs, headers, costs, algo, depth + 1, cost + costs[bestF], [...(path || []), { feature: fName, val: 1 }]) : { decision: majorityClass, path: [...(path || []), { feature: fName, val: 1 }] },
    fail: failI.length > 0 ? buildDiagnosisTree(failI, nextF, headerPairs, headers, costs, algo, depth + 1, cost + costs[bestF], [...(path || []), { feature: fName, val: 0 }]) : { decision: majorityClass, path: [...(path || []), { feature: fName, val: 0 }] }
  };
}

/**
 * Main Entry for Tree Traversal
 * Mengembalikan path persis sesuai dengan jejak belokan Tree.
 */
function traverseTree(tree, evalResult) {
  let current = tree;
  const pathLog = [];
  
  while (current && current.feature) {
    const key = current.feature;
    const dat = evalResult.dataValues[key];
    const status = evalResult.snapshot[key];
    
    if (status === undefined || status === null || status === "N/A") {
      pathLog.push(key + " → N/A (Data Kosong / Basi)");
      break; 
    }
    if (!dat) {
      pathLog.push(key + " → N/A (Data Kosong / Tidak Tercatat)");
      break; 
    }
    
    pathLog.push(key + " → " + status + " " + (dat.desc || dat.mathStr));
    current = status === "PASS" ? current.pass : current.fail;
  }
  
  return {
    result: current ? current.decision : "Unknown",
    path: pathLog
  };
}

/**
 * 🎨 Export Peta Pohon ke Format Mermaid JS untuk UI
 * Berjalan rekursif memetakan seluk beluk percabangan
 */
function exportTreeToMermaid(treeNode) {
  let mermaidStr = "graph TD\n";
  let counter = 0;
  
  function traverse(node, parentId, edgeLabel, currentDepth) {
     if(currentDepth > 10) {
         if (parentId) mermaidStr += `  ${parentId} -- "${edgeLabel}" --> N_trunc${counter++}["..."]\n`;
         return;
     }
     if(!node) return;
     
     const myId = "N" + counter++;
     let label = node.feature ? node.feature : (node.decision ? node.decision : "Unknown");
     
     label = label.replace(/"/g, "'").replace(/[\[\]]/g, "");
     
     if (node.feature) {
         mermaidStr += `  ${myId}["🎛️ ${label}?"]\n`;
         mermaidStr += `  style ${myId} fill:#f8fafc,stroke:#cbd5e1,color:#334155,stroke-width:2px\n`;
     } else {
         mermaidStr += `  ${myId}("🩺 ${label}")\n`;
         mermaidStr += `  style ${myId} fill:#eff6ff,stroke:#60a5fa,color:#1e40af,stroke-width:2px,stroke-dasharray: 5 5\n`;
     }
     
     if (parentId) {
         mermaidStr += `  ${parentId} -- "${edgeLabel}" --> ${myId}\n`;
     }
     
     if (node.feature) {
         traverse(node.pass, myId, "PASS", currentDepth + 1);
         traverse(node.fail, myId, "FAIL", currentDepth + 1);
     }
  }
  
  traverse(treeNode, null, "", 0);
  return mermaidStr;
}
