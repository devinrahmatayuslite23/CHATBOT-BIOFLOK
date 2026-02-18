"""
Feed Calculator Module
======================
Modul untuk menghitung kebutuhan pakan harian berdasarkan sampling mingguan.

Methodology Reference: 
  - Sukabumi Plug&Play Pilot Farm Dashboard (20240802)
  - Feed rate: 5% untuk ikan <25g, 2.5% untuk ikan >25g
  - FCR Target: 1.2 (intensive), 1.7 (conventional)

Fitur:
1. Kalkulasi feed rate berdasarkan average weight
2. Proyeksi FCR (Feed Conversion Ratio)
3. Estimasi biaya pakan
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# Import from existing modules
try:
    from drive import (
        sampling_tab, feed_tab,
        log_daily_feed, get_daily_feed_count, 
        get_weekly_feed_summary, get_target_feed, populate_target_feed
    )
    DRIVE_AVAILABLE = True
except ImportError:
    sampling_tab = None
    feed_tab = None
    DRIVE_AVAILABLE = False


# === CONFIGURATION (Based on Sukabumi Pilot Farm Data) ===

# Feed rate by fish weight category (% of body weight per day)
# Reference: Spreadsheet "20240802 Sukabumi Plug&Play Pilot Farm Dashboard"
# Client uses: 5% for fish < 25g, 2.5% for fish >= 25g
FEED_RATE_TABLE = {
    # (min_weight, max_weight): (min_rate, max_rate)
    (0, 10): (5.0, 5.0),         # Very small fry - using client's 5%
    (10, 25): (5.0, 5.0),        # Small fry - using client's 5%
    (25, 50): (2.5, 2.5),        # Fry - using client's 2.5%
    (50, 100): (2.5, 2.5),       # Fingerlings - using client's 2.5%
    (100, 150): (2.5, 2.5),      # Juveniles - using client's 2.5%
    (150, 250): (2.5, 2.5),      # Sub-adults - using client's 2.5%
    (250, 400): (2.0, 2.5),      # Adults
    (400, 1000): (1.5, 2.0),     # Market size
}

# Default feed prices from client data (IDR per kg)
# Reference: Spreadsheet shows Rp18,500 (starter) and Rp11,000-11,500 (grower)
FEED_PRICES = {
    "starter": 18500,   # For fish < 25g
    "grower_1": 11500,  # For fish 25-100g  
    "grower_2": 11000,  # For fish > 100g
}
DEFAULT_FEED_PRICE = 11500

# Target FCR values from Sukabumi Pilot Farm
# Reference: Row 135-136 of spreadsheet
FCR_TARGETS = {
    "excellent": (0.8, 1.0),      # Based on client's best FCR values (~0.52-0.85)
    "good": (1.0, 1.2),           # Standard FCR (intensive) = 1.20
    "average": (1.2, 1.5),        # Between intensive and conventional
    "poor": (1.5, 1.7),           # Standard FCR (conventional) = 1.70
    "very_poor": (1.7, 3.0),      # Above conventional standard
}

# Standard benchmarks from client data
FCR_STANDARD_INTENSIVE = 1.20
FCR_STANDARD_CONVENTIONAL = 1.70


# === SAMPLING DATA ACCESS ===

def get_latest_sampling() -> Optional[Dict]:
    """
    Ambil data sampling mingguan terakhir dari spreadsheet.
    
    Returns:
        Dict dengan average_weight, fish_count, survival_rate, dll
    """
    if not sampling_tab:
        return None
    
    try:
        all_data = sampling_tab.get_all_values()
        if len(all_data) < 2:
            return None
        
        headers = all_data[0]
        last_row = all_data[-1]
        
        # Parse data
        timestamp = last_row[0] if len(last_row) > 0 else ""
        reporter = last_row[1] if len(last_row) > 1 else ""
        avg_weight_str = last_row[2] if len(last_row) > 2 else "0"
        avg_length_str = last_row[3] if len(last_row) > 3 else "0"
        
        try:
            avg_weight = float(avg_weight_str.replace(",", "."))
        except:
            avg_weight = 0.0
        
        try:
            avg_length = float(avg_length_str.replace(",", "."))
        except:
            avg_length = 0.0
        
        return {
            "timestamp": timestamp,
            "reporter": reporter,
            "avg_weight_g": avg_weight,
            "avg_length_cm": avg_length,
            "raw_row": last_row
        }
        
    except Exception as e:
        print(f"⚠️ Error getting sampling data: {e}")
        return None


def get_sampling_history(weeks: int = 4) -> List[Dict]:
    """
    Ambil history sampling untuk analisis growth rate.
    """
    if not sampling_tab:
        return []
    
    try:
        all_data = sampling_tab.get_all_values()
        if len(all_data) < 2:
            return []
        
        history = []
        for row in all_data[1:]:
            try:
                timestamp = row[0] if len(row) > 0 else ""
                avg_weight = float(row[2].replace(",", ".")) if len(row) > 2 and row[2] else 0
                avg_length = float(row[3].replace(",", ".")) if len(row) > 3 and row[3] else 0
                
                if avg_weight > 0:
                    history.append({
                        "timestamp": timestamp,
                        "avg_weight_g": avg_weight,
                        "avg_length_cm": avg_length
                    })
            except (ValueError, IndexError):
                continue
        
        # Return last n weeks (assuming 1 sample per week)
        return history[-weeks:] if len(history) >= weeks else history
        
    except Exception as e:
        print(f"⚠️ Error getting sampling history: {e}")
        return []


# === FEED CALCULATION ===

def get_feed_rate(avg_weight_g: float) -> Tuple[float, float]:
    """
    Tentukan feed rate (% body weight) berdasarkan average weight.
    
    Returns:
        Tuple of (min_rate, max_rate) in percentage
    """
    for (min_w, max_w), (min_r, max_r) in FEED_RATE_TABLE.items():
        if min_w <= avg_weight_g < max_w:
            return (min_r, max_r)
    
    # Default for very large fish
    return (1.5, 2.0)


def calculate_daily_feed(
    fish_count: int,
    avg_weight_g: float,
    feed_rate_pct: Optional[float] = None,
    survival_rate: float = 1.0
) -> Dict:
    """
    Hitung kebutuhan pakan harian.
    
    Args:
        fish_count: Jumlah ikan awal
        avg_weight_g: Rata-rata berat ikan (gram)
        feed_rate_pct: Feed rate manual (optional). Jika None, akan dihitung otomatis.
        survival_rate: Estimated survival rate (0.0-1.0)
    
    Returns:
        Dict dengan daily_feed_kg, recommendations, dll
    """
    # Calculate estimated current fish count
    effective_fish_count = int(fish_count * survival_rate)
    
    # Get feed rate
    if feed_rate_pct is None:
        min_rate, max_rate = get_feed_rate(avg_weight_g)
        # Use mid-point as default
        feed_rate_pct = (min_rate + max_rate) / 2
    
    # Calculate total biomass
    total_biomass_kg = (effective_fish_count * avg_weight_g) / 1000
    
    # Calculate daily feed
    daily_feed_kg = total_biomass_kg * (feed_rate_pct / 100)
    
    # Get recommended range
    min_rate, max_rate = get_feed_rate(avg_weight_g)
    feed_range_min = total_biomass_kg * (min_rate / 100)
    feed_range_max = total_biomass_kg * (max_rate / 100)
    
    return {
        "fish_count_initial": fish_count,
        "fish_count_effective": effective_fish_count,
        "avg_weight_g": avg_weight_g,
        "total_biomass_kg": round(total_biomass_kg, 2),
        "feed_rate_pct": round(feed_rate_pct, 2),
        "daily_feed_kg": round(daily_feed_kg, 2),
        "feed_range_min_kg": round(feed_range_min, 2),
        "feed_range_max_kg": round(feed_range_max, 2),
        "recommended_rate_range": f"{min_rate}-{max_rate}%"
    }


def calculate_feeding_schedule(
    daily_feed_kg: float,
    feeding_frequency: int = 3
) -> List[Dict]:
    """
    Buat jadwal pemberian pakan.
    
    Args:
        daily_feed_kg: Total pakan harian (kg)
        feeding_frequency: Frekuensi pemberian pakan per hari
    
    Returns:
        List of feeding times with amounts
    """
    # Default feeding times
    feeding_times = {
        2: ["07:00", "17:00"],
        3: ["07:00", "12:00", "17:00"],
        4: ["06:00", "10:00", "14:00", "18:00"],
        5: ["06:00", "09:00", "12:00", "15:00", "18:00"],
    }
    
    times = feeding_times.get(feeding_frequency, feeding_times[3])
    amount_per_feeding = daily_feed_kg / len(times)
    
    schedule = []
    for time in times:
        schedule.append({
            "time": time,
            "amount_kg": round(amount_per_feeding, 2)
        })
    
    return schedule


def estimate_fcr(
    total_feed_kg: float,
    weight_gain_kg: float
) -> Dict:
    """
    Hitung FCR (Feed Conversion Ratio).
    
    FCR = Total Feed / Weight Gain
    
    Args:
        total_feed_kg: Total pakan yang diberikan (kg)
        weight_gain_kg: Total pertambahan berat (kg)
    
    Returns:
        Dict dengan FCR value dan rating
    """
    if weight_gain_kg <= 0:
        return {
            "fcr": None,
            "rating": "UNKNOWN",
            "message": "Tidak dapat menghitung FCR (tidak ada pertambahan berat)"
        }
    
    fcr = total_feed_kg / weight_gain_kg
    
    # Determine rating based on Sukabumi Pilot Farm standards
    if fcr <= FCR_TARGETS["excellent"][1]:
        rating = "EXCELLENT"
        message = f"FCR sangat baik! Lebih baik dari standar intensive ({FCR_STANDARD_INTENSIVE})."
    elif fcr <= FCR_TARGETS["good"][1]:
        rating = "GOOD"
        message = f"FCR baik. Sesuai standar intensive ({FCR_STANDARD_INTENSIVE})."
    elif fcr <= FCR_TARGETS["average"][1]:
        rating = "AVERAGE"
        message = "FCR rata-rata. Ada ruang untuk improvement."
    elif fcr <= FCR_TARGETS["poor"][1]:
        rating = "POOR"
        message = f"FCR mendekati standar konvensional ({FCR_STANDARD_CONVENTIONAL}). Perlu evaluasi."
    else:
        rating = "VERY_POOR"
        message = "FCR di atas standar konvensional. Evaluasi pakan dan manajemen pemberian."
    
    return {
        "fcr": round(fcr, 2),
        "rating": rating,
        "message": message,
        "target_range": f"{FCR_TARGETS['good'][0]}-{FCR_TARGETS['good'][1]}",
        "benchmark_intensive": FCR_STANDARD_INTENSIVE,
        "benchmark_conventional": FCR_STANDARD_CONVENTIONAL
    }


def get_feed_price(avg_weight_g: float) -> float:
    """
    Get appropriate feed price based on fish weight.
    Reference: Sukabumi Pilot Farm spreadsheet
    """
    if avg_weight_g < 25:
        return FEED_PRICES["starter"]  # Rp18,500
    elif avg_weight_g < 100:
        return FEED_PRICES["grower_1"]  # Rp11,500
    else:
        return FEED_PRICES["grower_2"]  # Rp11,000


def estimate_feed_cost(
    daily_feed_kg: float,
    price_per_kg: float = None,
    days: int = 1,
    avg_weight_g: float = None
) -> Dict:
    """
    Estimasi biaya pakan menggunakan tiered pricing dari Sukabumi Pilot Farm.
    """
    # Auto-select price based on fish weight if not provided
    if price_per_kg is None:
        if avg_weight_g is not None:
            price_per_kg = get_feed_price(avg_weight_g)
        else:
            price_per_kg = DEFAULT_FEED_PRICE
    
    total_feed = daily_feed_kg * days
    total_cost = total_feed * price_per_kg
    
    return {
        "daily_feed_kg": daily_feed_kg,
        "days": days,
        "total_feed_kg": round(total_feed, 2),
        "price_per_kg": price_per_kg,
        "total_cost": round(total_cost, 0),
        "formatted_cost": f"Rp{total_cost:,.0f}"
    }


# === GROWTH PROJECTION ===

def calculate_growth_rate(sampling_history: List[Dict]) -> Optional[Dict]:
    """
    Hitung growth rate dari history sampling.
    
    Returns:
        Dict dengan average daily gain dan projected harvest date
    """
    if len(sampling_history) < 2:
        return None
    
    # Calculate weight differences
    weights = [(s["timestamp"], s["avg_weight_g"]) for s in sampling_history]
    
    # Simple: use first and last
    first_weight = weights[0][1]
    last_weight = weights[-1][1]
    
    # Assume 7 days between samplings
    days_elapsed = (len(weights) - 1) * 7
    
    if days_elapsed <= 0:
        return None
    
    total_gain = last_weight - first_weight
    adg = total_gain / days_elapsed  # Average Daily Gain (g/day)
    
    return {
        "first_weight_g": first_weight,
        "last_weight_g": last_weight,
        "total_gain_g": round(total_gain, 1),
        "days_elapsed": days_elapsed,
        "adg_g_per_day": round(adg, 2),
        "weeks_sampled": len(weights)
    }


def project_harvest(
    current_weight_g: float,
    target_weight_g: float,
    adg: float
) -> Optional[Dict]:
    """
    Proyeksi waktu harvest berdasarkan growth rate.
    """
    if adg <= 0:
        return None
    
    weight_remaining = target_weight_g - current_weight_g
    if weight_remaining <= 0:
        return {
            "status": "READY",
            "message": "Ikan sudah mencapai target berat! Siap panen.",
            "current_weight_g": current_weight_g,
            "target_weight_g": target_weight_g
        }
    
    days_to_target = weight_remaining / adg
    projected_date = datetime.now() + timedelta(days=days_to_target)
    
    return {
        "status": "GROWING",
        "current_weight_g": current_weight_g,
        "target_weight_g": target_weight_g,
        "weight_remaining_g": round(weight_remaining, 1),
        "days_to_harvest": int(days_to_target),
        "projected_date": projected_date.strftime("%Y-%m-%d"),
        "adg_used": adg
    }


# === CHATBOT INTEGRATION ===

def get_feed_recommendation(
    avg_weight_g: Optional[float] = None,
    fish_count: int = 8000,
    survival_rate: float = 0.9,
    target_weight_g: float = 250
) -> Dict:
    """
    Generate rekomendasi pakan lengkap.
    
    Args:
        avg_weight_g: Rata-rata berat ikan. Jika None, ambil dari sampling terakhir.
        fish_count: Jumlah ikan
        survival_rate: Estimated survival rate
        target_weight_g: Target berat untuk harvest
    """
    # Get weight from sampling if not provided
    if avg_weight_g is None:
        sampling = get_latest_sampling()
        if sampling and sampling["avg_weight_g"] > 0:
            avg_weight_g = sampling["avg_weight_g"]
        else:
            return {
                "status": "NO_DATA",
                "message": "Tidak ada data sampling. Mohon input berat rata-rata ikan."
            }
    
    # Calculate feed
    feed_calc = calculate_daily_feed(
        fish_count=fish_count,
        avg_weight_g=avg_weight_g,
        survival_rate=survival_rate
    )
    
    # Get schedule
    schedule = calculate_feeding_schedule(feed_calc["daily_feed_kg"], feeding_frequency=3)
    
    # Get cost estimate with tiered pricing based on fish weight
    cost = estimate_feed_cost(feed_calc["daily_feed_kg"], days=7, avg_weight_g=avg_weight_g)
    
    # Get growth projection
    history = get_sampling_history(weeks=4)
    growth = calculate_growth_rate(history) if len(history) >= 2 else None
    harvest_projection = None
    
    if growth and growth["adg_g_per_day"] > 0:
        harvest_projection = project_harvest(
            current_weight_g=avg_weight_g,
            target_weight_g=target_weight_g,
            adg=growth["adg_g_per_day"]
        )
    
    return {
        "status": "SUCCESS",
        "feed_calculation": feed_calc,
        "feeding_schedule": schedule,
        "weekly_cost": cost,
        "growth_data": growth,
        "harvest_projection": harvest_projection
    }


def format_pakan_response(avg_weight_g: Optional[float] = None, lang: str = "id") -> str:
    """
    Format response untuk command 'pakan' di chatbot.
    """
    result = get_feed_recommendation(avg_weight_g=avg_weight_g)
    
    if result["status"] == "NO_DATA":
        return f"⚠️ {result['message']}\n\nContoh: 'pakan 105' (untuk input berat 105 gram)"
    
    feed = result["feed_calculation"]
    schedule = result["feeding_schedule"]
    cost = result["weekly_cost"]
    growth = result.get("growth_data")
    harvest = result.get("harvest_projection")
    
    message = f"""🐟 Rekomendasi Pakan Harian

