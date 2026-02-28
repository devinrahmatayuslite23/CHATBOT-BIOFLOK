import os
import io
import json
import base64
import pickle
import gspread
import requests
from datetime import datetime, timedelta
import random  # For mock confidence in demo
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Load environment variables
load_dotenv()

# === Auth credentials ===
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

# Try OAuth first (for Drive uploads), fallback to Service Account
drive_creds = None
sheets_creds = None

# Check for OAuth token (preferred for Drive)
if os.path.exists('token.pickle'):
    print("🔑 Using OAuth credentials for Drive...")
    with open('token.pickle', 'rb') as token:
        drive_creds = pickle.load(token)
    
    # Refresh if expired
    if drive_creds and drive_creds.expired and drive_creds.refresh_token:
        drive_creds.refresh(Request())
        # Save refreshed token
        with open('token.pickle', 'wb') as token:
            pickle.dump(drive_creds, token)
    
    # Use OAuth for both Drive and Sheets
    sheets_creds = drive_creds
else:
    print("⚠️  No OAuth token found. Using Service Account...")
    print("   Note: Drive uploads will use fallback (Twilio URL)")
    print("   Run 'python oauth_authorize.py' to enable Drive uploads")
    
    # Fallback to Service Account
    if "GOOGLE_CREDS_BASE64" in os.environ:
        creds_json = base64.b64decode(os.environ["GOOGLE_CREDS_BASE64"])
        creds_dict = json.loads(creds_json)
        sheets_creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        drive_creds = sheets_creds
    else:
        creds_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
        sheets_creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
        drive_creds = sheets_creds

# === Google Sheets ===
try:
    gc = gspread.authorize(sheets_creds)
    ssid = os.getenv("SPREADSHEET_ID", "1mRxH3sRqq_FsXa5KRyMJZLqMEIMBIjPf1U312me0TBA")
    try:
        dashboard = gc.open_by_key(ssid)
    except:
        dashboard = gc.open("Lab Test Bioflok") # Fallback to name
    print(f"✅ Connected to Spreadsheet: {dashboard.title}")
except Exception as e:
    print(f"❌ Error connecting to Google Sheets: {e}")
    dashboard = None

# Define Worksheets (Safe Init)
# Define Worksheets (Safe Init)
def get_worksheet(name, headers):
    if not dashboard: return None
    
    # 1. Try exact match
    try:
        ws = dashboard.worksheet(name)
        # Check/Update Header if found
        try:
             # Basic check: if A1 is empty, likely new/empty
             if not ws.acell('A1').value:
                 ws.append_row(headers)
                 ws.format('A1:Z1', {'textFormat': {'bold': True}})
        except: pass
        return ws
    except gspread.WorksheetNotFound:
        # 2. Try Case-Insensitive Match
        try:
            all_sheets = dashboard.worksheets()
            for sheet in all_sheets:
                if sheet.title.lower() == name.lower():
                    print(f"⚠️ Found sheet '{sheet.title}' matching '{name}', using it.")
                    return sheet
        except: pass

        # 3. Create New
        try:
            ws = dashboard.add_worksheet(title=name, rows=1000, cols=15)
            ws.append_row(headers)
            ws.format('A1:Z1', {'textFormat': {'bold': True}})
            return ws
        except Exception as e:
             print(f"❌ Failed to create worksheet '{name}': {e}")
             return None

# [MODIFIKASI] Definisi Header Baru (Sesuai 3 Kategori)
# 1. Water Quality (Value & ADC first, then Photos at far right)
WATER_HEADERS = [
    "Timestamp", "Type", "Device", 
    "DO", "DO ADC", 
    "pH", "pH ADC", 
    "TDS", "TDS ADC", 
    "Temp", "Temp ADC",
    "DO Photo", "pH Photo", "TDS Photo", "Temp Photo",
    "Note"
]

# 2. Media - General Video (Pond Condition)
VIDEO_HEADERS = ["Timestamp", "Reporter ID", "Video Link", "Note"]

