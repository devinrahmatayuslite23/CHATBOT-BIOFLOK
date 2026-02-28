"""
DO (Dissolved Oxygen) Analyzer Module
=====================================
Modul untuk mendeteksi drop DO dan menghitung kebutuhan aerasi ideal.

Fitur:
1. Deteksi rate of change DO (mg/L per jam)
2. Threshold-based alert untuk DO drop
3. Kalkulasi aerasi ideal berdasarkan volume kolam dan jumlah ikan
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import gspread

# Import from existing modules
try:
    from drive import water_tab
    from thresholds import SOP_THRESHOLDS
except ImportError:
    water_tab = None
    SOP_THRESHOLDS = {"do": {"min": 5.0, "max": 6.5}}


# === CONFIGURATION ===

# Default pond parameters (can be overridden via config)
DEFAULT_POND_CONFIG = {
    "volume_m3": 1000,          # Volume kolam dalam m³
    "fish_count": 8000,         # Jumlah ikan
    "target_do": 6.0,           # Target DO (mg/L)
    "aerator_efficiency": 0.15, # Efisiensi transfer oksigen (15%)
    "safety_factor": 1.2,       # Safety factor untuk kalkulasi
}

# DO Drop Detection Thresholds
DO_DROP_THRESHOLDS = {
    "critical_drop_rate": 0.5,    # mg/L per jam (drop kritis)
    "warning_drop_rate": 0.3,     # mg/L per jam (warning)
    "critical_level": 3.0,        # mg/L (level kritis)
    "warning_level": 4.0,         # mg/L (warning level)
    "analysis_window_hours": 24,   # Window waktu untuk analisis trend (Extended for Demo)
}


# === DO TREND ANALYSIS ===

def get_recent_do_readings(hours: int = 4, fallback: bool = False) -> List[Dict]:
    """
    Ambil data DO dari Water Quality tab dalam window waktu tertentu.
    
    Args:
        hours: Window waktu dalam jam
        fallback: Jika True, ambil SEMUA data tanpa filter waktu (fallback mode)
    
    Returns:
        List of dict dengan keys: timestamp, do_value, device
    """
    if not water_tab:
        return []
    
    try:
        all_data = water_tab.get_all_values()
        if len(all_data) < 2:
            return []
        
        readings = []
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Column indices
        ts_idx = 0  # Timestamp
        do_idx = 3  # DO column (index 3)
        device_idx = 2  # Device
        
        for row in all_data[1:]:
            try:
                ts_str = row[ts_idx] if len(row) > ts_idx else ""
                if not ts_str:
                    continue
                
                # Robust Timestamp Parsing
                ts = None
                formats = [
                    "%Y-%m-%d %H:%M:%S", 
                    "%d/%m/%Y %H:%M:%S", 
                    "%m/%d/%Y %H:%M:%S",
                    "%Y/%m/%d %H:%M:%S"
                ]
                for fmt in formats:
                    try:
                        ts = datetime.strptime(ts_str, fmt)
                        break
                    except ValueError:
                        continue
                
                if not ts:
                    print(f"⚠️ Failed to parse TS: {ts_str}")
                    continue

                # Filter waktu hanya jika BUKAN fallback mode
                if not fallback and ts < cutoff_time:
                    continue
                
                do_str = row[do_idx] if len(row) > do_idx else ""
                if not do_str or do_str == "-":
                    continue
                
                do_val = float(do_str.replace(",", "."))
                device = row[device_idx] if len(row) > device_idx else "Unknown"
                
                readings.append({
                    "timestamp": ts,
                    "do_value": do_val,
                    "device": device
                })
            except (ValueError, IndexError):
                continue
        
        readings.sort(key=lambda x: x["timestamp"])
        return readings
        
    except Exception as e:
        print(f"⚠️ Error getting DO readings: {e}")
        return []



def calculate_do_drop_rate(readings: List[Dict]) -> Optional[float]:
    """
    Hitung rate of change DO (mg/L per jam) menggunakan linear regression sederhana.
    
    Returns:
        Slope dalam mg/L per jam. Negatif = DO menurun.
    """
    if len(readings) < 2:
        return None
    
    # Simple linear regression
    n = len(readings)
    
    # Convert timestamps to hours from first reading
    t0 = readings[0]["timestamp"]
    x = [(r["timestamp"] - t0).total_seconds() / 3600 for r in readings]  # hours
    y = [r["do_value"] for r in readings]
    
    # Calculate slope: (n*Σxy - Σx*Σy) / (n*Σx² - (Σx)²)
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi ** 2 for xi in x)
    
    denominator = n * sum_x2 - sum_x ** 2
    if denominator == 0:
        return 0.0
    
    slope = (n * sum_xy - sum_x * sum_y) / denominator
    return round(slope, 3)


def analyze_do_trend() -> Dict:
    """
    Analisis lengkap trend DO dan deteksi drop.
    Jika tidak ada data dalam window 24 jam, otomatis fallback ke data DO terakhir yang ada.
    
    Returns:
        Dict dengan keys: status, current_do, drop_rate, alert_level, recommendation,
                          data_timestamp, is_fallback
    """
    window_hours = DO_DROP_THRESHOLDS["analysis_window_hours"]
    readings = get_recent_do_readings(hours=window_hours)
    is_fallback = False

    # [OPSI B] Fallback: jika tidak ada data dalam window, ambil data terakhir yang ada
    if not readings:
        print(f"⚠️ Tidak ada data DO dalam {window_hours} jam, mencoba fallback ke data terakhir...")
        readings = get_recent_do_readings(fallback=True)
        if readings:
            is_fallback = True
            print(f"✅ Fallback berhasil, ditemukan {len(readings)} data historis.")
    
    if not readings:
        return {
            "status": "NO_DATA",
            "current_do": None,
            "drop_rate": None,
            "alert_level": "UNKNOWN",
            "recommendation": "Tidak ada data DO tersedia. Pastikan sensor terhubung.",
            "data_timestamp": None,
            "is_fallback": False
        }
    
    current_do = readings[-1]["do_value"]
    data_timestamp = readings[-1]["timestamp"]  # Timestamp data DO terbaru
    drop_rate = calculate_do_drop_rate(readings)
    
    # Determine alert level
    alert_level = "NORMAL"
    recommendation = "Kondisi DO normal."
    
    if current_do <= DO_DROP_THRESHOLDS["critical_level"]:
        alert_level = "CRITICAL"
        recommendation = f"⚠️ KRITIS! DO sangat rendah ({current_do} mg/L). Aktifkan aerasi darurat segera!"
    elif current_do <= DO_DROP_THRESHOLDS["warning_level"]:
        alert_level = "WARNING"
        recommendation = f"⚡ DO rendah ({current_do} mg/L). Tingkatkan aerasi."
    
    if drop_rate is not None and drop_rate < 0:
        abs_rate = abs(drop_rate)
        if abs_rate >= DO_DROP_THRESHOLDS["critical_drop_rate"]:
            alert_level = "CRITICAL"
            recommendation = f"⚠️ KRITIS! DO turun cepat ({abs_rate} mg/L/jam). Cek aerator dan kurangi pakan!"
        elif abs_rate >= DO_DROP_THRESHOLDS["warning_drop_rate"]:
            if alert_level != "CRITICAL":
                alert_level = "WARNING"
            recommendation = f"⚡ DO menurun ({abs_rate} mg/L/jam). Monitor ketat dan siapkan aerasi tambahan."
    
    return {
        "status": "ANALYZED",
        "current_do": current_do,
        "drop_rate": drop_rate,
        "alert_level": alert_level,
        "recommendation": recommendation,
        "data_points": len(readings),
        "time_range_hours": window_hours,
        "data_timestamp": data_timestamp,
        "is_fallback": is_fallback
    }



# === AERATION CALCULATOR ===

def calculate_oxygen_demand(
    current_do: float,
    target_do: float,
    volume_m3: float,
    fish_count: int,
    avg_weight_g: float = 100,
    safety_factor: float = 1.2
) -> Dict:
    """
    Hitung kebutuhan oksigen untuk mencapai target DO.
    
    Rumus:
    - Oxygen Deficit = (Target DO - Current DO) × Volume × 1000 (kg O2)
    - Fish Respiration = Fish Count × Avg Weight × Respiration Rate
    - Total O2 Need = Deficit + Respiration × Safety Factor
    
    Args:
        current_do: DO saat ini (mg/L)
        target_do: Target DO (mg/L)
        volume_m3: Volume kolam (m³)
        fish_count: Jumlah ikan
        avg_weight_g: Rata-rata berat ikan (gram)
        safety_factor: Faktor keamanan (default 1.2)
    
    Returns:
        Dict dengan kebutuhan O2 dan rekomendasi aerator
    """
    # Constants
    RESPIRATION_RATE = 0.0003  # kg O2 / kg fish / hour (typical for tilapia)
    AERATOR_TRANSFER_RATE = 0.5  # kg O2 / HP / hour (typical paddle wheel)
    
    # Calculate oxygen deficit (kg O2)
    # 1 mg/L = 1 g/m³ = 0.001 kg/m³
    do_deficit = max(0, target_do - current_do)
    oxygen_deficit_kg = do_deficit * volume_m3 * 0.001  # Convert to kg
    
    # Calculate fish respiration demand (kg O2/hour)
    total_fish_weight_kg = (fish_count * avg_weight_g) / 1000
    hourly_respiration_kg = total_fish_weight_kg * RESPIRATION_RATE
    
    # Total oxygen need (kg O2)
    total_o2_need_kg = (oxygen_deficit_kg + hourly_respiration_kg) * safety_factor
    
    # Calculate recommended aerator capacity
    recommended_hp = total_o2_need_kg / AERATOR_TRANSFER_RATE
    
    return {
        "current_do": current_do,
        "target_do": target_do,
        "oxygen_deficit_kg": round(oxygen_deficit_kg, 3),
        "hourly_respiration_kg": round(hourly_respiration_kg, 3),
        "total_o2_need_kg": round(total_o2_need_kg, 3),
        "recommended_aerator_hp": round(recommended_hp, 2),
        "calculation_notes": f"Berdasarkan volume {volume_m3}m³, {fish_count} ikan @ {avg_weight_g}g rata-rata"
    }


def get_aeration_recommendation(pond_config: Optional[Dict] = None) -> Dict:
    """
    Generate rekomendasi aerasi lengkap berdasarkan kondisi terkini.
    
    Args:
        pond_config: Konfigurasi kolam (optional, gunakan default jika None)
    
    Returns:
        Dict dengan trend analysis + aeration calculation
    """
    config = pond_config or DEFAULT_POND_CONFIG
    
    # Get trend analysis
    trend = analyze_do_trend()
    
    if trend["current_do"] is None:
        return {
            "trend": trend,
            "aeration": None,
            "message": "Tidak dapat menghitung kebutuhan aerasi tanpa data DO."
        }
    
    # Calculate aeration needs
    aeration = calculate_oxygen_demand(
        current_do=trend["current_do"],
        target_do=config.get("target_do", 6.0),
        volume_m3=config.get("volume_m3", 1000),
        fish_count=config.get("fish_count", 8000),
        avg_weight_g=config.get("avg_weight_g", 100),
        safety_factor=config.get("safety_factor", 1.2)
    )
    
    # Format timestamp info untuk output
    ts = trend.get("data_timestamp")
    is_fallback = trend.get("is_fallback", False)
    window_hours = trend.get("time_range_hours", 24)
    data_points = trend.get("data_points", 0)

    if ts:
        now = datetime.now()
        selisih = now - ts
        total_menit = int(selisih.total_seconds() // 60)
        jam = total_menit // 60
        menit = total_menit % 60

        ts_str = ts.strftime("%d %b %Y, %H:%M")
        if jam > 0:
            umur_data = f"{jam} jam {menit} menit lalu"
        elif menit > 0:
            umur_data = f"{menit} menit lalu"
        else:
            umur_data = "baru saja"

        if is_fallback:
            info_data = (
                f"📋 *Sumber Data:*\n"
                f"• Data terakhir: {ts_str} ({umur_data})\n"
                f"• Jumlah titik data: {data_points} pembacaan\n"
                f"⚠️ _Tidak ada data baru dalam {window_hours} jam — menggunakan data historis_"
            )
        else:
            info_data = (
                f"📋 *Sumber Data:*\n"
                f"• Data terbaru: {ts_str} ({umur_data})\n"
                f"• Rentang analisis: {window_hours} jam terakhir ({data_points} pembacaan)"
            )
    else:
        info_data = "📋 *Sumber Data:* Tidak diketahui"

    # Status level dalam bahasa natural
    level_info = {
        "NORMAL": "✅ Normal — kondisi DO baik",
        "WARNING": "⚠️ Waspada — DO mulai rendah",
        "CRITICAL": "🚨 Kritis — perlu tindakan segera",
        "UNKNOWN": "❓ Tidak diketahui"
    }
    status_natural = level_info.get(trend["alert_level"], trend["alert_level"])

    # Trend DO dalam bahasa natural
    dp = trend.get("drop_rate")
    if dp is None:
        trend_natural = "Tidak cukup data untuk hitung tren"
    elif dp > 0.05:
        trend_natural = f"📈 Naik +{abs(dp)} mg/L/jam"
    elif dp < -0.05:
        trend_natural = f"📉 Turun -{abs(dp)} mg/L/jam (perlu perhatian)"
    else:
        trend_natural = f"➡️ Stabil ({dp} mg/L/jam)"

    # Header urgency
    if trend["alert_level"] == "CRITICAL":
        header = "🚨 *DARURAT - STATUS AERASI*"
    elif trend["alert_level"] == "WARNING":
        header = "⚠️ *WASPADA - STATUS AERASI*"
    else:
        header = "💨 *CEK AERASI KOLAM*"

    message = (
        f"{header}\n\n"
        f"📋 *Sumber Data*\n"
        f"{info_data}\n\n"
        f"🌊 *Kondisi DO*\n"
        f"• Level: *{trend['current_do']} mg/L*\n"
        f"• Tren: {trend_natural}\n"
        f"• Status: {status_natural}\n\n"
        f"🔧 *Kebutuhan Aerasi*\n"
        f"• Defisit O₂: {aeration['oxygen_deficit_kg']} kg\n"
        f"• Total/jam: {aeration['total_o2_need_kg']} kg O₂\n"
        f"• Aerator: *{aeration['recommended_aerator_hp']} HP*\n\n"
        f"💡 {trend['recommendation']}\n\n"
        f"_Ketik pertanyaan untuk diskusi lanjut_"
    )

    
    return {
        "trend": trend,
        "aeration": aeration,
        "message": message
    }


# === CHATBOT INTEGRATION ===

def format_aerasi_response(lang: str = "id") -> str:
    """
    Format response untuk command 'aerasi' di chatbot.
    """
    result = get_aeration_recommendation()
    return result["message"]


if __name__ == "__main__":
    # Test module
    print("=== DO Analyzer Test ===")
    print(format_aerasi_response())
