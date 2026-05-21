const fs = require('fs');

// 1. Load the backend Code from DiagnosticTree.gs
const treeScript = fs.readFileSync('../Google_Apps_Script/DiagnosticTree.gs', 'utf8');
eval(treeScript); // Load functions into global scope

// 2. Read the CSV
const csv = fs.readFileSync('Matrix_Diagnosis.csv', 'utf8');
const lines = csv.split('\n').map(l => l.trim()).filter(l => l.length > 0);

// Line 1: Index, Frequency, Diagnosis, Low DO, High Do, Low Pump...
const headersRaw = lines[0].split(',').slice(3); // Feature names
const headers = headersRaw.map(h => h.replace(/^["']|["']$/g, '').trim());

// Line 2: Costs
const costRow = lines[1].split(',').slice(3).map(c => parseFloat(c) || 1.0);
const features = headers.map((name, idx) => ({ idx, name, cost: costRow[idx] }));

// Load items starting from line 2
const items = [];
for (let i = 2; i < lines.length; i++) {
  const row = lines[i].split(',').map(c => c.trim().replace(/^["']|["']$/g, ''));
  if (row.length < 3) continue;
  
  const freq = parseInt(row[1]) || 1;
  const decision = row[2];
  
  const vals = [];
  for (let k = 3; k < row.length; k++) {
    const valStr = row[k].toUpperCase();
    if (valStr === '1' || valStr === 'PASS' || valStr === 'TRUE') vals.push(1);
    else if (valStr === '0' || valStr === '2' || valStr === 'FAIL' || valStr === 'FALSE' || valStr === '-1') vals.push(0);
    else vals.push(null);
  }
  
  items.push({ freq, decision, vals });
}

// 3. Build tree for all 3 algos
function printTree(node, indent) {
  indent = indent || "";
  if (!node.feature) {
    return indent + "LEAF: " + (node.decision || "Unknown") + "\n";
  }
  let out = indent + "[" + node.feature + "]\n";
  if (node.pass) out += indent + "  PASS ->\n" + printTree(node.pass, indent + "    ");
  if (node.fail) out += indent + "  FAIL ->\n" + printTree(node.fail, indent + "    ");
  return out;
}

const algos = ['id3', 'voi', 'eff'];
const names = { id3: 'ID3 Speed Max', voi: 'VOI Cost Efficient', eff: 'Efficiency Gain2/Cost DEFAULT' };

for (let a = 0; a < algos.length; a++) {
  const algo = algos[a];
  const itemsCopy = items.map(function(i) { return { freq: i.freq, decision: i.decision, vals: i.vals.slice() }; });
  const featuresCopy = features.map(function(f) { return { idx: f.idx, name: f.name, cost: f.cost }; });
  const tree = buildDiagnosisTree(itemsCopy, featuresCopy, 0, 0, "", algo, 6);
  const txt = "=== " + names[algo] + " ===\nROOT: " + (tree.feature || tree.decision) + "\n\n" + printTree(tree, "");
  fs.writeFileSync("tree_" + algo + ".txt", txt);
  console.log(names[algo] + ": ROOT = " + (tree.feature || tree.decision));
}
