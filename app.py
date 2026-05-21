from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
from forms.daily_form import daily_form_id
from forms.weekly_form import weekly_form_id
from drive import log_reading, log_weekly, upload_photo, get_latest_daily_data, log_ai_analysis
from scheduler import (
    send_whatsapp_message,
    notify_experts,
    send_daily_reminder,
    schedule_jobs,
    update_last_activity
)
import os
import re
import threading
from datetime import datetime
from ai_helper import check_out_of_range, generate_recommendations # [MODIFIKASI] Import AI helper untuk fitur manual

# [NEW] Import IoT monitoring modules
try:
    from do_analyzer import format_aerasi_response, get_aeration_recommendation
    from ph_drift_detector import format_calibration_response, format_troubleshoot_response
    from feed_calculator import format_pakan_response, format_log_pakan_response, format_rekap_pakan_response
    from diagnosis_engine import format_diagnosa_response, format_diagnosa_detail, generate_diagnosa_explanation, force_reload_config
    IOT_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ IoT modules not fully loaded: {e}")
    IOT_MODULES_AVAILABLE = False

load_dotenv()
app = Flask(__name__)
user_state = {}

# === Async Reply Helper ===

def send_async_reply(to_number: str, message: str):
    """Kirim pesan WA via Twilio REST API (untuk dipakai di background thread)."""
    # Twilio WhatsApp limit: 1600 karakter
    MAX_CHARS = 1500
    if len(message) > MAX_CHARS:
        message = message[:MAX_CHARS - 30].rsplit("\n", 1)[0] + "\n\n_...(pesan dipotong)_"

    # Selalu print ke terminal dulu (bisa dipantau meski Twilio limit habis)
    print(f"\n{'='*50}")
    print(f"📋 [ASYNC OUTPUT] → {to_number}")
    print(f"{'='*50}")
    print(message)
    print(f"{'='*50}\n")

    try:
        from twilio.rest import Client
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_PHONE_NUMBER", "whatsapp:+14155238886")
        client = Client(account_sid, auth_token)
        client.messages.create(
            from_=from_number,
            to=f"whatsapp:{to_number}",
            body=message
        )
        print(f"📤 [ASYNC] Pesan terkirim ke {to_number} ({len(message)} chars)")
    except Exception as e:
        print(f"⚠️ [ASYNC] Gagal kirim ke WA (pesan tetap tercetak di atas): {e}")

# === Utilities ===

# === Utilities ===

def extract_number(text):
    if not text: return None
    # [MODIFIKASI] Auto-Format: Ganti koma jadi titik (6,5 -> 6.5)
    text = text.replace(",", ".")
    match = re.search(r"[-+]?\d*\.\d+|\d+", text)
    return match.group() if match else None

def get_daily_menu_text(responses):
    # Helper untuk menampilkan Menu Harian dengan status Checklist
    menu = "❓ **Pilih Data yang Ingin Diisi:**\n(Ketik angka menu, atau 'Selesai' untuk proses)\n\n"
    
    cats = [
        ("💧 **KUALITAS AIR**", [("do", "1", "do"), ("ph", "2", "ph"), ("temp", "3", "suhu"), ("tds", "4", "tds")]),
        ("🐟 **FISIK & PAKAN**", [("dead_fish", "5", "mati"), ("feeding_freq", "6", "freq"), ("feed_weight", "7", "berat")]),
        ("⚙️ **MESIN**", [("inv_feed", "8", "invp"), ("inv_rest", "9", "invr"), ("pump_relay", "11", "pompa"), ("aerator_relay", "12", "kincir")]),
        ("🎬 **MEDIA**", [("general_video", "10", "video")])
    ]
    
    for title, items in cats:
        menu += f"{title}\n"
        for key, code, keyword in items:
            # Cari nama display dari daily_form_id
            item_def = next((x for x in daily_form_id if x["key"] == key), None)
            if item_def:
                status = "✅" if key in responses else "⚪"
                # Menambahkan kode keyboard dalam kurung [kode]
                menu += f"{code}. {item_def['name']} [{keyword}] {status}\n"
        menu += "\n"
        
    menu += "✅ Ketik **'Selesai'** jika pelaporan sudah cukup.\n\n"
    menu += "💡 **Tips:** Bapak bisa isi cepat dengan ketik kodenya!\n"
    menu += "Contoh: `do 5.5 ph 7.2 mati 0`"
    return menu

# === Webhook Route ===

@app.route("/webhook/config-update", methods=["GET", "POST"])
def config_update_webhook():
    """Endpoint for Google Apps Script to notify config changes."""
    try:
        force_reload_config()
        print("🚀 Received update signal from Spreadsheet! Config reloaded.")
        return "Config Reloaded", 200
    except Exception as e:
        print(f"⚠️ Webhook update error: {e}")
        return f"Error: {e}", 500