# 3. Machine - Inverter Data (Manual Input)
INVERTER_HEADERS = [
    "Timestamp", "Reporter ID", 
    "Inverter Feed (Hz)", "Inverter Feed Photo",
    "Inverter Rest (Hz)", "Inverter Rest Photo",
    "Note"
]

# 4. Farm Control (Mesin & Infrastruktur IoT)
# AC/DC Status | Relay Status
CONTROL_HEADERS = [
    "Timestamp", "Type", "Device",          # Unified Header Pattern
    "AC Status", "DC Status",               # Optocoupler Inputs (ON/OFF or 1/0)
    "Pump Relay", "Aerator Relay",          # Relay Outputs
    "Note"
]

# 5. Biological Data (SPLIT TABS)
# Added Reporter ID to all Bio tabs
DEAD_FISH_HEADERS = ["Timestamp", "Reporter ID", "Count", "Photo Link", "Note"]

# [CONSOLIDATED] Feed Tracker - Unified tab for all feeding data
# Data only from client CSV (no assumptions)
FEED_TRACKER_HEADERS = [
    "Date", "Day", "Pangan (kg)", "Harga/kg", "Biaya Harian", 
    "Photo Link", "Reporter", "Note"
]

# [MODIFIKASI] Weekly Sampling (Format Lebar + Rata2)
# Added Reporter ID as requested
SAMPLING_HEADERS = ["Timestamp", "Reporter ID", "Avg Weight (g)", "Avg Length (cm)"]
for i in range(1, 31):
    SAMPLING_HEADERS.extend([f"Fish {i} Photo", f"Fish {i} Weight", f"Fish {i} Length"])

# 5. Config Tab (Thresholds)
# Split Alerts (Low/High) - No Action Column
THRESHOLD_HEADERS = ["Parameter", "Min Value", "Max Value", "Unit", "Alert Low", "Alert High"]

# 6. [REMOVED] Dashboard tab no longer used - diagnosis reads from source tabs directly
# DASHBOARD_HEADERS kept for reference only
DASHBOARD_HEADERS = [
    "Last Update", 
    "DO (mg/L)", "pH", "Temperature (C)", "TDS (ppm)", 
    "AC Status", "DC Status", "Pump Relay", "Aerator Relay",
    "Dead Fish", "Feed Weight", 
    "Current Diagnosis"
]

# 7. Matrix Diagnosis (Knowledge Base)
MATRIX_HEADERS = [
    "Index", "Frequency", "Diagnosis", 
    "Low DO", "High DO", "Low Pump", "High Pump", "Low pH", "High pH", 
    "Low Temp", "High Temp", "Low Death", "High Death", "Low SR", "High SR", 
    "Low Weight", "High Weight", "Low Feed", "High Feed", 
    "Power Outage", "High Biomass", "Cost ($)"
]

# 8. AI Event Log Analysis (History of triggered diagnoses)
EVENT_LOG_HEADERS = ["Timestamp", "Diagnosis", "Trigger Data", "Note", "Actual_Diagnosis", "Status_Match"]

# Initialize Tabs
water_tab = get_worksheet("Water Quality", WATER_HEADERS)
control_tab = get_worksheet("Farm Control", CONTROL_HEADERS)
video_tab = get_worksheet("Media - General Video", VIDEO_HEADERS)
inverter_tab = get_worksheet("Machine - Inverter Data", INVERTER_HEADERS)

# Bio Tabs
dead_fish_tab = get_worksheet("Bio - Dead Fish", DEAD_FISH_HEADERS)
sampling_tab = get_worksheet("Sampling", SAMPLING_HEADERS)  # Renamed for clarity

# Config (Dashboard removed - no longer needed)
threshold_tab = get_worksheet("THRESHOLD", THRESHOLD_HEADERS)
# realtime_tab = None  # Dashboard tab removed
matrix_tab = get_worksheet("Matrix Diagnosis", MATRIX_HEADERS)
event_log_tab = get_worksheet("AI Event Log Analysis", EVENT_LOG_HEADERS)

# === FEED TRACKER (Consolidated - Sukabumi Pilot Farm Methodology) ===

