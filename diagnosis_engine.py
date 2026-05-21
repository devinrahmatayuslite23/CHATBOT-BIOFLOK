"""
Diagnosis Engine Module
Dynamic diagnosis system that reads rules and matrix from Google Sheets.
Includes: Emergency Priority, In-Memory Cache, Weighted Scoring.
"""
import drive
import time
import requests
import os
from datetime import datetime, timedelta

# ===========================
# API TO GOOGLE APPS SCRIPT
# ===========================
# TODO: Ganti URL di bawah ini dengan URL Web App Apps Script milik Anda (setelah di-deploy)
GAS_API_URL = os.getenv("GAS_API_URL", "https://script.google.com/macros/s/AKfycbybH-RzEaZJ_wL_U8eQWjF7tZ-_Y7Xz8/exec")

# ===========================
# SMART CACHE STRATEGY
# Rules: cached 30 min (rarely change)
# Tab Data (sensor): ALWAYS fresh (changes frequently)
# ===========================
_cache = {
    "rules": None,
    "config_last_fetch": None,
    "config_ttl_minutes": 1440
}


def _is_config_cache_valid():
    """Check if rules & matrix cache is still fresh."""
    if _cache["config_last_fetch"] is None:
        return False
    elapsed = datetime.now() - _cache["config_last_fetch"]
    return elapsed < timedelta(minutes=_cache["config_ttl_minutes"])


def force_reload_config():
    """Force clear cache so next fetch gets fresh rules."""
    _cache["config_last_fetch"] = None
    _cache["rules"] = None
    print("🔄 Cache cleared via manual refresh.")
    return True


def _fetch_config():
    """Fetch rules and matrix (cached)."""
    sh = drive.dashboard
    if not sh:
        raise Exception("Dashboard connection not available")
    
    # 1. Read Diagnosis_Rules
    rules_ws = sh.worksheet("Diagnosis_Rules")
    rules_data = rules_ws.get_all_values()
    rules_rows = rules_data[1:]
    
    rules = []
    tab_names = set()
    for row in rules_rows:
        if len(row) < 5: continue
        param, keyword, tab_source, operator, value = row[0], row[1], row[2], row[3], row[4]
        
        if not tab_source or tab_source == "UNKNOWN":
            continue
        
        rules.append({
            "param": param, "keyword": keyword,
            "tab_source": tab_source, "operator": operator,
            "value": value,
            # --- Gerbong Logic 1 (Kolom F, G, H, I, J) ---
            "logic":       row[5]  if len(row) > 5  else "",
            "keyword2":    row[6]  if len(row) > 6  else "",
            "tab_source2": row[7]  if len(row) > 7  else "",
            "operator2":   row[8]  if len(row) > 8  else "",
            "value2":      row[9]  if len(row) > 9  else "",
            # --- Gerbong Logic 2 (Kolom K, L, M, N, O) ---
            "logic2":      row[10] if len(row) > 10 else "",
            "keyword3":    row[11] if len(row) > 11 else "",
            "tab_source3": row[12] if len(row) > 12 else "",
            "operator3":   row[13] if len(row) > 13 else "",
            "value3":      row[14] if len(row) > 14 else "",
        })
        tab_names.add(tab_source)
    
    # 2. Matrix Diagnosis is now handled entirely by Apps Script, no need to fetch it here.
    
    _cache["rules"] = rules
    _cache["config_last_fetch"] = datetime.now()
    print(f"🔄 Diagnosis Rules reloaded from Spreadsheet! (Next refresh in {_cache['config_ttl_minutes']} min)")
    
    return rules


def _fetch_tab_data(rules):
    """ALWAYS fetch fresh sensor data from tabs (no cache)."""
    sh = drive.dashboard
    if not sh:
        raise Exception("Dashboard connection not available")
    
    tab_names = set(r["tab_source"] for r in rules)
    tab_data = {}
    for tab_name in tab_names:
        try:
            ws = sh.worksheet(tab_name)
            tab_data[tab_name] = ws.get_all_values()
            time.sleep(0.3)
        except Exception as e:
            print(f"⚠️ Diagnosis: cannot read tab '{tab_name}': {e}")
            tab_data[tab_name] = []
    
    return tab_data

_DEFAULT_SENSOR_DATA = {
    "do": 4.5,          # Dissolved Oxygen (mg/L)
    "ph": 7.5,          # pH Level
    "temperature": 28.0,# Temperature (°C)
    "ammonia": 0.0,     # Ammonia (mg/L) - Optional
    "nitrate": 0.0,     # Nitrate (mg/L) - Optional
    "salinity": 0,      # Salinity (ppt) - Optional
    "turbidity": 0,     # Turbidity (NTU) - Optional
    "orp": 0            # ORP (mV) - Optional
}

