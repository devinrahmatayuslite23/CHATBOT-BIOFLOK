/**
 * =========================================================================
 * 💨 DO ANALYZER ENGINE (GOOGLE APPS SCRIPT EDITION)
 * =========================================================================
 * Mengadopsi logika do_analyzer.py untuk menjalankan math regresi linear
 * langsung di server Google. Super ringan dan instan!
 */

const DEFAULT_POND_CONFIG = {
    volume_m3: 1000,
    fish_count: 8000,
    target_do: 6.0,
    aerator_efficiency: 0.15,
    safety_factor: 1.2
};

const DO_DROP_THRESHOLDS = {
    critical_drop_rate: 0.5,
    warning_drop_rate: 0.3,
    critical_level: 3.0,
    warning_level: 4.0,
    analysis_window_hours: 24
};

function do_analyzeTrend(ss) {
    const sheet = ss.getSheetByName("Water Quality");
    if (!sheet) return { status: "NO_DATA", recommendation: "Tab Water Quality tidak ditemukan." };
    
    const cutoff = new Date(new Date().getTime() - (DO_DROP_THRESHOLDS.analysis_window_hours * 60 * 60 * 1000));
    const rows = sheet.getDataRange().getValues();
    let readings = [];
    
    for (let i = 1; i < rows.length; i++) {
        let tsStr = rows[i][0];
        let doVal = rows[i][3];
        if (!tsStr || doVal === "" || doVal === "-") continue;
        
        let ts = new Date(tsStr);
        if (ts.toString() === "Invalid Date") continue;
        
        if (ts >= cutoff) {
            readings.push({
                timestamp: ts,
                do_value: parseFloat(doVal.toString().replace(",", ".")),
                device: rows[i][2] || "Unknown"
            });
        }
    }
    
    readings.sort((a,b) => a.timestamp - b.timestamp);
    
    // Fallback if empty in window
    if (readings.length === 0) {
        for (let i = rows.length - 1; i >= 1; i--) {
            let tsStr = rows[i][0];
            let doVal = rows[i][3];
            if (!tsStr || doVal === "" || doVal === "-") continue;
            let ts = new Date(tsStr);
            if (ts.toString() !== "Invalid Date") {
               readings.push({
                  timestamp: ts,
                  do_value: parseFloat(doVal.toString().replace(",", ".")),
                  device: rows[i][2] || "Unknown"
               });
               break; // ambil 1 saja yang terakhir
            }
        }
        if (readings.length === 0) return { status: "NO_DATA", recommendation: "Belum ada data DO di Spreadsheet." };
    }
    
    const current_do = readings[readings.length - 1].do_value;
    const data_timestamp = readings[readings.length - 1].timestamp;
    
    // slope calculation if >1 data point
    let drop_rate = null;
    if (readings.length >= 2) {
        let n = readings.length;
        let t0 = readings[0].timestamp.getTime();
        let x = readings.map(r => (r.timestamp.getTime() - t0) / 3600000);
        let y = readings.map(r => r.do_value);
        
        let sum_x = x.reduce((a,b)=>a+b, 0);
        let sum_y = y.reduce((a,b)=>a+b, 0);
        let sum_xy = x.reduce((sum, xi, i) => sum + xi * y[i], 0);
        let sum_x2 = x.reduce((sum, xi) => sum + xi * xi, 0);
        
        let denominator = n * sum_x2 - sum_x * sum_x;
        if (denominator !== 0) {
            drop_rate = (n * sum_xy - sum_x * sum_y) / denominator;
        } else {
            drop_rate = 0.0;
        }
    }
    
    let alert_level = "NORMAL";
    let recommendation = "Kondisi DO normal.";
    
    if (current_do <= DO_DROP_THRESHOLDS.critical_level) {
        alert_level = "CRITICAL";
        recommendation = `⚠️ KRITIS! DO sangat rendah (${current_do} mg/L). Aktifkan aerasi darurat segera!`;
    } else if (current_do <= DO_DROP_THRESHOLDS.warning_level) {
        alert_level = "WARNING";
        recommendation = `⚡ DO rendah (${current_do} mg/L). Tingkatkan aerasi.`;
    }
    
    if (drop_rate !== null && drop_rate < 0) {
        let abs_rate = Math.abs(drop_rate);
        if (abs_rate >= DO_DROP_THRESHOLDS.critical_drop_rate) {
            alert_level = "CRITICAL";
            recommendation = `⚠️ KRITIS! DO turun cepat (${abs_rate.toFixed(3)} mg/L/jam). Cek aerator dan kurangi pakan!`;
        } else if (abs_rate >= DO_DROP_THRESHOLDS.warning_drop_rate) {
            if (alert_level !== "CRITICAL") alert_level = "WARNING";
            recommendation = `⚡ DO menurun (${abs_rate.toFixed(3)} mg/L/jam). Monitor ketat dan siapkan aerasi tambahan.`;
        }
    }
    
    return {
        status: "ANALYZED",
        current_do: current_do,
        drop_rate: drop_rate !== null ? parseFloat(drop_rate.toFixed(3)) : null,
        alert_level: alert_level,
        recommendation: recommendation,
        data_points: readings.length,
        time_range_hours: DO_DROP_THRESHOLDS.analysis_window_hours,
        data_timestamp: Utilities.formatDate(data_timestamp, Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm:ss"),
        is_fallback: readings.length === 1
    };
}

function do_calculateOxygenDemand(current_do, config) {
    const target_do = config.target_do || 6.0;
    const do_deficit = Math.max(0, target_do - current_do);
    const oxygen_deficit_kg = do_deficit * (config.volume_m3 || 1000) * 0.001;
    const hourly_respiration_kg = ((config.fish_count || 8000) * (config.avg_weight_g || 100) / 1000) * 0.0003;
    const total_o2_need_kg = (oxygen_deficit_kg + hourly_respiration_kg) * (config.safety_factor || 1.2);
    const recommended_aerator_hp = total_o2_need_kg / 0.5;
    
    return {
        current_do: current_do,
        target_do: target_do,
        oxygen_deficit_kg: parseFloat(oxygen_deficit_kg.toFixed(3)),
        hourly_respiration_kg: parseFloat(hourly_respiration_kg.toFixed(3)),
        total_o2_need_kg: parseFloat(total_o2_need_kg.toFixed(3)),
        recommended_aerator_hp: parseFloat(recommended_aerator_hp.toFixed(2))
    };
}

function getAerationRecommendationApi() {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const trend = do_analyzeTrend(ss);
    
    if (trend.status === "NO_DATA" || trend.current_do == null) {
        return { trend: trend, aeration: null, message: "Tidak dapat menghitung kebutuhan aerasi tanpa data DO." };
    }
    
    const aeration = do_calculateOxygenDemand(trend.current_do, DEFAULT_POND_CONFIG);
    return { trend: trend, aeration: aeration, message: "Success" };
}