# Unified Feed Tracker Tab (replaces 3 old tabs)
feed_tracker_tab = get_worksheet("Feed Tracker", FEED_TRACKER_HEADERS)

# Target Pangan - Reference data from Sukabumi
TARGET_FEED_HEADERS = [
    "Minggu", "Bobot Target (g)", "Feed Rate (%)", "Pangan Target (kg)", "FCR Standard"
]
target_feed_tab = get_worksheet("Target Pangan", TARGET_FEED_HEADERS)

# FCR Analysis - Feed Conversion Ratio tracking (from client CSV Row 88-93)
FCR_ANALYSIS_HEADERS = [
    "Minggu", "Kenaikan Bobot (kg)", "Pakan Mingguan (kg)", "FCR Real", "FCR Target", "Status"
]
fcr_analysis_tab = get_worksheet("FCR Analysis", FCR_ANALYSIS_HEADERS)

# Backward compatibility aliases
feed_tab = feed_tracker_tab  # Alias for old code
daily_feed_tab = feed_tracker_tab  # Alias for old code
weekly_feed_tab = None  # Removed - calculated dynamically

daily_tab = water_tab # Fallback compatibility
weekly_tab = sampling_tab  # Fallback compatibility

# === AI Dashboard & Diagnosis ===

def update_dashboard(data_dict):
    """
    [UPDATED] Dashboard tab removed. Now only triggers diagnosis.
    Called after data is logged to source tabs.
    """
    try:
        run_diagnosis()
    except Exception as e:
        print(f"⚠️ Auto-diagnosis error: {e}")

def run_diagnosis():
    """
    [UPDATED] Uses new diagnosis_engine for consistent results.
    Reads from source tabs directly (no Dashboard dependency).
    Logs to Event Log and notifies experts if diagnosis changes.
    """
    if not event_log_tab: return
    
    try:
        from diagnosis_engine import _fetch_all_data, _evaluate_rules, _match_matrix, _check_emergency
        
        # Run full diagnosis pipeline
        rules, tab_data, matrix_data = _fetch_all_data()
        snapshot, data_values = _evaluate_rules(rules, tab_data)
        results = _match_matrix(snapshot, matrix_data)
        emergencies = _check_emergency(snapshot, data_values)
        
        if not results:
            print("✅ Auto-Diagnosis: No issues detected")
            return
        
        top = results[0]
        diag_text = top["diagnosis"]
        score = int(top["final_score"])
        
        # Only log if score >= 40% (meaningful match)
        if score < 40:
            print(f"✅ Auto-Diagnosis: Top match below threshold ({score}%)")
            return
        
        # Check if diagnosis changed from last event log entry
        try:
            log_data = event_log_tab.get_all_values()
            last_diag = log_data[-1][1] if len(log_data) > 1 else ""
        except:
            last_diag = ""
        
        if diag_text == last_diag:
            print(f"📉 Auto-Diagnosis: Same as last ({diag_text[:40]}), skipping log")
            return
        
        # Build trigger summary
        triggers = [f"{k}:{v}" for k, v in snapshot.items() if v == "PASS"]
        trigger_str = ", ".join(triggers)
        
        # Log without Gemini (save API quota for manual 'analisa' requests)
        ai_note = f"Auto-Diagnosis ({score}%): {top['matched']}/{top['total']} conditions matched"
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        event_log_tab.append_row([timestamp, diag_text, trigger_str, ai_note, "", ""])
        print(f"🚨 Matrix Diagnosis: {diag_text[:50]} ({score}%) | Logged")
        
        # Emergency notification
        if emergencies:
            try:
                from scheduler import notify_experts
                sensor_ctx = {p: info["value"] for p, info in data_values.items()}
                notify_experts("SYSTEM-AUTO", sensor_ctx)
            except: pass
    
    except Exception as e:
        print(f"⚠️ Diagnosis matching error: {e}")
        import traceback
        traceback.print_exc()







# === Google Drive ===
drive_service = build('drive', 'v3', credentials=drive_creds)
TARGET_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")

