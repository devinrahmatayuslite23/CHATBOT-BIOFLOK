"""
pH Drift Detector Module
========================
Modul untuk mendeteksi drift sensor pH dan memberikan alarm kalibrasi.

Fitur:
1. Deteksi drift gradual (slope analysis)
2. Deteksi sensor stuck (low variance)
3. Panduan troubleshooting terintegrasi
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import math

# Import from existing modules
try:
    from drive import water_tab
    from thresholds import SOP_THRESHOLDS
except ImportError:
    water_tab = None
    SOP_THRESHOLDS = {"ph": {"min": 6.5, "max": 8.5}}


# === CONFIGURATION ===

# pH Drift Detection Thresholds
PH_DRIFT_THRESHOLDS = {
    "drift_slope_threshold": 0.1,    # pH/hari - slope di atas ini = drift
    "stuck_variance_threshold": 0.01, # Variance di bawah ini = sensor stuck
    "noise_threshold": 0.5,           # Noise di atas ini = masalah koneksi
    "analysis_window_hours": 24,      # Window waktu untuk analisis
    "min_data_points": 10,            # Minimum data untuk analisis valid
}

# Physical limits for pH sensor
PH_PHYSICAL_LIMITS = {
    "min": 0.0,
    "max": 14.0,
}


# === TROUBLESHOOTING GUIDE ===

TROUBLESHOOTING_GUIDE = {
    "DRIFT_UP": {
        "symptom": "pH drift naik secara gradual",
        "possible_causes": [
            "Electrode aging (reference junction drying)",
            "Buildup on electrode surface",
            "Reference electrolyte depleting"
        ],
        "steps": [
            "1. Bersihkan probe dengan sikat lembut dan air destilasi",
            "2. Rendam probe dalam KCl 3M selama 2-4 jam",
            "3. Kalibrasi ulang dengan buffer pH 7.0 dan pH 4.0",
            "4. Jika masih drift, ganti electrode reference"
        ],
        "urgency": "MEDIUM"
    },
    "DRIFT_DOWN": {
        "symptom": "pH drift turun secara gradual",
        "possible_causes": [
            "Reference junction clogged",
            "Contamination on glass membrane",
            "Temperature compensation error"
        ],
        "steps": [
            "1. Rendam probe dalam warm water (40°C) selama 30 menit",
            "2. Bersihkan dengan HCl 0.1M selama 5-10 menit",
            "3. Bilas dengan air destilasi",
            "4. Kalibrasi ulang dengan buffer pH 7.0 dan pH 10.0"
        ],
        "urgency": "MEDIUM"
    },
    "SENSOR_STUCK": {
        "symptom": "Pembacaan pH tidak berubah (stuck)",
        "possible_causes": [
            "Electrode broken/cracked",
            "Cable disconnected or damaged",
            "ADC module failure"
        ],
        "steps": [
            "1. Cek koneksi kabel dari sensor ke ESP32",
            "2. Cek apakah probe tercelup dalam cairan",
            "3. Coba ukur dengan buffer pH 7.0 - harus menunjukkan 7.0±0.2",
            "4. Jika tidak berubah, ganti probe pH"
        ],
        "urgency": "HIGH"
    },
    "HIGH_NOISE": {
        "symptom": "Pembacaan pH sangat fluktuatif",
        "possible_causes": [
            "Electrical interference (grounding issue)",
            "Damaged cable shielding",
            "Moisture in connector"
        ],
        "steps": [
            "1. Cek grounding pada probe (pastikan terhubung ke ground)",
            "2. Jauhkan kabel sensor dari sumber EMI (motor, inverter)",
            "3. Cek apakah ada air/kelembaban di konektor",
            "4. Gunakan kabel shielded jika belum"
        ],
        "urgency": "MEDIUM"
    },
    "OUT_OF_RANGE": {
        "symptom": "Pembacaan pH di luar range fisik (< 0 atau > 14)",
        "possible_causes": [
            "Sensor completely broken",
            "ADC calibration error",
            "Wrong sensor connected"
        ],
        "steps": [
            "1. Pastikan sensor yang terhubung adalah sensor pH",
            "2. Cek wiring ke ADC (apakah terbalik?)",
            "3. Reset ADC module/ESP32",
            "4. Ganti sensor jika masih error"
        ],
        "urgency": "HIGH"
    },
    "NORMAL": {
        "symptom": "Sensor berfungsi normal",
        "possible_causes": [],
        "steps": [
            "Lakukan kalibrasi rutin setiap 2 minggu",
            "Simpan probe dalam KCl 3M saat tidak digunakan",
            "Hindari probe terkena udara terlalu lama"
        ],
        "urgency": "LOW"
    }
}


# === pH DATA ANALYSIS ===

def get_recent_ph_readings(hours: int = 24) -> List[Dict]:
    """
    Ambil data pH dari Water Quality tab dalam window waktu tertentu.
    """
    if not water_tab:
        return []
    
    try:
        all_data = water_tab.get_all_values()
        if len(all_data) < 2:
            return []
        
        readings = []
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Column indices (from WATER_HEADERS in drive.py)
        ts_idx = 0   # Timestamp
        ph_idx = 5   # pH column
        device_idx = 2
        
        for row in all_data[1:]:
            try:
                ts_str = row[ts_idx] if len(row) > ts_idx else ""
                if not ts_str:
                    continue
                
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                if ts < cutoff_time:
                    continue
                
                ph_str = row[ph_idx] if len(row) > ph_idx else ""
                if not ph_str or ph_str == "-":
                    continue
                
                ph_val = float(ph_str.replace(",", "."))
                device = row[device_idx] if len(row) > device_idx else "Unknown"
                
                readings.append({
                    "timestamp": ts,
                    "ph_value": ph_val,
                    "device": device
                })
            except (ValueError, IndexError):
                continue
        
        readings.sort(key=lambda x: x["timestamp"])
        return readings
        
    except Exception as e:
        print(f"⚠️ Error getting pH readings: {e}")
        return []


def calculate_slope(readings: List[Dict]) -> Optional[float]:
    """
    Hitung slope pH menggunakan linear regression.
    
    Returns:
        Slope dalam pH/hari. Positif = naik, Negatif = turun.
    """
    if len(readings) < 2:
        return None
    
    n = len(readings)
    t0 = readings[0]["timestamp"]
    
    # Convert to days
    x = [(r["timestamp"] - t0).total_seconds() / 86400 for r in readings]  # days
    y = [r["ph_value"] for r in readings]
    
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi ** 2 for xi in x)
    
    denominator = n * sum_x2 - sum_x ** 2
    if denominator == 0:
        return 0.0
    
    slope = (n * sum_xy - sum_x * sum_y) / denominator
    return round(slope, 4)


def calculate_variance(readings: List[Dict]) -> float:
    """
    Hitung variance dari pembacaan pH.
    """
    if len(readings) < 2:
        return 0.0
    
    values = [r["ph_value"] for r in readings]
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return round(variance, 4)


def detect_drift(readings: List[Dict]) -> Dict:
    """
    Deteksi pH drift dengan analisis slope dan variance.
    
    Returns:
        Dict dengan drift_type, severity, dan details
    """
    if len(readings) < PH_DRIFT_THRESHOLDS["min_data_points"]:
        return {
            "drift_type": "INSUFFICIENT_DATA",
            "severity": "UNKNOWN",
            "message": f"Data tidak cukup (perlu minimal {PH_DRIFT_THRESHOLDS['min_data_points']} data points)"
        }
    
    # Check for out-of-range values
    ph_values = [r["ph_value"] for r in readings]
    if any(v < PH_PHYSICAL_LIMITS["min"] or v > PH_PHYSICAL_LIMITS["max"] for v in ph_values):
        return {
            "drift_type": "OUT_OF_RANGE",
            "severity": "HIGH",
            "message": "Terdeteksi pembacaan di luar range fisik pH (0-14)"
        }
    
    slope = calculate_slope(readings)
    variance = calculate_variance(readings)
    current_ph = readings[-1]["ph_value"]
    
    # Check for stuck sensor (very low variance)
    if variance < PH_DRIFT_THRESHOLDS["stuck_variance_threshold"]:
        return {
            "drift_type": "SENSOR_STUCK",
            "severity": "HIGH",
            "slope": slope,
            "variance": variance,
            "current_ph": current_ph,
            "message": f"Sensor mungkin stuck! Variance sangat rendah: {variance}"
        }
    
    # Check for high noise
    if variance > PH_DRIFT_THRESHOLDS["noise_threshold"]:
        return {
            "drift_type": "HIGH_NOISE",
            "severity": "MEDIUM",
            "slope": slope,
            "variance": variance,
            "current_ph": current_ph,
            "message": f"Noise tinggi terdeteksi! Variance: {variance}"
        }
    
    # Check for drift
    if abs(slope) > PH_DRIFT_THRESHOLDS["drift_slope_threshold"]:
        drift_direction = "DRIFT_UP" if slope > 0 else "DRIFT_DOWN"
        return {
            "drift_type": drift_direction,
            "severity": "MEDIUM",
            "slope": slope,
            "variance": variance,
            "current_ph": current_ph,
            "message": f"Drift terdeteksi! Rate: {slope} pH/hari"
        }
    
    # Normal operation
    return {
        "drift_type": "NORMAL",
        "severity": "LOW",
        "slope": slope,
        "variance": variance,
        "current_ph": current_ph,
        "message": "Sensor berfungsi normal"
    }


# === CALIBRATION STATUS ===

def get_calibration_status() -> Dict:
    """
    Cek status kalibrasi sensor pH dan generate rekomendasi.
    """
    readings = get_recent_ph_readings(hours=PH_DRIFT_THRESHOLDS["analysis_window_hours"])
    drift_analysis = detect_drift(readings)
    
    # Get troubleshooting guide
    drift_type = drift_analysis.get("drift_type", "NORMAL")
    guide = TROUBLESHOOTING_GUIDE.get(drift_type, TROUBLESHOOTING_GUIDE["NORMAL"])
    
    needs_calibration = drift_type not in ["NORMAL", "INSUFFICIENT_DATA"]
    
    return {
        "needs_calibration": needs_calibration,
        "drift_analysis": drift_analysis,
        "troubleshooting": guide,
        "data_points": len(readings),
        "analysis_window_hours": PH_DRIFT_THRESHOLDS["analysis_window_hours"]
    }


def format_calibration_response(lang: str = "id") -> str:
    """
    Format response untuk command 'kalibrasi' di chatbot.
    """
    status = get_calibration_status()
    drift = status["drift_analysis"]
    guide = status["troubleshooting"]
    
    if drift["drift_type"] == "INSUFFICIENT_DATA":
        return f"""📊 Status Kalibrasi Sensor pH

