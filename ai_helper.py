import os
from google import genai
from thresholds import SOP_THRESHOLDS
from drive import get_recent_trends

# Twilio numbers of experts who should receive alerts
EXPERT_NUMBERS = ["+6281224982768"] # [MODIFIKASI] Nomor Pakar diganti ke user

# Configure Gemini
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def check_out_of_range(data):
    """Check which values fall outside SOP limits."""
    alerts = {}
    for key, val in data.items():
        # Skip None, empty strings, or non-numeric values
        if val is None or val == '' or val == '-':
            continue
        try:
            value = float(val)
            if key in SOP_THRESHOLDS:
                limits = SOP_THRESHOLDS[key]
                if value < limits["min"] or value > limits["max"]:
                    alerts[key] = value
        except (ValueError, TypeError):
            continue
    return alerts

def generate_recommendations(alerts, lang="en"):
    if not alerts:
        return []

    # Fetch sheet context
    trend_text = get_recent_trends()

    # Build the prompt
    if lang == "id":
        prompt = (
            "Kamu adalah AI teknisi akuakultur. Berdasarkan data kualitas air di bawah ini (yang berada di luar ambang batas) "
            "dan tren data terbaru dari tambak, buat hipotesis dan saran perbaikan.\n"
            "PENTING: Jawab SANGAT SINGKAT dan PADAT. Keterbatasan pesan WhatsApp.\n"
            "MAKSIMAL 800 KARAKTER (sekitar 100-120 kata). Fokus hanya pada 3 poin terpenting.\n"
            "Gunakan format poin-poin yang rapi.\n\n"
        )
    else:
        prompt = (
            "You are an aquaculture technician AI. Based on the following out-of-range water quality readings and recent farm trends, "
            "generate hypotheses and troubleshooting actions. Respond in bullet points.\n\n"
        )

    for key, val in alerts.items():
        prompt += f"- {key.upper()}: {val}\n"

    prompt += f"\nRecent data:\n{trend_text}"
    prompt += "\n\nOnly include specific, actionable suggestions based on the trends and values."

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        content = response.text
        return content.strip().split("\n")
    except Exception as e:
        return [f"⚠️ Kesalahan AI: {e}" if lang == "id" else f"⚠️ AI error: {e}"]

def generate_ai_analysis(dashboard_dict, diagnosis_result, lang="id"):
    """
    Generate a more comprehensive AI narrative based on the 
    Matrix Diagnosis result and current sensor data.
    """
    prompt = (
        f"Sebagai ahli akuakultur, berikan analisis singkat untuk kondisi berikut:\n"
        f"Kondisi Saat Ini (Diagnosa Matrix): **{diagnosis_result}**\n\n"
        f"Data Sensor: {str(dashboard_dict)}\n\n"
        f"Tugasmu: Jelaskan MENGAPA kondisi ini terjadi dan apa 2-3 langkah DARURAT yang harus dilakukan."
        f"Gunakan Bahasa Indonesia yang teknis tapi mudah dimengerti petambak."
        f"MAKSIMAL 150 kata."
    )
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return f"⚠️ Gagal memuat analisa cerdas: {e}"

# === INTERACTIVE COPILOT SESSIONS ===

def start_do_copilot(aeration_data: dict) -> tuple:
    """
    Start an interactive Copilot session for DO analysis.
    Returns the initial AI message and the chat history list.
    """
    trend = aeration_data.get("trend", {})
    aeration = aeration_data.get("aeration", {})
    
    # Format system prompt with actual math data
    system_instruction = (
        "Kamu adalah Asisten AI Ahli Akuakultur (Copilot). "
        "Tugasmu: Mendampingi petambak menangani masalah Dissolved Oxygen (DO).\n"
        "Bicaralah dengan ramah, teknis tapi mudah dimengerti, dan gunakan format yang enak dibaca di WhatsApp.\n\n"
        "FAKTA SAAT INI (dihitung oleh sistem matematika):\n"
        f"- DO Kolam: {trend.get('current_do')} mg/L\n"
        f"- Pergerakan (Drop Rate): {trend.get('drop_rate')} mg/L per jam\n"
        f"- Status Darurat: {trend.get('alert_level')}\n"
        f"- Defisit Oksigen: {aeration.get('oxygen_deficit_kg')} kg\n"
        f"- Kebutuhan Aerator Minimum: {aeration.get('recommended_aerator_hp')} HP (PK)\n\n"
        "TUGAS PERTAMAMU:\n"
        "Buat 1 pesan pembuka (maksimal 150 kata). Sampaikan ringkasan fakta di atas dengan bahasa manusi. "
        "Di akhir pesan, tanyakan kepada petambak apakah kincir mereka memadai atau jika ada kendala lain."
    )
    
    try:
        history = [
            {"role": "user", "parts": [{"text": system_instruction}]},
            {"role": "model", "parts": [{"text": "Mengerti. Saya akan bertindak sebagai Copilot Akuakultur dan memberikan analisa berdasarkan data tersebut."}]}
        ]
        
        # We simulate the first user trigger to get the intro message
        first_trigger = "Tolong sampaikan hasil analisa DO saat ini kepada saya."
        
        response, new_history = chat_with_copilot(history, first_trigger)
        return response, new_history
        
    except Exception as e:
        return f"⚠️ Gagal memulai Copilot: {e}", []

def chat_with_copilot(chat_history: list, user_message: str) -> tuple:
    """
    Continue a Copilot session. Keep context via chat_history list.
    """
    try:
        # Add user message to history
        chat_history.append({"role": "user", "parts": [{"text": user_message}]})
        
        # We format the history back to generative AI format
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=chat_history
        )
        ai_reply = response.text.strip()
        
        # Save AI reply to history
        chat_history.append({"role": "model", "parts": [{"text": ai_reply}]})
        
        return ai_reply, chat_history
        
    except Exception as e:
        # Remove the failed user message so it doesn't corrupt history
        if chat_history and chat_history[-1]["role"] == "user":
            chat_history.pop()
        return f"⚠️ Maaf, Copilot sedang gangguan: {e}", chat_history