# In-memory store for first daily reading
daily_buffer = {}

def upload_photo(field_name, phone, date, file_url):
    """
    Upload photo to Google Drive. NO FALLBACK - must succeed!
    """
    print(f"📸 Uploading {field_name} from {phone}")
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Download from Twilio with auth
            print(f"📥 Downloading from Twilio (attempt {retry_count + 1}/{max_retries})...")
            response = requests.get(
                file_url,
                auth=HTTPBasicAuth(TWILIO_SID, TWILIO_AUTH),
                headers={"User-Agent": "Mozilla/5.0"},
                verify=False,
                timeout=30
            )
            
            print(f"📥 Download response: Status {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ Failed to download media. Status: {response.status_code}")
                retry_count += 1
                if retry_count < max_retries:
                    print(f"   ⏳ Retrying in 2 seconds...")
                    import time
                    time.sleep(2)
                    continue
                else:
                    raise Exception(f"Failed to download from Twilio after {max_retries} attempts. Status: {response.status_code}")

            # Check if it's a video
            is_video = file_url.endswith(".mp4") or "video" in response.headers.get("Content-Type", "")
            
            # Set filename
            if field_name == "general_video":
                filename = f"WATER CONDITIONS {date}.mp4"
            else:
                filename = f"{field_name.upper()} {date}.jpg"

            # Upload to Google Drive
            print(f"📤 Uploading to Drive folder: {TARGET_FOLDER_ID}")
            
            media = MediaIoBaseUpload(
                io.BytesIO(response.content), 
                mimetype='video/mp4' if is_video else 'image/jpeg'
            )
            file_metadata = {
                'name': filename,
                'parents': [TARGET_FOLDER_ID] if TARGET_FOLDER_ID else []
            }
            
            uploaded_file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id',
                supportsAllDrives=True
            ).execute()

            file_id = uploaded_file['id']
            
            # Make file publicly readable
            drive_service.permissions().create(
                fileId=file_id,
                body={'role': 'reader', 'type': 'anyone'},
                supportsAllDrives=True
            ).execute()

            link = f"https://drive.google.com/uc?id={file_id}"
            print(f"✅ Uploaded to Drive: {filename} → {link}")
            return link
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Upload error (attempt {retry_count + 1}): {e}")
            
            # Retry on transient errors
            if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                retry_count += 1
                if retry_count < max_retries:
                    print(f"   ⏳ Retrying in 2 seconds...")
                    import time
                    time.sleep(2)
                    continue
            
            # Fatal errors - don't retry
            if "storageQuotaExceeded" in error_msg:
                print(f"❌ FATAL: Drive storage quota exceeded!")
                print(f"   💡 SOLUSI:")
                print(f"   1. Pastikan OAuth sudah configured (token.pickle exists)")
                print(f"   2. Jalankan: python oauth_authorize.py")
                print(f"   3. Restart server")
                raise Exception("Drive storage quota exceeded. Run oauth_authorize.py first!")
            
            # Other errors
            import traceback
            traceback.print_exc()
            
            retry_count += 1
            if retry_count < max_retries:
                print(f"   ⏳ Retrying in 2 seconds...")
                import time
                time.sleep(2)
            else:
                raise Exception(f"Failed to upload photo after {max_retries} attempts: {error_msg}")
    
    # If we get here, all retries failed
    raise Exception(f"Failed to upload photo to Drive after {max_retries} attempts")


