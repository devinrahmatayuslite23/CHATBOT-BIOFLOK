from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from ai_helper import check_out_of_range, generate_recommendations, EXPERT_NUMBERS
from forms.daily_form import daily_form_id
from forms.weekly_form import weekly_form_id
from drive import log_reading, log_weekly, upload_photo
import os

from twilio.rest import Client
from dotenv import load_dotenv
load_dotenv()

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
client = Client(TWILIO_SID, TWILIO_AUTH)

user_state = {}
last_activity = {}

# Nomor HP penerima reminder (dari .env, pisahkan dengan koma)
_raw_recipients = os.getenv("REMINDER_RECIPIENTS", "")
REMINDER_RECIPIENTS = [r.strip() for r in _raw_recipients.split(",") if r.strip()]


scheduler = BackgroundScheduler()
scheduler.start()


def send_whatsapp_message(to, body):
    try:
        client.messages.create(
            from_=TWILIO_NUMBER, # [MODIFIKASI] Menghapus prefix 'whatsapp:' ganda
            to="whatsapp:" + to,
            body=body
        )
    except Exception as e:
        print(f"❌ Failed to send WhatsApp message to {to}: {e}")


def format_date_indonesian():
    hari = {
        "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
        "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu"
    }
    bulan = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
        7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }
    now = datetime.now()
    return f"{hari[now.strftime('%A')]}, {now.day:02d} {bulan[now.month]} {now.year}"


def notify_experts(user_phone, data, ai_insight=None):
    tanggal = format_date_indonesian()
    
    if isinstance(data, str):
        summary = f"📅 *{tanggal}*\n\n"
        if "SYSTEM-AUTO" in user_phone:
            summary += "🤖 *OTOMATIS - DETEKSI SISTEM*\n\n"
        elif "UJI COBA" in user_phone:
            summary += "🧪 *PESAN INI HANYA UJI COBA*\n\n"
        summary += f"📡 *Laporan Data* ({user_phone}):\n\n{data}"
    else:
        alerts = check_out_of_range({k.lower(): v for k, v in data.items()})
        all_keys = {
            "do": "DO (mg/L)", "ph": "pH", "temp": "Suhu (°C)", "temperature": "Suhu (°C)",
            "dead_fish": "Ikan Mati", "death": "Ikan Mati",
            "feeding_freq": "Frekuensi Pemberian Pakan",
            "feed_weight": "Berat Pakan (gram)", "feed": "Berat Pakan (gram)",
            "inv_feed": "Jumlah Pakan Tersisa",
            "inv_rest": "Jumlah Pakan Baru",
        }

        summary = f"📅 *{tanggal}*\n\n"
        if "SYSTEM-AUTO" in user_phone:
            summary += "🤖 *OTOMATIS - DETEKSI SISTEM*\n\n"
        elif "UJI COBA" in user_phone:
            summary += "🧪 *PESAN INI HANYA UJI COBA*\n\n"
        summary += f"📡 *Laporan Data* ({user_phone}):\n"

        for key, label in all_keys.items():
            # Avoid duplicate keys if both temp and temperature exist
            val = data.get(key) or data.get(key.title()) or data.get(key.upper())
            if val is None or val == "" or val == "-":
                continue
            
            emoji = "✅"
            note = ""
            key_low = key.lower()
            if key_low in alerts:
                emoji = "❌"
                try:
                    # Basic check for note
                    from thresholds import SOP_THRESHOLDS
                    if key_low in SOP_THRESHOLDS:
                        limit = SOP_THRESHOLDS[key_low]
                        f_val = float(val)
                        if f_val < limit["min"]: note = " (rendah)"
                        elif f_val > limit["max"]: note = " (tinggi)"
                except: pass
                
            summary += f"{emoji} {label}: {val}{note}\n"

        video_link = data.get("general_video_photo") or data.get("video")
        if video_link:
            summary += f"\n🎥 *Video Kondisi:*\n{video_link}"

    # AI INSIGHT LOGIC
    # AI hanya dikirim jika sudah ada hasil dari request manual user (ai_insight parameter)
    # Tidak lagi auto-trigger Gemini saat data sensor masuk → hemat kuota
    if ai_insight:
        rec_msg = f"\n\n🧠 **ANALISA CERDAS GEMINI:**\n{ai_insight}"
    elif not isinstance(data, str):
        rec_msg = "\n\n💡 _Ketik 'analisa' di chatbot untuk mendapatkan saran AI._"
    else:
        rec_msg = ""

    full_message = summary + rec_msg
    
    # [MODIFIKASI] Tampilkan pesan lengkap (termasuk saran AI) di terminal untuk debug/simulasi
    print("\n" + "="*40)
    print("📢 PESAN UNTUK PAKAR (Termasuk AI):")
    print(full_message)
    print("="*40 + "\n")

    for expert in EXPERT_NUMBERS:
        # [MODIFIKASI] Tambah Error Handling agar bot tidak crash jika Twilio gagal
        try:
            send_whatsapp_message(expert, full_message)
            print(f"✅ Alert sent to expert {expert}")
        except Exception as e:
            print(f"❌ Failed to alert expert {expert}: {e}")