@app.route("/webhook/sensor-update", methods=["POST"])
def sensor_update_webhook():
    """
    Endpoint for Google Apps Script to notify NEW SENSOR DATA.
    Triggered when ESP32 writes to 'Water Quality' or 'Farm Control'.
    """
    try:
        req_data = request.json
        sheet_name = req_data.get("sheet", "Unknown") if req_data else "Unknown"
        print(f"📡 New Sensor Data Signal from: {sheet_name}")

        # 1. Fetch Latest Data
        # We allow a small delay for GSheets to commit the write
        import time
        time.sleep(1) 
        
        # 2. Run Diagnosis & Check Alerts
        from drive import run_diagnosis
        # run_diagnosis() will internally log to 'AI Event Log'
        # AND it calls 'notify_experts' if there is an EMERGENCY.
        
        # We can also force a specific notification if it's Farm Control (Status Change)
        if sheet_name == "Farm Control":
             from drive import control_tab
             rows = control_tab.get_all_values()
             if len(rows) > 1:
                 last = rows[-1]
                 # AC=3, DC=4, Pump=5, Aerator=6
                 msg = f"🔧 *STATUS KONTROL UPDATE*\n\nAC: {last[3]}\nDC: {last[4]}\nPompa: {last[5]}\nAerator: {last[6]}"
                 notify_experts("CONTROL-UPDATE", msg)

        # For Water Quality (or fallback unknown), we handle the notification manually
        if sheet_name == "Water Quality" or "Unknown" in sheet_name:
             print("📡 Fetching latest sensor data for notification...")
             from diagnosis_engine import get_latest_sensor_data
             
             # Ambil data sensor mentah terbaru
             latest_data = get_latest_sensor_data()
             
             if latest_data:
                 # Format Pesan Notifikasi
                 timestamp = latest_data.get("timestamp", "Baru Saja")
                 do_val = latest_data.get("do", "-")
                 ph_val = latest_data.get("ph", "-")
                 temp_val = latest_data.get("temperature", "-")

                 msg = (
                     f"📡 *DATA SENSOR MASUK!* 📡\n"
                     f"🕒 {timestamp}\n\n"
                     f"💧 DO: {do_val} mg/L\n"
                     f"🧪 pH: {ph_val}\n"
                     f"🌡️ Suhu: {temp_val} °C\n\n"
                     f"_Balas 'diagnosa' untuk analisa lengkap._"
                 )
                 
                 # Kirim WA ke Pakar
                 notify_experts("SENSOR-IN", msg)
                 
                 # Tetap jalankan diagnosa di background (untuk log AI)
                 # Tapi tidak perlu kirim notif double (kecuali emergency)
                 # run_diagnosis_logic(latest_data) -> Opsional kalau mau
             else:
                 print("⚠️ Gagal mengambil data terbaru untuk notifikasi.")
                 
        return "Data Processed", 200

        return "Data Processed", 200
    except Exception as e:
        print(f"⚠️ Sensor webhook error: {e}")
        return f"Error: {e}", 500