def log_reading(phone, data_dict):
    """
    Log manual reading from WhatsApp to multiple tabs based on data type.
    Updated for SPLIT BIOLOGICAL TABS and DASHBOARD integration.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Update Real-time Dashboard
    update_dashboard(data_dict)
    
    # 1. Log to Water Quality Tab (if DO/pH/Temp/TDS exists)
    water_keys = ["do", "ph", "temp", "tds"]
    if any(k in data_dict for k in water_keys):
        row = [
            timestamp, "Manual", phone,
            data_dict.get("do", ""), "", # DO, ADC
            data_dict.get("ph", ""), "", # pH, ADC
            data_dict.get("tds", ""), "", # TDS, ADC
            data_dict.get("temp", ""), "", # Temp, ADC
            data_dict.get("do_photo", ""),
            data_dict.get("ph_photo", ""),
            data_dict.get("tds_photo", ""),
            data_dict.get("temp_photo", ""),
            data_dict.get("note", "")
        ]
        water_tab.append_row(row)
        print("✅ Logged to Water Quality")

    # 1B. Log to General Video Tab
    if "general_video" in data_dict or "general_video_photo" in data_dict:
        video_link = data_dict.get("general_video_photo") or data_dict.get("general_video", "")
        if str(video_link).startswith("http"):
            row = [timestamp, phone, video_link, data_dict.get("note", "")]
            video_tab.append_row(row)
            print("✅ Logged to Media - General Video")

    # 2. Log to Farm Control (IoT Machinery)
    control_keys = ["ac_status", "dc_status", "pump_relay", "aerator_relay"]
    if any(k in data_dict for k in control_keys):
        row = [
            timestamp, "Manual", phone,
            data_dict.get("ac_status", ""),
            data_dict.get("dc_status", ""),
            data_dict.get("pump_relay", ""),
            data_dict.get("aerator_relay", ""),
            data_dict.get("control_note", "")
        ]
        control_tab.append_row(row)
        print("✅ Logged to Farm Control")

    # 2B. Log to Machine - Inverter Data (Manual)
    if "inv_feed" in data_dict or "inv_rest" in data_dict:
        row = [
            timestamp, phone,
            data_dict.get("inv_feed", ""), data_dict.get("inv_feed_photo", ""),
            data_dict.get("inv_rest", ""), data_dict.get("inv_rest_photo", ""),
            data_dict.get("control_note", "") or data_dict.get("note", "")
        ]
        inverter_tab.append_row(row)
        print("✅ Logged to Machine - Inverter Data")

    # 3. Log to Bio - Dead Fish
    if "dead_fish" in data_dict:
        row = [
            timestamp, phone,
            data_dict.get("dead_fish", ""),
            data_dict.get("dead_fish_photo", ""),
            data_dict.get("bio_note", "")
        ]
        dead_fish_tab.append_row(row)
        print("✅ Logged to Bio - Dead Fish")

    # 4. Log to Bio - Feeding Data (Merged)
    if "feed_weight" in data_dict or "feeding_freq" in data_dict:
        row = [
            timestamp, phone,
            data_dict.get("feed_weight", ""),
            data_dict.get("feeding_freq", ""),
            data_dict.get("feed_weight_photo", ""),
            data_dict.get("bio_note", "")
        ]
        feed_tab.append_row(row)
        print("✅ Logged to Bio - Feeding Data")

def log_sensor_data(device_id, sensor_data):
    """
    Log automatic sensor data to Water Quality and Control Tabs.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Update Real-time Dashboard
    update_dashboard(sensor_data)
    
    # 1. Log to Water Quality
    if any(k in sensor_data for k in ["do", "ph", "tds", "temp"]):
        row = [
            timestamp, "IoT-Sensor", device_id,
            sensor_data.get("do", ""), sensor_data.get("do_adc", ""),
            sensor_data.get("ph", ""), sensor_data.get("ph_adc", ""),
            sensor_data.get("tds", ""), sensor_data.get("tds_adc", ""),
            sensor_data.get("temp", ""), sensor_data.get("temp_adc", ""),
            "", "", "", "", # Photo columns (empty for IoT)
            "" # Note
        ]
        water_tab.append_row(row)
    
    # 2. Log to Farm Control (IoT Machinery Status)
    if any(k in sensor_data for k in ["ac_status", "dc_status", "pump_relay", "aerator_relay"]):
        row = [
            timestamp, "IoT-Sensor", device_id,
            sensor_data.get("ac_status", ""),
            sensor_data.get("dc_status", ""),
            sensor_data.get("pump_relay", ""),
            sensor_data.get("aerator_relay", ""),
            "" # Note
        ]
        control_tab.append_row(row)
        
    print(f"✅ Sensor data logged from {device_id}")

