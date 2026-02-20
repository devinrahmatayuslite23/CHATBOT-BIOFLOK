"""
Diagnosis Engine Module
Dynamic diagnosis system that reads rules and matrix from Google Sheets.
Includes: Emergency Priority, In-Memory Cache, Weighted Scoring.
"""
import drive
import gspread
import time
from datetime import datetime, timedelta

# ===========================
# SMART CACHE STRATEGY
# Rules & Matrix: cached 30 min (rarely change)
# Tab Data (sensor): ALWAYS fresh (changes frequently)
# ===========================
_cache = {
    "rules": None,
    "matrix": None,
    "config_last_fetch": None,
    "config_ttl_minutes": 1440
}

SCORING_DATA_WEIGHT = 0.7
SCORING_PRIOR_WEIGHT = 0.3
DEPTH_CAP = 6


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
    _cache["matrix"] = None
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
        logic = row[5] if len(row) > 5 else ""
        
        if not tab_source or tab_source == "UNKNOWN":
            continue
        
        rules.append({
            "param": param, "keyword": keyword,
            "tab_source": tab_source, "operator": operator,
            "value": value, "logic": logic
        })
        tab_names.add(tab_source)
    
    # 2. Read Matrix Diagnosis
    matrix_ws = sh.worksheet("Matrix Diagnosis")
    matrix_data = matrix_ws.get_all_values()
    
    _cache["rules"] = rules
    _cache["matrix"] = matrix_data
    _cache["config_last_fetch"] = datetime.now()
    print(f"🔄 Diagnosis Rules & Matrix reloaded from Spreadsheet! (Next refresh in {_cache['config_ttl_minutes']} min)")
    
    return rules, matrix_data


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
        rules, _ = _fetch_config() 
        
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
        matrix_data = _cache["matrix"]
    else:
        rules, matrix_data = _fetch_config()
    
    # Sensor data: ALWAYS fresh
    tab_data = _fetch_tab_data(rules)
    
    return rules, tab_data, matrix_data


def _evaluate_rules(rules, tab_data):
    """Evaluate all rules against latest data → PASS/FAIL snapshot."""
    snapshot = {}
    data_values = {}  # Store actual values for display
    
    for rule in rules:
        tab_name = rule["tab_source"]
        data = tab_data.get(tab_name, [])
        
        if not data:
            snapshot[rule["param"]] = "FAIL"
            continue
        
        tab_headers = data[0]
        tab_rows = data[1:]
        
        # Find column
        col_idx = None
        matched_col = None
        for idx, h in enumerate(tab_headers):
            if rule["keyword"].lower() in h.lower():
                col_idx = idx
                matched_col = h
                break
        
        if col_idx is None:
            snapshot[rule["param"]] = "FAIL"
            continue
        
        # Get latest value
        latest_val = None
        for row in reversed(tab_rows):
            if col_idx < len(row) and row[col_idx].strip():
                latest_val = row[col_idx].strip()
                break
        
        if latest_val is None:
            snapshot[rule["param"]] = "FAIL"
            continue
        
        # Evaluate
        try:
            num_val = float(latest_val.replace(",", "."))
            num_threshold = float(rule["value"].replace(",", "."))
            
            op = rule["operator"]
            if op == "<": passed = num_val < num_threshold
            elif op == ">": passed = num_val > num_threshold
            elif op == "<=": passed = num_val <= num_threshold
            elif op == ">=": passed = num_val >= num_threshold
            elif op == "=": passed = num_val == num_threshold
            else: passed = False
        except ValueError:
            if rule["operator"] == "=":
                passed = latest_val.lower() == rule["value"].lower()
            else:
                passed = False
        
        status = "PASS" if passed else "FAIL"
        snapshot[rule["param"]] = status
        data_values[rule["param"]] = {
            "value": latest_val,
            "column": matched_col or rule["keyword"],
            "tab": tab_name
        }
    
    return snapshot, data_values


def _match_matrix(snapshot, matrix_data):
    """Match PASS/FAIL snapshot against Matrix Diagnosis."""
    headers = matrix_data[0]
    rows = matrix_data[1:]
    
    # Map columns
    param_cols = {}
    diag_col, freq_col, cost_col = 2, 1, None
    
    for i, h in enumerate(headers):
        h_clean = h.strip()
        if h_clean in snapshot:
            param_cols[h_clean] = i
        if "cost" in h.lower():
            cost_col = i
    
    max_possible = len(param_cols)
    
    # Collect frequencies for prior
    all_freq = []
    for row in rows:
        if len(row) <= diag_col: continue
        d = row[diag_col].strip()
        if d.startswith("COST") or d == "-" or not d: continue
        try:
            all_freq.append(float(row[freq_col].strip()))
        except:
            all_freq.append(0)
    total_freq = sum(all_freq) if all_freq else 1
    
    # Score diagnoses
    results = []
    for row in rows:
        if len(row) <= diag_col: continue
        diag_name = row[diag_col].strip()
        if diag_name.startswith("COST") or diag_name == "-" or not diag_name:
            continue
        
        try:
            freq_num = float(row[freq_col].strip())
        except:
            freq_num = 0
        
        total_cond = 0
        matched_cond = 0
        
        for param_name, col_idx in param_cols.items():
            if col_idx >= len(row): continue
            matrix_val = row[col_idx].strip().upper()
            if matrix_val in ("?", "", "-"): continue
            
            current_val = snapshot.get(param_name, "FAIL")
            total_cond += 1
            if matrix_val == current_val:
                matched_cond += 1
        
        if total_cond == 0:
            continue
        
        match_ratio = matched_cond / total_cond * 100
        depth_weight = min(total_cond, DEPTH_CAP) / DEPTH_CAP
        weighted_score = match_ratio * depth_weight
        prior = freq_num / total_freq if total_freq > 0 else 0
        final_score = (weighted_score * SCORING_DATA_WEIGHT) + (prior * 100 * SCORING_PRIOR_WEIGHT)
        
        if matched_cond > 0:
            results.append({
                "diagnosis": diag_name,
                "final_score": final_score,
                "match_ratio": match_ratio,
                "matched": matched_cond,
                "total": total_cond,
                "frequency": freq_num
            })
    
    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results


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