⚠️ {drift['message']}

Pastikan sensor mengirim data secara teratur untuk analisis drift."""
    
    urgency_emoji = {
        "HIGH": "🚨",
        "MEDIUM": "⚠️",
        "LOW": "✅"
    }
    
    emoji = urgency_emoji.get(guide["urgency"], "ℹ️")
    
    message = f"""📊 Status Kalibrasi Sensor pH

{emoji} Status: {drift['drift_type']}
• pH Saat Ini: {drift.get('current_ph', 'N/A')}
• Drift Rate: {drift.get('slope', 'N/A')} pH/hari
• Variance: {drift.get('variance', 'N/A')}

💡 {drift['message']}
"""
    
    if status["needs_calibration"]:
        message += f"""
🔧 Langkah Troubleshooting:
{chr(10).join(guide['steps'])}
"""
    
    return message


def format_troubleshoot_response(issue_type: Optional[str] = None, lang: str = "id") -> str:
    """
    Format response untuk command 'troubleshoot ph' di chatbot.
    
    Args:
        issue_type: Jenis masalah spesifik (optional). Jika None, tampilkan semua.
    """
    if issue_type:
        issue_key = issue_type.upper().replace(" ", "_")
        if issue_key in TROUBLESHOOTING_GUIDE:
            guide = TROUBLESHOOTING_GUIDE[issue_key]
            return f"""🔧 Troubleshooting: {guide['symptom']}