def send_daily_reminder():
    for number in REMINDER_RECIPIENTS:
        send_whatsapp_message(number, "🔔 Sekarang waktunya mengisi formulir harian!")
        user_state[number] = {
            "lang": None, "form_type": "daily", "responses": {},
            "media": {}, "stage": "lang_direct_daily"
        }
        send_whatsapp_message(number, "🌐 Silakan pilih bahasa:\n1. 🇮🇩 Bahasa Indonesia\n2. 🇬🇧 English")


def send_weekly_reminder():
    print("📆 Sending weekly reminder...")
    for number in REMINDER_RECIPIENTS:
        send_whatsapp_message(
            number,
            "📆 *Jangan lupa isi formulir mingguan hari ini!*\nSilakan balas pesan ini untuk memulai pengisian."
        )
        user_state[number] = {
            "lang": None, "form_type": "weekly", "responses": {},
            "media": {}, "step": 0, "stage": "lang_direct_weekly"
        }
        send_whatsapp_message(number, "🌐 Silakan pilih bahasa:\n1. 🇮🇩 Bahasa Indonesia\n2. 🇬🇧 English")




def send_sandbox_reactivation_warning(phone):
    send_whatsapp_message(
        phone,
        "⚠️ *Pengingat Aktivasi WhatsApp Bot*\n"
        "Dalam 1 jam koneksi akan kedaluwarsa.\n"
        "Segera kirim pesan *join sense-believed* untuk menjaga koneksi tetap aktif."
    )


def update_last_reactivation(phone):
    last_reactivation_times[phone] = datetime.utcnow()
    job_id = f"sandbox_reactivation_{phone}"
    # Remove any previous job for this user
    try:
        scheduler.remove_job(job_id)
    except:
        pass
    run_time = datetime.utcnow() + timedelta(hours=71)
    scheduler.add_job(
        send_sandbox_reactivation_warning,
        'date',
        run_date=run_time,
        args=[phone],
        id=job_id
    )


def update_last_activity(phone):
    last_activity[phone] = datetime.utcnow()
    schedule_sandbox_reminder(phone)


def schedule_sandbox_reminder(phone):
    job_id = f"sandbox_activity_reminder_{phone}"
    for job in scheduler.get_jobs():
        if job.id == job_id:
            scheduler.remove_job(job_id)
    run_time = datetime.utcnow() + timedelta(seconds=10)
    scheduler.add_job(
        send_sandbox_reactivation_warning,
        'date',
        run_date=run_time,
        args=[phone],
        id=job_id
    )


# [REMOVED] auto_sync_job - Dashboard tab removed, no need for background sync
# Diagnosis now runs: (1) when data arrives via log_reading/log_sensor_data
#                     (2) when user types 'diagnosa' or '9'

def schedule_jobs():
    scheduler.add_job(send_daily_reminder, 'cron', hour=22, minute=30)
    scheduler.add_job(send_daily_reminder, 'cron', hour=7, minute=30)
    scheduler.add_job(send_weekly_reminder, 'cron', day_of_week='sun', hour=5, minute=0)
    # auto_sync_job removed - Dashboard tab deleted