📊 Data Ikan:
• Jumlah: {feed['fish_count_effective']:,} ekor
• Berat rata-rata: {feed['avg_weight_g']}g
• Biomass total: {feed['total_biomass_kg']} kg

🍽️ Kebutuhan Pakan:
• Feed rate: {feed['feed_rate_pct']}% ({feed['recommended_rate_range']})
• Pakan harian: {feed['daily_feed_kg']} kg
• Range: {feed['feed_range_min_kg']}-{feed['feed_range_max_kg']} kg

⏰ Jadwal Pemberian:
"""
    
    for s in schedule:
        message += f"• {s['time']} → {s['amount_kg']} kg\n"
    
    message += f"""
💰 Estimasi Biaya (7 hari):
• Total pakan: {cost['total_feed_kg']} kg
• Biaya: {cost['formatted_cost']}
"""
    
    if harvest:
        if harvest["status"] == "READY":
            message += f"\n✅ {harvest['message']}"
        else:
            message += f"""
📈 Proyeksi Panen:
• Target: {harvest['target_weight_g']}g
• Sisa: {harvest['weight_remaining_g']}g lagi
• Estimasi: {harvest['days_to_harvest']} hari ({harvest['projected_date']})
"""
    
    return message


# === FEED LOGGING CHATBOT FUNCTIONS ===

def format_log_pakan_response(pangan_kg: float, \
                               jenis_pakan: str = "Grower", reporter: str = "", photo_link: str = "") -> str:
    """
    Format response untuk command 'log pakan' di chatbot.
    Logs the feed to spreadsheet and returns confirmation.
    """
    if not DRIVE_AVAILABLE:
        return "⚠️ Koneksi ke spreadsheet tidak tersedia. Data tidak tersimpan."
    
    # Determine price based on feed type
    harga = FEED_PRICES.get("starter" if jenis_pakan.lower() == "starter" else "grower_1", 11500)
    
    # [FIX] Call log_daily_feed with correct arguments (removed frekuensi/jenis_pakan)
    result = log_daily_feed(
        pangan_kg=pangan_kg,
        harga_per_kg=harga,
        photo_link=photo_link,
        reporter=reporter
    )
    
    if result["status"] == "SUCCESS":
        return f"""✅ Pakan Tercatat!