def _format_data_summary(snapshot, data_values, rules):
    """Format sensor data summary for WhatsApp."""
    lines = []
    
    # Group by tab for cleaner display
    seen = set()
    key_params = {
        "DO": ("Low DO", "High DO"),
        "pH": ("Low pH", "High pH"),
        "Suhu": ("Low Temp", "High Temp"),
        "Pompa": ("Low Pump", "High Pump"),
        "Kematian": ("Low Death", "High Death"),
        "Berat": ("Low Weight", "High Weight"),
        "Pakan": ("Low Feed", "High Feed"),
        "Listrik": ("Power Outage",),
    }
    
    # Interpret emoji based on parameter semantics
    # "Low Death PASS" means deaths are low → GOOD
    # "Low Temp PASS" means temp is low → WARNING
    # "Power Outage PASS" means power is out → BAD
    warning_when_pass = {"Low Temp", "High Temp", "Low DO", "High DO", 
                         "Low pH", "High pH", "Power Outage",
                         "High Death", "High Feed", "Low Feed",
                         "Low Weight", "High Biomass"}
    good_when_pass = {"High Pump", "Low Death", "High SR"}
    
    for label, params in key_params.items():
        for p in params:
            if p in data_values and p not in seen:
                val = data_values[p]["value"]
                status = snapshot.get(p, "FAIL")
                if status == "PASS":
                    emoji = "⚠️" if p in warning_when_pass else "✅"
                else:
                    emoji = "✅"
                lines.append(f"  {emoji} {label}: {val}")
                seen.add(p)
                for pp in params:
                    seen.add(pp)
                break
    
    return "\n".join(lines)


def format_diagnosa_response():
    """Main entry point: run full diagnosis and return formatted WhatsApp message."""
    try:
        # Always fetch (config cached internally, sensor data always fresh)
        rules, tab_data, matrix_data = _fetch_all_data()
        
        # Phase 3: Evaluate rules
        snapshot, data_values = _evaluate_rules(rules, tab_data)
        
        # Emergency check
        emergencies = _check_emergency(snapshot, data_values)
        
        # Phase 4: Matrix matching
        results = _match_matrix(snapshot, matrix_data)
        
        # Build WhatsApp message
        now = datetime.now().strftime("%d %b %Y, %H:%M WIB")
        
        msg = ""
        
        # Emergency alerts first
        if emergencies:
            msg += "⚡⚡⚡ *ALERT DARURAT* ⚡⚡⚡\n"
            msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
            for e in emergencies:
                msg += f"{e['title']}\n"
                msg += f"   {e['detail']}\n\n"
                msg += f"⏱️ Segera lakukan:\n{e['action']}\n\n"
            msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Data summary
        msg += "🔬 *DIAGNOSA KOLAM OTOMATIS*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += "📊 *Data Terakhir:*\n"
        msg += _format_data_summary(snapshot, data_values, rules) + "\n\n"
        
        # Top diagnosis
        if results:
            top = results[0]
            confidence = int(top["final_score"])
            msg += f"🏆 *Diagnosa Utama ({confidence}%):*\n"
            msg += f"{top['diagnosis']}\n"
            msg += f"  _({top['matched']}/{top['total']} syarat cocok)_\n\n"
            
            # Runner-ups (only if > 40%)
            others = [r for r in results[1:5] if r["final_score"] >= 40]
            if others:
                msg += "📋 *Kemungkinan Lain:*\n"
                for i, r in enumerate(others):
                    score = int(r["final_score"])
                    # Extract short diagnosis name (D23 – Title)
                    d_name = r["diagnosis"]
                    if len(d_name) > 40:
                        d_name = d_name[:40] + "..."
                    msg += f"  {i+2}. {d_name} ({score}%)\n"
                msg += "\n"
        else:
            msg += "✅ *Tidak ada masalah terdeteksi.*\n\n"
        
        # Active conditions
        active = [k for k, v in snapshot.items() if v == "PASS"]
        if active:
            msg += f"⚡ *Kondisi Aktif ({len(active)}):* "
            msg += ", ".join(active) + "\n\n"
        
        msg += f"━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"📅 {now}\n"
        msg += f"Ketik 'detail' untuk breakdown | 'analisa' untuk penjelasan AI"
        
        return msg
        
    except Exception as e:
        return f"⚠️ Error menjalankan diagnosa: {e}"