# --- EXPORTED FUNCTION FOR APP.PY ---
def get_latest_sensor_data():
    """
    Fetch the absolute latest row from 'Water Quality' tab.
    Used for direct notification without full diagnosis.
    """
    try:
        # We need rules to identify the 'Water Quality' tab and its columns
        rules = _fetch_config()  # ← Fixed: _fetch_config() now returns only rules
        
        # Filter rules to find the 'Water Quality' tab
        water_quality_rules = [r for r in rules if r["tab_source"] == "Water Quality"]
        if not water_quality_rules:
            print("Warning: 'Water Quality' tab not found in rules. Returning default data.")
            return _DEFAULT_SENSOR_DATA

        # Fetch data for 'Water Quality' tab specifically
        tab_data = _fetch_tab_data(water_quality_rules)
        
        water_quality_data = tab_data.get("Water Quality")
        if not water_quality_data or len(water_quality_data) < 2: # Need headers + at least one row
            print("Warning: No data or insufficient data in 'Water Quality' tab. Returning default data.")
            return None # Return None to indicate no valid data found
        
        headers = water_quality_data[0]
        latest_row = water_quality_data[-1] # Get the very last row
        
        # [NEW LOGIC] Check Source Column (Index 2 - 'ESP_Bioflok_01' etc)
        # If it starts with '+' (Phone Number), it's from WhatsApp -> IGNORE NOTIFICATION
        # If it contains 'ESP' or doesn't start with '+', it's likely a sensor -> PROCESS
        
        source_id = str(latest_row[2]) if len(latest_row) > 2 else ""
        print(f"📡 New Data Detected. Source ID: {source_id}")
        
        if source_id.startswith("+"):
            print("⛔ Data source is a phone number (WhatsApp Manual Input). Skipping notification.")
            return None

        # Map latest row values to a dictionary using headers
        sensor_data = {}
        for i, header in enumerate(headers):
            if i < len(latest_row):
                try:
                    # Attempt to convert to float, otherwise keep as string
                    sensor_data[header.lower()] = float(latest_row[i].replace(",", "."))
                except ValueError:
                    sensor_data[header.lower()] = latest_row[i]
            else:
                sensor_data[header.lower()] = None # Handle missing values
        
        # Ensure essential keys are present, using defaults if not found
        final_sensor_data = _DEFAULT_SENSOR_DATA.copy()
        for key in final_sensor_data:
            if key in sensor_data and sensor_data[key] is not None:
                final_sensor_data[key] = sensor_data[key]
        
        return final_sensor_data
    except Exception as e:
        print(f"Error fetching latest sensor data: {e}")
        return None


def _fetch_all_data():
    """Fetch everything: config (cached) + sensor data (always fresh)."""
    # Config: use cache if valid
    if _is_config_cache_valid():
        rules = _cache["rules"]
    else:
        rules = _fetch_config()
    
    # Sensor data: ALWAYS fresh
    tab_data = _fetch_tab_data(rules)
    
    return rules, tab_data


# Matrix matching is now handled by Google Apps Script


def _check_emergency(snapshot, data_values):
    """Check for emergency conditions that need immediate alert."""
    emergencies = []
    
    if snapshot.get("Power Outage") == "PASS":
        val = data_values.get("Power Outage", {}).get("value", "0")
        emergencies.append({
            "type": "POWER",
            "title": "🔴 LISTRIK MATI",
            "detail": f"AC Status: {val}",
            "action": "1. Cek sumber listrik / genset\n2. Nyalakan aerator manual\n3. Stop pemberian pakan"
        })
    
    if snapshot.get("Low DO") == "PASS":
        val = data_values.get("Low DO", {}).get("value", "?")
        emergencies.append({
            "type": "DO",
            "title": "🔴 OKSIGEN KRITIS",
            "detail": f"DO: {val} mg/L",
            "action": "1. Tambah aerasi segera\n2. Kurangi pakan\n3. Cek kondisi blower"
        })
    
    return emergencies


def _format_data_summary(trigger_values_list):
    """Format sensor data summary from JSON trigger list for WhatsApp."""
    if not trigger_values_list:
        return "  Data parameter tidak tersedia"
        
    lines = []
    # trigger_values_list format: ["do: 4.5", "temperature: 28.5", "ph: 7.2"]
    for item in trigger_values_list:
        # Pengecekan sederhana menggunakan string matching untuk icon
        lower_item = item.lower()
        if "mati" in lower_item or "kematian" in lower_item or "outage" in lower_item or "ac_status: off" in lower_item:
            emoji = "⚠️"
        else:
            emoji = "✅" 
            
        # Format ke title case parameter jika memungkinkan misal "do" -> "DO"
        parts = item.split(":", 1)
        if len(parts) == 2:
            param = parts[0].strip().title()
            val = parts[1].strip()
            if param.lower() == "do": param = "DO"
            if param.lower() == "ph": param = "pH"
            if param.lower() == "tds": param = "TDS"
            lines.append(f"  {emoji} {param}: {val}")
        else:
            lines.append(f"  {emoji} {item}")
            
    return "\n".join(lines)