Kemungkinan Penyebab:
{chr(10).join('• ' + c for c in guide['possible_causes'])}

Langkah Perbaikan:
{chr(10).join(guide['steps'])}

Urgensi: {guide['urgency']}"""
    
    # Show all issues summary
    message = """🔧 Panduan Troubleshooting Sensor pH

Ketik 'troubleshoot [masalah]' untuk detail:

1. DRIFT_UP - pH naik gradual
2. DRIFT_DOWN - pH turun gradual  
3. SENSOR_STUCK - Pembacaan tidak berubah
4. HIGH_NOISE - Pembacaan fluktuatif
5. OUT_OF_RANGE - Pembacaan error

Contoh: 'troubleshoot drift_up'"""
    
    return message


# === ALERT SYSTEM ===

def check_ph_alerts() -> Optional[Dict]:
    """
    Cek apakah ada alert pH yang perlu dikirim.
    
    Returns:
        Dict dengan alert info jika ada, None jika tidak ada alert.
    """
    status = get_calibration_status()
    
    if not status["needs_calibration"]:
        return None
    
    drift = status["drift_analysis"]
    guide = status["troubleshooting"]
    
    return {
        "alert_type": drift["drift_type"],
        "severity": guide["urgency"],
        "message": format_calibration_response(),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


if __name__ == "__main__":
    # Test module
    print("=== pH Drift Detector Test ===")
    print(format_calibration_response())
    print("\n" + "="*50 + "\n")
    print(format_troubleshoot_response())