📅 Tanggal: {result['date']}
📊 Hari ke-{result['day']}
🍽️ Pakan: {result['pangan_kg']} kg
💰 Biaya: {result['biaya']}

Data tersimpan di tab 'Feed Tracker'.
Ketik 'rekap pakan' untuk lihat total minggunan."""
    else:
        return f"⚠️ Gagal menyimpan data: {result.get('message', 'Unknown error')}"


def format_rekap_pakan_response(week_number: int = None) -> str:
    """
    Format response untuk command 'rekap pakan' di chatbot.
    Shows weekly feed summary with comparison to target.
    """
    if not DRIVE_AVAILABLE:
        return "⚠️ Koneksi ke spreadsheet tidak tersedia."
    
    summary = get_weekly_feed_summary(week_number)
    
    if summary["status"] == "NO_DATA":
        return f"📊 {summary['message']}\n\nGunakan 'log pakan [kg]' untuk mulai mencatat."
    
    if summary["status"] == "ERROR":
        return f"⚠️ Error: {summary.get('message', 'Unknown error')}"
    
    # Get target for comparison
    target = get_target_feed(summary["minggu"])
    
    message = f"""📊 Rekap Pakan Minggu {summary['minggu']}

📅 Periode: {summary['tanggal_mulai']} - {summary['tanggal_akhir']}
📝 Hari tercatat: {summary['hari_tercatat']} hari

🍽️ Total Pakan: {summary['total_pangan_kg']} kg
💰 Total Biaya: {summary['total_biaya']}
"""
    
    if target:
        # Compare with target
        diff = summary['total_pangan_kg'] - target['pangan_target_kg']
        diff_pct = (diff / target['pangan_target_kg'] * 100) if target['pangan_target_kg'] > 0 else 0
        
        if diff > 0:
            status = f"📈 +{diff:.1f} kg ({diff_pct:+.1f}%) dari target"
        elif diff < 0:
            status = f"📉 {diff:.1f} kg ({diff_pct:.1f}%) dari target"
        else:
            status = "✅ Sesuai target!"
        
        message += f"""
📌 Perbandingan Target:
• Target: {target['pangan_target_kg']} kg
• FCR Target: {target['fcr_standard']}
{status}
"""
    
    return message


if __name__ == "__main__":
    # Test module
    print("=== Feed Calculator Test ===")
    print(format_pakan_response(avg_weight_g=105))