def format_diagnosa_response():
    """Main entry point: Call Google Apps Script API to run diagnosis and return formatted WhatsApp message."""
    try:
        print(f"📡 Requesting Diagnosis from Google Apps Script API...")
        payload = {"action": "run_diagnosis"}
        
        response = requests.post(GAS_API_URL, json=payload, timeout=30)
        response.raise_for_status()
        
        res_json = response.json()
        print(f"📥 Received response from GAS: {res_json.get('status', 'unknown')}")
        
        now = datetime.now().strftime("%d %b %Y, %H:%M WIB")
        status = res_json.get("status")
        
        if status == "error":
           error_msg = res_json.get("error_message", "Unknown error in Apps Script")
           return f"⚠️ Error dari Google Sheets API: {error_msg}"
        
        msg = "🔬 *DIAGNOSA KOLAM OTOMATIS*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        if status == "danger":
            # Emergency Alert (DO Kritis / Listrik Mati)
            snapshot = res_json.get("snapshot", {})
            trigger_values = res_json.get("trigger_values", [])
            val_dict = {}
            for tv in trigger_values:
                parts = tv.split(": ", 1)
                if len(parts) == 2:
                    val_dict[parts[0].strip()] = parts[1].strip()
            data_values_mock = {k: {"value": v} for k, v in val_dict.items()}
            emergencies = _check_emergency(snapshot, data_values_mock)
            if emergencies:
                msg += "⚡⚡⚡ *ALERT DARURAT* ⚡⚡⚡\n"
                msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
                for e in emergencies:
                    msg += f"{e['title']}\n"
                    msg += f"   {e['detail']}\n\n"
                    msg += f"⏱️ Segera lakukan:\n{e['action']}\n\n"
                msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

            # Data summary dari trigger_values (hanya PASS)
            if trigger_values:
                msg += "📊 *Data Terakhir:*\n"
                msg += _format_data_summary(trigger_values) + "\n\n"
            
            # Top diagnosis
            top_diagnosis = res_json.get("top_diagnosis", "Unknown")
            final_score = int(res_json.get("final_score", 0))
            matched = res_json.get("matched_conditions", 0)
            total = res_json.get("total_conditions", 0)
            
            msg += f"🏆 *Diagnosa Utama ({final_score}%):*\n"
            msg += f"{top_diagnosis}\n"
            msg += f"  _({matched}/{total} syarat cocok)_\n\n"
            
            # Kemungkinan Lain (runner-up dari all_results)
            all_results = res_json.get("all_results", [])
            others = [r for r in all_results[1:5] if r.get("final_score", 0) >= 40]
            if others:
                msg += "📋 *Kemungkinan Lain:*\n"
                for i, r in enumerate(others):
                    score = int(r.get("final_score", 0))
                    d_name = r.get("diagnosis", "")
                    if len(d_name) > 40:
                        d_name = d_name[:40] + "..."
                    msg += f"  {i+2}. {d_name} ({score}%)\n"
                msg += "\n"
            
            # Kondisi Aktif (semua PASS dari snapshot)
            active = [k for k, v in snapshot.items() if v == "PASS"]
            if active:
                msg += f"⚡ *Kondisi Aktif ({len(active)}):* "
                msg += ", ".join(active) + "\n\n"
            
        elif status == "normal":
            msg += "✅ *Tidak ada masalah terdeteksi. Kondisi Normal.*\n\n"
        else:
            msg += f"⚠️ Status respon API tidak dikenali: {status}\n\n"
            
        msg += f"━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"📅 {now}\n"
        msg += f"Ketik 'detail' untuk breakdown | 'analisa' untuk penjelasan AI"
        
        return msg
        
    except requests.exceptions.RequestException as e:
        return f"⚠️ Error koneksi ke Google Apps Script: {e}\nPastikan GAS Web App URL valid dan sudah di-deploy."
    except Exception as e:
        return f"⚠️ Error menjalankan diagnosa: {e}"


