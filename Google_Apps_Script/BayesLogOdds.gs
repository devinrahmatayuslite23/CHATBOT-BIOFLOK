/**
 * 🧪 BAYESIAN LOG-ODDS ENGINE
 * ------------------------------------------------------------------------
 * Upgraded from the old parallel scoring system.
 * Uses Log-Odds updates with False Alarm tolerance.
 * ------------------------------------------------------------------------
 */

function runBayesLogOdds(snapshot, matrixData, falseAlarmRate = 0.05) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const matrix = matrixData || getMatrixForTree(ss); // Reuse fetch logic
  
  const results = [];
  
  // False Alarm tolerance parameters
  const far = falseAlarmRate;
  const t_rate = 1 - far;
  
  matrix.items.forEach(disease => {
    // Initial Log-Odds based on Frequency (Prior)
    // We normalize frequency to avoid infinity
    const totalFreq = matrix.items.reduce((s, i) => s + i.freq, 0);
    const prior = disease.freq / totalFreq;
    let logOdds = Math.log(prior / (1 - prior));

    // Update with each observation in snapshot
    matrix.headers.forEach((hName, hIdx) => {
      const observation = snapshot[hName];
      if (observation === undefined || observation === "N/A" || observation === null) return;

      const target = disease.vals[hIdx];
      const match = (observation === "PASS" ? 1 : 0) === target;

      // Likelihood Ratio update
      // If observation matches definition: weight = True Positive / False Positive
      // If observation doesn't match: weight = False Negative / True Negative
      let weight = 1;
      if (match) {
        weight = t_rate / far;
      } else {
        weight = far / t_rate;
      }

      logOdds += Math.log(weight);
    });

    // Back to probability
    const finalProb = 1 / (1 + Math.exp(-logOdds));
    results.push({
      diagnosis: disease.decision,
      probability: finalProb,
      freq: disease.freq
    });
  });

  // Sort by probability DESC
  return results.sort((a, b) => b.probability - a.probability);
}