def format_diagnosa_detail():
    """Show detailed diagnosis breakdown."""
    try:
        # Always fetch (config cached internally, sensor data always fresh)
        rules, tab_data, matrix_data = _fetch_all_data()
        
        snapshot, data_values = _evaluate_rules(rules, tab_data)
        results = _match_matrix(snapshot, matrix_data)
        
        msg = "🔍 *DETAIL DIAGNOSA*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Show top 5
        for i, r in enumerate(results[:5]):
            emoji = "🔴" if r["final_score"] >= 60 else "🟠" if r["final_score"] >= 40 else "🟡"
            msg += f"{emoji} *#{i+1} ({int(r['final_score'])}%)*\n"
            msg += f"{r['diagnosis']}\n"
            msg += f"  Match: {r['matched']}/{r['total']} | Freq: {int(r['frequency'])}\n\n"
        
        # Show all rule results
        msg += "📊 *Rule Evaluation:*\n"
        for param, status in snapshot.items():
            val = data_values.get(param, {}).get("value", "-")
            emoji = "🟢" if status == "PASS" else "⚪"
            msg += f"  {emoji} {param}: {val} → {status}\n"
        
        return msg
        
    except Exception as e:
        return f"⚠️ Error: {e}"


def generate_diagnosa_explanation():
    """
    Generate AI explanation for the current diagnosis.
    Calls Gemini to explain WHY the diagnosis makes sense,
    connects real data to the diagnosis, and gives actionable steps.
    Returns formatted WhatsApp message (separate bubble).
    """
    try:
        import os
        from google import genai
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        # Get fresh diagnosis data
        rules, tab_data, matrix_data = _fetch_all_data()
        snapshot, data_values = _evaluate_rules(rules, tab_data)
        results = _match_matrix(snapshot, matrix_data)
        emergencies = _check_emergency(snapshot, data_values)
        
        if not results:
            return "✅ Tidak ada masalah terdeteksi. Kolam dalam kondisi baik."
        
        top = results[0]
        
        # Build sensor context string
        sensor_lines = []
        for param, info in data_values.items():
            sensor_lines.append(f"  - {param}: {info['value']}")
        sensor_text = "\n".join(sensor_lines)
        
        # Active conditions
        active = [k for k, v in snapshot.items() if v == "PASS"]
        active_text = ", ".join(active) if active else "Tidak ada"
        
        # Build Gemini prompt
        prompt = (
            f"Kamu adalah ahli akuakultur bioflok Indonesia. "
            f"Berdasarkan data sensor dan diagnosa berikut, berikan penjelasan untuk petambak.\n\n"
            f"DIAGNOSA UTAMA: {top['diagnosis']} (confidence {int(top['final_score'])}%)\n"
            f"Syarat cocok: {top['matched']}/{top['total']}\n\n"
            f"DATA SENSOR TERKINI:\n{sensor_text}\n\n"
            f"KONDISI AKTIF: {active_text}\n\n"
        )
        
        if emergencies:
            emg_text = ", ".join([e['title'] for e in emergencies])
            prompt += f"⚠️ KONDISI DARURAT: {emg_text}\n\n"
        
        # Runner-ups for context
        if len(results) > 1:
            others = [f"{r['diagnosis']} ({int(r['final_score'])}%)" for r in results[1:3]]
            prompt += f"KEMUNGKINAN LAIN: {', '.join(others)}\n\n"
        
        prompt += (
            "TUGASMU:\n"
            "1. Jelaskan MENGAPA diagnosa ini masuk akal berdasarkan data\n"
            "2. Hubungkan antar parameter (misal: suhu tinggi → DO turun)\n"
            "3. Berikan 3-4 langkah KONKRIT yang harus dilakukan petambak SEKARANG\n"
            "4. Sebutkan risiko jika tidak ditangani\n\n"
            "FORMAT: Gunakan emoji dan bullet points. Bahasa Indonesia yang mudah dimengerti.\n"
            "BATASAN: MAKSIMAL 200 kata. Padat dan langsung ke inti."
        )
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        ai_text = response.text.strip()
        
        # Format for WhatsApp
        msg = "🧠 *PENJELASAN AI:*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += ai_text + "\n\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "Ketik 'Menu' untuk kembali."
        
        return msg
        
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "quota" in error_str.lower():
            return ("🧠 *PENJELASAN AI:*\n\n"
                    "⚠️ Kuota AI harian sudah habis.\n"
                    "Coba lagi besok atau dalam 1-2 menit.\n\n"
                    "Ketik 'Menu' untuk kembali.")
        return f"🧠 *PENJELASAN AI:*\n\n⚠️ Gagal memuat analisa.\n\nKetik 'Menu' untuk kembali."