def format_diagnosa_detail():
    """Show detailed diagnosis breakdown menggunakan data dari GAS API.
    READ-ONLY: tidak menyimpan ke Diagnosis History."""
    try:
        print(f"📡 Requesting Detail from Google Apps Script API (read-only)...")
        payload = {"action": "get_diagnosis_detail"}  # ← read-only, tidak update History
        response = requests.post(GAS_API_URL, json=payload, timeout=30)
        response.raise_for_status()
        res_json = response.json()
        
        status = res_json.get("status")
        if status == "error":
            return f"⚠️ Error: {res_json.get('error_message', 'Unknown')}"
        if status == "normal":
            return "✅ Kondisi Normal. Tidak ada masalah terdeteksi."
        
        msg = "🔍 *DETAIL DIAGNOSA*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Top 5 dari all_results
        all_results = res_json.get("all_results", [])
        for i, r in enumerate(all_results[:5]):
            score = int(r.get("final_score", 0))
            emoji = "🔴" if score >= 60 else "🟠" if score >= 40 else "🟡"
            msg += f"{emoji} *#{i+1} ({score}%)*\n"
            msg += f"{r.get('diagnosis', '-')}\n"
            msg += f"  Match: {r.get('matched',0)}/{r.get('total',0)} | Freq: {int(r.get('frequency',0))}\n\n"
        
        # Rule Evaluation dari snapshot + trigger_values
        snapshot = res_json.get("snapshot", {})
        trigger_values = res_json.get("trigger_values", [])
        
        # Buat dict value dari trigger_values: "Low DO: 20" → {"Low DO": "20"}
        val_dict = {}
        for tv in trigger_values:
            parts = tv.split(": ", 1)
            if len(parts) == 2:
                val_dict[parts[0].strip()] = parts[1].strip()
        
        if snapshot:
            msg += "📊 *Rule Evaluation:*\n"
            for param, status_val in snapshot.items():
                val = val_dict.get(param, "-")
                emoji = "🟢" if status_val == "PASS" else "⚪"
                msg += f"  {emoji} {param}: {val} → {status_val}\n"
        
        msg += "\nKetik 'Menu' untuk kembali."
        return msg
        
    except Exception as e:
        return f"⚠️ Error mengambil detail: {e}"


def generate_diagnosa_explanation():
    """
    Generate AI explanation for the current diagnosis based on API response.
    """
    try:
        from google import genai
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        # Request data dari GAS API (read-only, tidak update Diagnosis History)
        response = requests.post(GAS_API_URL, json={"action": "get_diagnosis_detail"}, timeout=30)
        response.raise_for_status()
        res_json = response.json()
        
        if res_json.get("status") == "normal" or res_json.get("status") == "error":
            return "✅ Tidak ada masalah krusial terdeteksi. Kolam dalam kondisi baik."
            
        top_diagnosis = res_json.get("top_diagnosis", "Unknown")
        final_score = int(res_json.get("final_score", 0))
        matched = res_json.get("matched_conditions", 0)
        total = res_json.get("total_conditions", 0)
        trigger_values = res_json.get("trigger_values", [])
        
        # Build sensor context string
        sensor_text = "\n".join([f"  - {val}" for val in trigger_values])
        
        # Build Gemini prompt
        prompt = (
            f"Kamu adalah ahli akuakultur bioflok Indonesia. "
            f"Berdasarkan data sensor dan diagnosa berikut, berikan penjelasan untuk petambak.\n\n"
            f"DIAGNOSA UTAMA: {top_diagnosis} (confidence {final_score}%)\n"
            f"Syarat cocok: {matched}/{total}\n\n"
            f"DATA SENSOR TERKINI:\n{sensor_text}\n\n"
        )
        
        prompt += (
            "TUGASMU:\n"
            "1. Jelaskan MENGAPA diagnosa ini masuk akal\n"
            "2. Hubungkan antar parameter (misal: suhu tinggi → DO turun)\n"
            "3. Berikan 3 langkah KONKRIT yang harus dilakukan SEKARANG\n"
            "4. Sebutkan 1 risiko jika tidak ditangani\n\n"
            "FORMAT: Emoji + bullet points. Bahasa Indonesia. Mudah dimengerti petambak.\n"
            "BATASAN: MAKSIMAL 120 kata. Sangat padat, langsung ke inti. Jangan bertele-tele."
        )
        
        response_gemini = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        ai_text = response_gemini.text.strip()
        
        msg = f"🧠 *PENJELASAN AI*\n\n{ai_text}\n\nKetik 'Menu' untuk kembali."
        
        return msg
        
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "quota" in error_str.lower():
            return ("🧠 *PENJELASAN AI:*\n\n"
                    "⚠️ Kuota AI harian sudah habis.\n"
                    "Coba lagi besok atau dalam 1-2 menit.\n\n"
                    "Ketik 'Menu' untuk kembali.")
        return f"🧠 *PENJELASAN AI:*\n\n⚠️ Gagal memuat analisa. {e}\n\nKetik 'Menu' untuk kembali."