@app.route("/webhook", methods=["POST"])
@app.route("/whatsapp", methods=["POST"])  # Support both endpoints
def whatsapp_reply():
    sender = request.form.get("From").replace("whatsapp:", "")
    msg_text = request.form.get("Body", "").strip() # Jangan lower dulu biar case sensitive kalau perlu
    msg_lower = msg_text.lower()
    media_url = request.form.get("MediaUrl0")
    
    print(f"\n📩 PESAN MASUK dari {sender}: {msg_text} | Media: {media_url}") 

    resp = MessagingResponse()
    msg = resp.message()
    
    def reply(r):
        print(f"📤 MEMBALAS: {str(r)}")
        return str(r)

    # [GLOBAL RULE 1] Navigasi 'q' / 'menu' -> RESET
    if msg_lower in ["q", "quit", "batal", "menu", "halo", "start", "hi", "test", "hello", "hallo", "p", "ping"]:
        user_state[sender] = {"stage": "menu", "responses": {}, "media": {}, "form_type": None, "session_history": []}
        msg.body("🌊 **Smart Aquaculture System Ready.**\n"
                 "Silakan pilih aktivitas:\n\n"
                 "1️⃣ **Input Laporan Harian**\n"
                 "2️⃣ **Laporan Mingguan**\n"
                 "3️⃣ **Cek Data Terakhir**\n"
                 "4️⃣ **Analisa AI Spesifik**\n"
                 "5️⃣ 📂 **Buka Database** (Spreadsheet)\n\n"
                 "--- 🔬 IoT Monitoring ---\n"
                 "6️⃣ 💨 **Cek Aerasi** (DO Analysis)\n"
                 "7️⃣ 🐟 **Kalkulasi Pakan**\n"
                 "8️⃣ 🔧 **Kalibrasi pH**\n"
                 "9️⃣ 🔬 **Diagnosa Kolam**")
        return reply(resp)

    # Init State
    if sender not in user_state:
        user_state[sender] = {"stage": "menu"}
        msg.body("🌊 **Smart Aquaculture System Ready.**\n"
                 "Silakan pilih aktivitas:\n\n"
                 "1️⃣ **Input Laporan Harian**\n"
                 "2️⃣ **Laporan Mingguan**\n"
                 "3️⃣ **Cek Data Terakhir**\n"
                 "4️⃣ **Analisa AI Spesifik**\n"
                 "5️⃣ 📂 **Buka Database** (Spreadsheet)\n\n"
                 "--- 🔬 IoT Monitoring ---\n"
                 "6️⃣ 💨 **Cek Aerasi** (DO Analysis)\n"
                 "7️⃣ 🐟 **Kalkulasi Pakan**\n"
                 "8️⃣ 🔧 **Kalibrasi pH**\n"
                 "9️⃣ 🔬 **Diagnosa Kolam**")
        return reply(resp)

    state = user_state[sender]
    stage = state.get("stage")

    # === MENU UTAMA (HYBRID) ===
    if stage == "menu":
        if msg_lower == "1":
            state["stage"] = "daily_menu"
            state["form_type"] = "daily"
            if "responses" not in state: state["responses"] = {}
            msg.body(get_daily_menu_text(state["responses"]) + 
                     "\n\n� *Tips: Bapak bisa langsung kirim deretan angka (misal: 5.5 7.2 28) untuk isi cepat!*")
        
        elif msg_lower == "2":
            state["stage"] = "weekly_in_progress"
            state["form_type"] = "weekly"
            state["form"] = weekly_form_id
            state["step"] = 0
            state["responses"] = {}
            msg.body(weekly_form_id[0]["prompt"])
            
        elif msg_lower == "3":
            # Logic Cek Data Terakhir (reads from WATER QUALITY tab)
            data = get_latest_daily_data()
            if data:
                resp_text = "📊 **DATA TERAKHIR**\n"
                for k,v in data.items():
                    if v and v != "-": resp_text += f"• {k}: {v}\n"
                resp_text += "\nKetik '9' untuk diagnosa kolam.\nKetik 'Menu' untuk kembali."
                msg.body(resp_text)
            else:
                msg.body("⚠️ Belum ada data.")
                
        elif msg_lower == "4":
            # Logic AI Manual Trigger (Enhanced with Gemini) - ASYNC
            data = get_latest_daily_data()
            if data:
                # Langsung balas loading agar tidak timeout
                msg.body("🧠 *Sedang memproses analisa AI...* Hasilnya akan dikirim dalam beberapa detik.")

                # Proses AI di background thread
                def run_ai_analysis(target, sensor_ctx_copy):
                    try:
                        try:
                            diag = format_diagnosa_response()
                        except:
                            diag = "Tidak tersedia"
                        from ai_helper import generate_ai_analysis
                        ai_insight = generate_ai_analysis(sensor_ctx_copy, diag)
                        result = f"🧠 *ANALISA CERDAS GEMINI AI*\n\n{ai_insight}\n\nKetik 'Menu' untuk kembali."
                    except Exception as e:
                        error_str = str(e)
                        if "429" in error_str or "quota" in error_str.lower():
                            result = "⚠️ Kuota AI harian sudah habis. Coba lagi nanti."
                        else:
                            result = f"⚠️ Gagal memuat AI: {e}"
                    send_async_reply(target, result)

                sensor_ctx = {k: v for k, v in data.items() if v and v != "-"}
                t = threading.Thread(target=run_ai_analysis, args=(sender, sensor_ctx), daemon=True)
                t.start()
            else:
                msg.body("⚠️ Data tidak ditemukan untuk dianalisa.")
            
        elif msg_lower == "5":
            ssid = os.getenv("SPREADSHEET_ID", "1mRxH3sRqq_FsXa5KRyMJZLqMEIMBIjPf1U312me0TBA")
            spreadsheet_url = os.getenv("SPREADSHEET_URL", "https://docs.google.com/spreadsheets/d/" + ssid)
            msg.body(f"📂 **Akses Database Tambak**\n🔗 {spreadsheet_url}\n\nKetik 'Menu' untuk kembali.")
        
        # [NEW] IoT Monitoring Menu Options
        elif msg_lower == "6" or msg_lower.startswith("aerasi"):
            # DO Analysis & Aeration Recommendation (AI Copilot Integration)
            if not IOT_MODULES_AVAILABLE:
                msg.body("⚠️ Modul IoT belum tersedia.")
            else:
                try:
                    from do_analyzer import get_aeration_recommendation
                    from ai_helper import start_do_copilot
                    
                    # 1. Get math analysis (ringan, tidak pakai AI)
                    aeration_data = get_aeration_recommendation()
                    
                    if not aeration_data or aeration_data.get("aeration", None) is None:
                        msg.body("⚠️ Data DO belum cukup untuk dianalisa.")
                        return reply(resp)
                    
                    # 2. Simpan di memori sementara untuk dipakai AI nanti
                    state["last_aeration_data"] = aeration_data
                    
                    # 3. Langsung balas hasil perhitungan tanpa memanggil AI
                    msg_text_resp = aeration_data.get("message", "Data Aerasi berhasil dimuat.")
                    msg_text_resp += "\n\n🤖 *Punya pertanyaan lebih lanjut?*\nKetik *'tanya ai'* untuk konsultasi interaktif dengan Copilot mengenai kondisi diatas."
                    msg.body(msg_text_resp)
                except Exception as e:
                    msg.body(f"⚠️ Error: {e}")
                    
        elif msg_lower == "tanya ai":
            # AI Copilot Integration for DO Analysis
            if "last_aeration_data" not in state:
                msg.body("⚠️ Silahkan ketik 'aerasi' terlebih dahulu untuk menarik data terbaru sebelum memanggil AI.")
            else:
                try:
                    from ai_helper import start_do_copilot
                    aeration_data = state["last_aeration_data"]
                    
                    # Langsung balas loading
                    msg.body("💨 *Sedang memanggil DO Copilot...* Mohon tunggu sebentar.")

                    # Proses Copilot di background
                    def run_do_copilot(target, aer_data, st):
                        try:
                            initial_response, history = start_do_copilot(aer_data)
                            st["stage"] = "copilot_session"
                            st["session_history"] = history
                            full_response = f"💡 *DO COPILOT*\n\n{initial_response}\n\n_(Balas pesan ini untuk ngobrol, ketik 'Menu' untuk akhiri)_"
                            send_async_reply(target, full_response)
                        except Exception as e:
                            error_str = str(e)
                            if "429" in error_str or "quota" in error_str.lower():
                                send_async_reply(target, "⚠️ Kuota AI harian sudah habis (Free Tier Limit). Coba lagi nanti.")
                            else:
                                send_async_reply(target, f"⚠️ Error DO Copilot: {e}")

                    t = threading.Thread(target=run_do_copilot, args=(sender, aeration_data, state), daemon=True)
                    t.start()
                except Exception as e:
                    msg.body(f"⚠️ Error: {e}")
        
        elif msg_lower == "7" or msg_lower.startswith("pakan"):
            # Feed Calculation
            if not IOT_MODULES_AVAILABLE:
                msg.body("⚠️ Modul IoT belum tersedia.")
            else:
                try:
                    # Check if weight is provided
                    weight_match = re.search(r"\d+\.?\d*", msg_text)
                    weight = float(weight_match.group()) if weight_match and msg_lower != "7" else None
                    result = format_pakan_response(avg_weight_g=weight)
                    msg.body(result + "\n\nKetik 'Menu' untuk kembali.")
                except Exception as e:
                    msg.body(f"⚠️ Error: {e}")
        
        elif msg_lower == "8" or msg_lower.startswith("kalibrasi"):
            # pH Calibration Status
            if not IOT_MODULES_AVAILABLE:
                msg.body("⚠️ Modul IoT belum tersedia.")
            else:
                try:
                    result = format_calibration_response()
                    msg.body(result + "\n\nKetik 'troubleshoot ph' untuk panduan lengkap.\nKetik 'Menu' untuk kembali.")
                except Exception as e:
                    msg.body(f"⚠️ Error: {e}")
        
        elif msg_lower.startswith("troubleshoot"):
            # pH Troubleshooting Guide
            if not IOT_MODULES_AVAILABLE:
                msg.body("⚠️ Modul IoT belum tersedia.")
            else:
                try:
                    # Extract issue type if provided
                    parts = msg_lower.split()
                    issue_type = parts[1] if len(parts) > 1 else None
                    result = format_troubleshoot_response(issue_type=issue_type)
                    msg.body(result + "\n\nKetik 'Menu' untuk kembali.")
                except Exception as e:
                    msg.body(f"⚠️ Error: {e}")
        
        # [NEW] Diagnosa Kolam - Dynamic Matrix Diagnosis
        elif msg_lower == "9" or msg_lower.startswith("diagnosa"):
            if not IOT_MODULES_AVAILABLE:
                msg.body("⚠️ Modul IoT belum tersedia.")
            else:
                try:
                    result = format_diagnosa_response()
                    msg.body(result + "\n\n💡 *Ingin tahu kenapa hasilnya seperti ini?*\nKetik *'kenapa'* atau *'jelaskan'* untuk penjelasan detail.")
                except Exception as e:
                    msg.body(f"⚠️ Error diagnosa: {e}")

        # [NEW] Penjelasan Detail Diagnosa - "Kenapa hasilnya begini?"
        elif msg_lower in ["kenapa", "jelaskan", "detail diagnosa", "why", "explain"]:
            if not IOT_MODULES_AVAILABLE:
                msg.body("⚠️ Modul IoT belum tersedia.")
            else:
                try:
                    import drive
                    sh = drive.dashboard
                    if not sh:
                        msg.body("⚠️ Tidak dapat terhubung ke database.")
                    else:
                        hist_ws = sh.worksheet("Diagnosis History")
                        hist_data = hist_ws.get_all_values()
                        if len(hist_data) < 2:
                            msg.body("⚠️ Belum ada riwayat diagnosa.")
                        else:
                            headers = hist_data[0]
                            last_row = hist_data[-1]
                            
                            # Kolom tetap:
                            # 0=Timestamp, 1=Diagnosa, 2=Prob, 3=Match, 4=Kemungkinan Lain
                            # 5+ = Parameter dengan nilai "KW:val (context) → STATUS"
                            timestamp = last_row[0] if len(last_row) > 0 else "-"
                            diagnosa  = last_row[1] if len(last_row) > 1 else "-"
                            prob      = last_row[2] if len(last_row) > 2 else "-"
                            
                            detail_lines = []
                            for i, header in enumerate(headers[5:], start=5):
                                if i >= len(last_row): break
                                cell_val = last_row[i]
                                if not cell_val or cell_val.strip() == "": continue
                                
                                # Format: "KW:nilai (konteks) → PASS/FAIL"
                                if "→ PASS" in cell_val:
                                    status_icon = "✅"
                                    status_text = "PASS (Gejala Ditemukan)"
                                elif "→ FAIL" in cell_val:
                                    status_icon = "❌"
                                    status_text = "FAIL (Tidak Relevan)"
                                else:
                                    status_icon = "⚪"
                                    status_text = cell_val
                                
                                # Ambil bagian nilai sebelum tanda "→"
                                val_part = cell_val.split("→")[0].strip()
                                detail_lines.append(f"{status_icon} *{header}*\n   {val_part} → {status_text}")
                            
                            if detail_lines:
                                detail_text = "\n\n".join(detail_lines)
                                reply_msg = (
                                    f"📊 *PENJELASAN DIAGNOSA TERAKHIR*\n"
                                    f"🕐 {timestamp}\n"
                                    f"🩺 Hasil: *{diagnosa}* ({prob}%)\n\n"
                                    f"━━━━━━━━━━━\n"
                                    f"{detail_text}\n\n"
                                    f"━━━━━━━━━━━\n"
                                    f"💬 Nilai dalam kurung () = konteks syarat Logic yang dipakai.\n"
                                    f"Tanda @ = jam kejadian (Logika TIME).\n\n"
                                    f"Ketik 'Menu' untuk kembali."
                                )
                            else:
                                reply_msg = "⚠️ Tidak ada detail parameter yang bisa ditampilkan."
                            
                            msg.body(reply_msg)
                except Exception as e:
                    msg.body(f"⚠️ Error membaca penjelasan: {e}")
        # [NEW] Manual Refresh Command
        elif msg_lower in ["refresh", "reload", "update rules"]:
            if not IOT_MODULES_AVAILABLE:
                msg.body("⚠️ Modul IoT belum tersedia.")
            else:
                try:
                    force_reload_config()
                    msg.body("🔄 **Update Berhasil!**\n\nRules & Matrix Diagnosa baru saja diambil ulang dari Spreadsheet.\n\nSilakan coba diagnosa sekarang dengan data terbaru.")
                except Exception as e:
                    msg.body(f"⚠️ Gagal refresh: {e}")
        
        # AI Explanation (manual trigger) - ASYNC
        elif msg_lower == "analisa" or msg_lower == "analisis":
            if not IOT_MODULES_AVAILABLE:
                msg.body("⚠️ Modul IoT belum tersedia.")
            else:
                msg.body("🧠 *Sedang menyusun penjelasan AI...* Hasilnya akan dikirim sebentar.")

                def run_diagnosa_explanation(target):
                    try:
                        ai_text = generate_diagnosa_explanation()
                        send_async_reply(target, ai_text)
                    except Exception as e:
                        send_async_reply(target, f"⚠️ Gagal analisa AI: {e}")

                t = threading.Thread(target=run_diagnosa_explanation, args=(sender,), daemon=True)
                t.start()
        
        elif msg_lower == "detail":
            if not IOT_MODULES_AVAILABLE:
                msg.body("⚠️ Modul IoT belum tersedia.")
            else:
                try:
                    result = format_diagnosa_detail()
                    msg.body(result + "\n\nKetik 'Menu' untuk kembali.")
                except Exception as e:
                    msg.body(f"⚠️ Error: {e}")
        
        
        # [NEW] Feed Tracker Commands
        elif msg_lower.startswith("log pakan"):
            # Log daily feed to spreadsheet
            if not IOT_MODULES_AVAILABLE:
                msg.body("⚠️ Modul IoT belum tersedia.")
            else:
                try:
                    # Parse: "log pakan 3.5" or "log pakan 3.5 3x grower"
                    parts = msg_text.split()
                    if len(parts) >= 3:
                        pangan_kg = float(parts[2])
                        frekuensi = 3  # default
                        jenis_pakan = "Grower"  # default
                        
                        # Optional: parse frequency and type
                        if len(parts) >= 4:
                            freq_match = re.search(r"(\d+)x", parts[3])
                            if freq_match:
                                frekuensi = int(freq_match.group(1))
                            elif parts[3].lower() in ["starter", "grower"]:
                                jenis_pakan = parts[3].capitalize()
                        if len(parts) >= 5 and parts[4].lower() in ["starter", "grower"]:
                            jenis_pakan = parts[4].capitalize()
                        
                        # [FIX] Handle Photo Upload
                        photo_link = ""
                        if media_url:
                            try:
                                photo_link = upload_photo("feed_log", sender, datetime.now().strftime("%Y-%m-%d"), media_url)
                            except Exception as e:
                                msg.body(f"⚠️ Gagal upload foto: {e}")
                                return reply(resp)

                        result = format_log_pakan_response(
                            pangan_kg=pangan_kg, 
                            jenis_pakan=jenis_pakan,
                            reporter=sender,
                            photo_link=photo_link
                        )
                        msg.body(result + "\n\nKetik 'Menu' untuk kembali.")
                    else:
                        msg.body("Format: 'log pakan [kg]'\nContoh: 'log pakan 3.5'\nAtau: 'log pakan 3.5 3x grower'")
                except ValueError:
                    msg.body("⚠️ Format angka salah.\nContoh: 'log pakan 3.5'")
                except Exception as e:
                    msg.body(f"⚠️ Error: {e}")
        
        elif msg_lower.startswith("rekap pakan"):
            # Show weekly feed summary
            if not IOT_MODULES_AVAILABLE:
                msg.body("⚠️ Modul IoT belum tersedia.")
            else:
                try:
                    # Parse optional week number: "rekap pakan minggu 3"
                    week_num = None
                    parts = msg_lower.split()
                    if len(parts) >= 4 and parts[2] == "minggu":
                        try:
                            week_num = int(parts[3])
                        except:
                            pass
                    
                    result = format_rekap_pakan_response(week_number=week_num)
                    msg.body(result + "\n\nKetik 'Menu' untuk kembali.")
                except Exception as e:
                    msg.body(f"⚠️ Error: {e}")
            
        else:
            msg.body("❓ Pilih angka 1-9 atau ketik:\n• 'aerasi' - cek DO & aerasi\n• 'pakan [berat]' - kalkulasi pakan\n• 'log pakan [kg]' - catat pakan harian\n• 'rekap pakan' - lihat total mingguan\n• 'kalibrasi' - status sensor pH\n• 'troubleshoot ph' - panduan pH")
        return reply(resp)



    # === DAILY REPORTING (HYBRID: GUIDED OR BATCH) ===
    if stage == "daily_menu":
        if msg_lower in ["selesai", "kirim", "ya", "done"]:
            if not state["responses"]:
                msg.body("⚠️ Data masih kosong. Isi minimal 1 item.")
                return reply(resp)
            
            # Move to confirmation
            state["pending_data"] = state["responses"]
            state["stage"] = "confirm"
            summary = "🧐 **TINJAU LAPORAN ANDA:**\n"
            for k, v in state["pending_data"].items():
                if not k.endswith("_photo"):
                    summary += f"• {k.replace('_',' ').title()}: **{v}**\n"
            summary += "\nKetik **'YA'** untuk simpan, atau kirim koreksi."
            msg.body(summary)
            return reply(resp)

        # A. Check for Keyword-Based Batch Input (New Smart Feature)
        keyword_map = {
            r"\bdo\b": "do", r"\bph\b": "ph", r"\btds\b": "tds",
            r"\btemp\b": "temp", r"\bsuhu\b": "temp",
            r"\bmati\b": "dead_fish", r"\bdeath\b": "dead_fish",
            r"\bfreq\b": "feeding_freq",
            r"\bberat\b": "feed_weight", r"\bweight\b": "feed_weight",
            r"\binvp\b": "inv_feed", r"\binvf\b": "inv_feed",
            r"\binvr\b": "inv_rest", r"\binvs\b": "inv_rest",
            r"\bpump\b": "pump_relay", r"\bpompa\b": "pump_relay",
            r"\baerator\b": "aerator_relay", r"\bkincir\b": "aerator_relay", r"\bair\b": "aerator_relay"
        }
        
        found_keywords = False
        for pattern, key in keyword_map.items():
            # Look for "key value" pattern
            match = re.search(pattern + r"\s*([-+]?\d*\.\d+|\d+)", msg_lower)
            if match:
                state["responses"][key] = match.group(1)
                found_keywords = True
        
        if found_keywords:
            # [BARU] Cek apakah ada foto yang menyertai Smart Input
            if media_url:
                # Rule: Hanya boleh 1 kunci jika pakai foto (sesuai request "satu persatu")
                detected_keys = [k for k in state["responses"] if k not in state.get("pending_data", {})] 
                # Note: detected_keys di atas mungkin agak bias kalau state["responses"] sudah ada isinya dari step sebelumnya.
                # Lebih aman kita cek 'match' dari loop di atas tadi.
                
                # Kita hitung ulang match yg baru saja terjadi
                current_matches = []
                for pattern, key in keyword_map.items():
                    if re.search(pattern + r"\s*([-+]?\d*\.\d+|\d+)", msg_lower):
                        current_matches.append(key)
                
                # Deduplicate
                current_matches = list(set(current_matches))

                if len(current_matches) == 1:
                    target_key = current_matches[0]
                    # Upload Photo
                    try:
                        msg.body(f"📸 Mengupload foto untuk {target_key}...")
                        photo_link = upload_photo(target_key, sender, datetime.now().strftime("%Y-%m-%d"), media_url)
                        state["responses"][f"{target_key}_photo"] = photo_link
                        msg.body(f"🧠 **Smart Input + Foto Diterima!**\n" + get_daily_menu_text(state["responses"]))
                        return reply(resp)
                    except Exception as e:
                         msg.body(f"⚠️ Gagal upload foto: {e}")
                elif len(current_matches) > 1:
                     msg.body(f"⚠️ **Info:** Foto hanya bisa diproses jika Anda kirim **satu per satu**.\n(Contoh: 'do 5' + Foto)\nData angka tetap tersimpan.")

            msg.body(f"🧠 **Smart Input Diterima!**\n" + get_daily_menu_text(state["responses"]))
            return reply(resp)

        # B. Fallback to Positional Batch Input (Legacy Shortcut)
        all_numbers = re.findall(r"[-+]?\d*\.\d+|\d+", msg_text.replace(",", "."))
        if len(all_numbers) > 1:
            # Multi-parameter detected
            keys = ["do", "ph", "temp", "tds", "dead_fish", "feeding_freq", "feed_weight", "inv_feed", "inv_rest", "general_video", "pump_relay", "aerator_relay"]
            for i, val in enumerate(all_numbers):
                if i < len(keys): state["responses"][keys[i]] = val
            
            msg.body(f"⚡ **Positional Input Diterima!**\n" + get_daily_menu_text(state["responses"]))
            return reply(resp)

        # C. Check for Sequential Selection (1-10)
        menu_map = {
            "1": "do", "2": "ph", "3": "temp", "4": "tds",
            "5": "dead_fish", "6": "feeding_freq", "7": "feed_weight",
            "8": "inv_feed", "9": "inv_rest", "10": "general_video",
            "11": "pump_relay", "12": "aerator_relay"
        }
        target_key = menu_map.get(msg_lower)
        if target_key:
            state["target_key"] = target_key
            state["stage"] = "daily_input"
            item = next(f for f in daily_form_id if f["key"] == target_key)
            msg.body(f"Masukkan data **{item['name']}**.\n(Boleh ketik Angka saja, ATAU kirim Foto dengan caption Angka)")
        else:
            msg.body("❓ Pilih angka menu (1-9), ketik 'Selesai', atau langsung kirim deretan angka untuk fast-track.")
        return reply(resp)

    # C. GUIDED INPUT (Step-by-step for a single parameter)
    if stage == "daily_input":
        target_key = state["target_key"]
        
        # Parse value & media
        val_number = extract_number(msg_text)
        if media_url:
            photo_link = upload_photo(target_key, sender, datetime.now().strftime("%Y-%m-%d"), media_url)
            state["responses"][f"{target_key}_photo"] = photo_link
        
        if val_number:
            state["responses"][target_key] = val_number
            msg.body(f"✅ Data tersimpan.\n\n" + get_daily_menu_text(state["responses"]))
            state["stage"] = "daily_menu"
        elif media_url and target_key == "general_video":
            state["responses"][target_key] = photo_link
            msg.body("✅ Video tersimpan.\n\n" + get_daily_menu_text(state["responses"]))
            state["stage"] = "daily_menu"
        elif media_url:
            msg.body("📸 Foto diterima. Mohon masukkan juga **angkanya**.")
        else:
            msg.body("❌ Masukkan angka valid.")
        return reply(resp)

    # === CONFIRMATION & LOGGING ===
    if stage == "confirm":
        if msg_lower in ["ya", "y", "yes", "ok", "oke", "siap", "selesai"]:
            # Merge responses and media with proper suffix mapping
            final_data = {**state["pending_data"]}
            if "media" in state:
                for k, v in state["media"].items():
                    final_data[f"{k}_photo"] = v
            
            log_reading(sender, final_data)
            
            # Diagnosis with new engine
            try:
                diag_result = format_diagnosa_response()
                msg.body(f"✅ **DATA TERSIMPAN!**\n\n{diag_result}")
            except:
                msg.body("✅ **DATA TERSIMPAN!**\n\nKetik '9' untuk diagnosa.\nKetik 'Menu' untuk kembali.")
            state["stage"] = "menu"
            state["responses"] = {}
        else:
            # Allow corrections
            num = extract_number(msg_text)
            if num:
                msg.body("💡 Untuk koreksi, silakan masuk ke 'Menu' lalu isi ulang item tersebut.")
            else:
                msg.body("Ketik **'YA'** untuk menyimpan laporan.")
        return reply(resp)

    # [Legacy] Weekly Flow (Restored)
    if stage == "weekly_in_progress":
        # Safety check: pastikan form ada di state
        if "form" not in state:
            state["form"] = weekly_form_id
            state["step"] = 0
            state["responses"] = {}
            state["media"] = {}
        
        # Allow early finish dengan "selesai"
        if msg_lower in ["selesai", "done", "finish"]:
            if state["responses"]:
                # Merge responses and media with suffix
                final_data = {**state["responses"]}
                if "media" in state:
                    for k, v in state["media"].items():
                        final_data[f"{k}_photo"] = v
                log_weekly(sender, final_data)
                msg.body(f"✅ Laporan Mingguan tersimpan ({len(state['responses'])} data).\n\nKetik 'Menu' untuk kembali.")
                state["stage"] = "menu"
            else:
                msg.body("⚠️ Belum ada data yang diisi. Ketik 'Menu' untuk batal.")
            return reply(resp)
            
        form = state["form"]
        step = state["step"]
        if step >= len(form):
             msg.body("✅ Data Mingguan sudah lengkap.")
             return reply(resp)

        current = form[step]
        key = current["key"]

        # Allow skip dengan "skip" atau "lewati"
        if msg_lower in ["skip", "lewati", "next"]:
            state["step"] += 1
            if state["step"] < len(form):
                next_q = form[state["step"]]
                msg.body(f"⏭️ Dilewati.\n\n{next_q['prompt']}")
            else:
                if state["responses"]:
                    final_data = {**state["responses"]}
                    if "media" in state:
                        for k, v in state["media"].items():
                            final_data[f"{k}_photo"] = v
                    log_weekly(sender, final_data)
                    msg.body(f"✅ Terima kasih! Laporan Mingguan selesai ({len(state['responses'])} data tersimpan).\n\nKetik 'Menu' untuk kembali.")
                else:
                    msg.body("⚠️ Tidak ada data. Ketik 'Menu' untuk kembali.")
                state["stage"] = "menu"
            return reply(resp)

        # 1. Cek Angka
        val_number = extract_number(msg_text)
        if val_number and key not in state["responses"]:
            state["responses"][key] = val_number
            
        # 2. Cek Media
        photo_uploaded = False
        if media_url:
            # Upload langsung agar aman
            link = upload_photo(key, sender, datetime.now().strftime("%Y-%m-%d"), media_url)
            if link:
                state["media"][key] = link # Simpan link
                photo_uploaded = True
            else:
                # Upload gagal - beri tahu user
                msg.body(f"❌ Upload foto gagal (error koneksi).\n\n💡 Ketik 'Skip' untuk lewati foto ini, atau coba kirim ulang foto.")
                return reply(resp)

        # 3. Validasi
        photo_required = current.get("require_photo", True)
        has_number = key in state["responses"]
        has_photo = not photo_required or key in state["media"]

        if has_number and has_photo:
            # Lanjut ke next step
            state["step"] += 1
            if state["step"] < len(form):
                next_q = form[state["step"]]
                msg.body(f"✅ Tersimpan.\n\n{next_q['prompt']}\n\n💡 Ketik 'Selesai' untuk mengirim laporan sekarang, atau 'Skip' untuk lewati.")
            else:
                # SELESAI
                final_data = {**state["responses"]}
                if "media" in state:
                    for k, v in state["media"].items():
                        final_data[f"{k}_photo"] = v
                log_weekly(sender, final_data)
                msg.body(f"✅ Terima kasih! Laporan Mingguan selesai ({len(state['responses'])} data tersimpan).\n\nKetik 'Menu' untuk kembali.")
                state["stage"] = "menu"
        else:
            # Belum lengkap
            if not has_number:
                msg.body(f"🔢 Masukkan angka untuk: {current['name']}\n\n💡 Ketik 'Skip' untuk lewati, atau 'Selesai' untuk finish.")
            elif not has_photo:
                msg.body(f"📸 Harap unggah foto bukti untuk: {current['name']}\n\n💡 Ketik 'Skip' untuk lewati foto ini.")
        
        return reply(resp)

        return reply(resp)

    # === HYPER-FOCUSED AI COPILOT ===
    # This block handles interactive Q&A session specifically.
    elif stage == "copilot_session":
        try:
            from ai_helper import chat_with_copilot
            
            history = state.get("session_history", [])
            
            # Langsung balas loading agar tidak timeout
            msg.body("💬 *Sedang memproses balasan AI...* Hasilnya akan dikirim sebentar.")
            
            # Deteksi keyword refresh data
            REFRESH_KEYWORDS = [
                "refresh", "cek ulang", "cek data", "data terbaru", "update data",
                "ambil data", "lihat data", "data sekarang", "kondisi sekarang",
                "gimana sekarang", "bagaimana sekarang", "kondisi terbaru"
            ]
            wants_refresh = any(kw in msg_lower for kw in REFRESH_KEYWORDS)
            
            # Proses Gemini di background thread
            def run_copilot_chat(target, hist, user_msg, st, do_refresh):
                try:
                    actual_msg = user_msg

                    # Jika user minta refresh → fetch data terbaru & inject ke konteks
                    if do_refresh:
                        try:
                            from drive import get_latest_logged_data
                            sensor_data = get_latest_logged_data()

                            # Bangun konteks data terbaru
                            refresh_ctx = "📡 [DATA TERBARU DARI SPREADSHEET]\n"
                            if sensor_data:
                                from datetime import datetime as dt
                                refresh_ctx += f"🕐 Diambil: {dt.now().strftime('%d %b %Y, %H:%M')}\n"
                                refresh_ctx += f"• DO: {sensor_data.get('do', '-')} mg/L\n"
                                refresh_ctx += f"• pH: {sensor_data.get('ph', '-')}\n"
                                refresh_ctx += f"• Suhu: {sensor_data.get('temp', '-')} °C\n"
                                refresh_ctx += f"• TDS: {sensor_data.get('tds', '-')} ppm\n"
                                refresh_ctx += f"• Listrik: {sensor_data.get('ac_status', '-')}\n"
                            else:
                                refresh_ctx += "Tidak ada data terbaru yang bisa diambil.\n"

                            # Inject ke pesan user
                            actual_msg = (
                                f"{user_msg}\n\n"
                                f"{refresh_ctx}\n"
                                f"Tolong analisa dan komentari data terbaru di atas."
                            )
                        except Exception as e:
                            actual_msg = f"{user_msg}\n\n[Gagal ambil data terbaru: {e}]"

                    ai_reply_text, new_history = chat_with_copilot(hist, actual_msg)
                    st["session_history"] = new_history
                    send_async_reply(target, f"{ai_reply_text}\n\n_(Ketik 'Menu' untuk mengakhiri diskusi)_")
                except Exception as e:
                    send_async_reply(target, f"⚠️ Kesalahan sistem saat berdiskusi: {e}\n\nKetik 'Menu' untuk kembali.")
            
            t = threading.Thread(target=run_copilot_chat, args=(sender, history, msg_text, state, wants_refresh), daemon=True)
            t.start()
        except Exception as e:
             msg.body(f"⚠️ Kesalahan sistem: {e}\n\nKetik 'Menu' untuk kembali.")
             
    else:
        # Fallback invalid stage
        state["stage"] = "menu"
        msg.body("❌ Maaf, saya tidak mengerti. Silakan ketik 'Menu'.")

    return reply(resp)

# === App Entry Point ===

if __name__ == '__main__':
    schedule_jobs()        # load all reminders
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