def log_weekly(phone, data_dict):
    """
    Log weekly sampling to 'Weekly Sampling Input' Tab.
    Format: [Timestamp, AvgW, AvgL, Fish1_Img, Fish1_W, Fish1_L, ... Fish30_L]
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Kumpulkan data detail
    details = []
    total_weight = 0
    total_length = 0
    count = 0
    
    for i in range(1, 31):
        w = data_dict.get(f"fish_{i}_weight", "")
        l = data_dict.get(f"fish_{i}_length", "")
        # Try multiple possible keys for the photo link
        # [FIX] Added 'fish_{i}_weight_photo' because app.py appends _photo to the key (which is fish_{i}_weight)
        p = data_dict.get(f"fish_{i}_photo") or data_dict.get(f"fish_{i}_weight_photo") or ""
        if not str(p).startswith("http"): p = "" # Ensure it's a link
        
        # Simpan ke list detail (untuk kolom Fish 1..30)
        details.extend([p, w, l])
        
        # Hitung rata-rata jika data valid
        try:
            val_w = float(w)
            val_l = float(l)
            if val_w > 0 and val_l > 0:
                total_weight += val_w
                total_length += val_l
                count += 1
        except: pass
            
    # Hitung Avg
    avg_weight = round(total_weight / count, 2) if count > 0 else 0
    avg_length = round(total_length / count, 2) if count > 0 else 0
    
    # Construct Final Row
    # Header: Timestamp, Reporter ID, Avg Weight, Avg Length, [Details...]
    row = [timestamp, phone, avg_weight, avg_length] + details
    
    print(f"DTO: {len(row)} columns")
    sampling_tab.append_row(row)
    print(f"✅ Weekly sampling logged to 'Weekly Sampling Input' (Reporter: {phone}, Avg: {avg_weight}g)")


def get_recent_trends(n=3):
    """Fetch and format last n rows of daily readings as AI prompt context."""
    try:
        records = daily_tab.get_all_records()
        if not records:
            return "No recent data available."

        recent = records[-n:]
        trend_lines = []
        for row in recent:
            timestamp = row.get("Timestamp", "Unknown time")
            do = row.get("DATA 1 - DO (mg/L)", "?")
            ph = row.get("DATA 3 - pH", "?")
            temp = row.get("DATA 5 - Temp (°C)", "?")
            deaths = row.get("DATA 9 - Fish Deaths", "?")
            trend_lines.append(
                f"{timestamp} — DO: {do}, pH: {ph}, Temp: {temp}, Deaths: {deaths}"
            )

        return "\n".join(trend_lines)
    except Exception as e:
        return f"⚠️ Error getting trends: {e}"

# [MODIFIKASI] Fungsi untuk mengambil data terakhir dari Spreadsheet
def get_latest_daily_data():
    try:
        # Ambil semua data (hati-hati jika data sangat banyak, tapi untuk pemula ini oke)
        # Lebih efisien ambil baris terakhir saja jika tahu jumlah baris
        all_values = daily_tab.get_all_values()
        
        if len(all_values) < 2: # Cuma header atau kosong
            return None
            
        headers = all_values[0]
        last_row = all_values[-1]
        
        # Gabungkan Header dengan Isinya
        data = {}
        for i in range(len(headers)):
            if i < len(last_row):
                data[headers[i]] = last_row[i]
            else:
                data[headers[i]] = "-" # Jika kosong
                
        return data
    except Exception as e:
        print(f"❌ Gagal ambil data: {e}")
        return None

def get_latest_logged_data():
    """
    Reads the absolute last rows from Water, Bio, and Control tabs 
    to reconstruct the current state for the Dashboard.
    """
    state = {}
    try:
        # Water Quality
        water_rows = water_tab.get_all_values()
        if len(water_rows) > 1:
            last = water_rows[-1]
            state.update({"do": last[3], "ph": last[5], "tds": last[7], "temp": last[9]})
        
        # Bio
        death_rows = dead_fish_tab.get_all_values()
        if len(death_rows) > 1: state["dead_fish"] = death_rows[-1][2]
        
        feed_rows = feed_tab.get_all_values()
        if len(feed_rows) > 1: state["feed_weight"] = feed_rows[-1][2]

        # Control
        control_rows = control_tab.get_all_values()
        if len(control_rows) > 1:
            last = control_rows[-1]
            state.update({"ac_status": last[3], "dc_status": last[4], "pump_relay": last[5], "aerator_relay": last[6]})

        return state
    except Exception as e:
        print(f"⚠️ Sync Error: {e}")
        return state

def check_and_sync_dashboard():
    """
    [UPDATED] Dashboard tab removed. Now triggers diagnosis from source tabs.
    """
    try:
        run_diagnosis()
        return True
    except Exception as e:
        print(f"❌ Auto Sync Failed: {e}")
        return False

# [MODIFIKASI] Fungsi Baru: Log ke Tab Khusus AI
def log_ai_analysis(category, input_data, analysis_text):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Format input data jadi string ringkas
        input_str = ", ".join([f"{k}: {v}" for k,v in input_data.items()])
        
        row = [timestamp, category, input_str, analysis_text]
        if event_log_tab:
            event_log_tab.append_row(row)
            print(f"✅ Analisa AI tersimpan di tab 'AI Event Log Analysis' ({category})")
            return True
        return False
    except Exception as e:
        print(f"❌ Gagal simpan log AI: {e}")
        return False


# === FEED TRACKER FUNCTIONS (Sukabumi Pilot Farm Methodology) ===

def log_daily_feed(pangan_kg: float, harga_per_kg: float = 11000, 
                   photo_link: str = "", reporter: str = "", note: str = ""):
    """
    Log pakan harian ke tab 'Feed Tracker' (consolidated tab).
    Data hanya dari client CSV, tanpa asumsi.
    
    Args:
        pangan_kg: Berat pakan yang diberikan hari ini (kg)
        harga_per_kg: Harga pakan per kg (dari client data)
        photo_link: Link foto pakan (optional)
        reporter: Nomor WhatsApp reporter
        note: Catatan tambahan
    
    Returns:
        Dict with status and day number
    """
    if not feed_tracker_tab:
        return {"status": "ERROR", "message": "Tab 'Feed Tracker' tidak tersedia"}
    
    try:
        # Get current data to calculate Day number
        all_data = feed_tracker_tab.get_all_values()
        day_number = len(all_data)  # Row 1 = header, so len = day number
        
        # Calculate biaya harian
        biaya_harian = pangan_kg * harga_per_kg
        
        # Create row (matches FEED_TRACKER_HEADERS - client data only)
        # Date, Day, Pangan (kg), Harga/kg, Biaya Harian, Photo Link, Reporter, Note
        date_str = datetime.now().strftime("%Y-%m-%d")
        row = [
            date_str,
            day_number,
            pangan_kg,
            harga_per_kg,
            biaya_harian,
            photo_link,
            reporter,
            note
        ]
        
        feed_tracker_tab.append_row(row)
        
        return {
            "status": "SUCCESS",
            "day": day_number,
            "date": date_str,
            "pangan_kg": pangan_kg,
            "biaya": f"Rp{biaya_harian:,.0f}"
        }
        
    except Exception as e:
        print(f"❌ Error logging daily feed: {e}")
        return {"status": "ERROR", "message": str(e)}


def get_daily_feed_count():
    """Get total number of days logged."""
    if not feed_tracker_tab:
        return 0
    try:
        all_data = feed_tracker_tab.get_all_values()
        return max(0, len(all_data) - 1)  # Exclude header
    except:
        return 0


def get_weekly_feed_summary(week_number: int = None):
    """
    Get summary of feed for a specific week or current week.
    Dynamically calculates from Feed Tracker tab.
    
    Args:
        week_number: Week number to get. If None, calculate current week.
    
    Returns:
        Dict with weekly totals and FCR
    """
    if not feed_tracker_tab:
        return {"status": "ERROR", "message": "Tab tidak tersedia"}
    
    try:
        all_data = feed_tracker_tab.get_all_values()
        if len(all_data) < 2:
            return {"status": "NO_DATA", "message": "Belum ada data pakan"}
        
        # Calculate current week if not specified
        total_days = len(all_data) - 1
        current_week = (total_days - 1) // 7 + 1
        
        if week_number is None:
            week_number = current_week
        
        # Get data for the specified week
        start_day = (week_number - 1) * 7 + 1
        end_day = min(week_number * 7, total_days)
        
        if start_day > total_days:
            return {"status": "NO_DATA", "message": f"Minggu {week_number} belum ada datanya"}
        
        # Sum feed for the week
        total_pangan = 0
        total_biaya = 0
        start_date = ""
        end_date = ""
        
        for i in range(start_day, end_day + 1):
            row = all_data[i]
            if len(row) >= 7:
                try:
                    pangan = float(row[2]) if row[2] else 0
                    biaya = float(row[6]) if row[6] else 0
                    total_pangan += pangan
                    total_biaya += biaya
                    
                    if not start_date and row[0]:
                        start_date = row[0]
                    end_date = row[0] if row[0] else end_date
                except:
                    continue
        
        return {
            "status": "SUCCESS",
            "minggu": week_number,
            "tanggal_mulai": start_date,
            "tanggal_akhir": end_date,
            "total_pangan_kg": round(total_pangan, 2),
            "total_biaya": f"Rp{total_biaya:,.0f}",
            "total_biaya_raw": total_biaya,
            "hari_tercatat": end_day - start_day + 1
        }
        
    except Exception as e:
        print(f"❌ Error getting weekly summary: {e}")
        return {"status": "ERROR", "message": str(e)}


def populate_target_feed():
    """
    Populate Target Pangan tab with data from Sukabumi Pilot Farm.
    Only adds data if tab is empty.
    """
    if not target_feed_tab:
        return False
    
    try:
        all_data = target_feed_tab.get_all_values()
        if len(all_data) > 1:  # Already has data
            return True
        
        # Target data from Sukabumi Pilot Farm (16 weeks)
        targets = [
            [1, 9.55, 5.0, 37.40, 1.20],
            [2, 14.58, 5.0, 56.55, 1.20],
            [3, 19.61, 2.5, 37.62, 1.20],
            [4, 24.64, 2.5, 47.01, 1.20],
            [5, 29.68, 2.5, 46.57, 1.20],
            [6, 40.57, 2.5, 51.46, 1.20],
            [7, 45.00, 2.5, 57.28, 1.20],
            [8, 53.16, 2.5, 66.75, 1.20],
            [9, 63.35, 2.5, 77.98, 1.20],
            [10, 75.25, 2.5, 62.35, 1.20],
            [11, 91.00, 2.5, 110.56, 1.20],
            [12, 105.00, 2.5, 173.19, 1.20],
            [13, 117.00, 2.5, 208.43, 1.20],
            [14, 130.00, 2.5, 243.58, 1.20],
            [15, 140.00, 2.5, 278.77, 1.20],
            [16, 148.08, 2.5, 148.08, 1.20],
        ]
        
        for row in targets:
            target_feed_tab.append_row(row)
        
        print("✅ Target Pangan populated from Sukabumi Pilot Farm data")
        return True
        
    except Exception as e:
        print(f"❌ Error populating target feed: {e}")
        return False


def get_target_feed(week_number: int):
    """Get target feed for a specific week."""
    if not target_feed_tab:
        return None
    
    try:
        all_data = target_feed_tab.get_all_values()
        for row in all_data[1:]:  # Skip header
            if len(row) >= 5:
                try:
                    if int(row[0]) == week_number:
                        return {
                            "minggu": week_number,
                            "bobot_target_g": float(row[1]),
                            "feed_rate_pct": float(row[2]),
                            "pangan_target_kg": float(row[3]),
                            "fcr_standard": float(row[4])
                        }
                except:
                    continue
        return None
    except:
        return None
