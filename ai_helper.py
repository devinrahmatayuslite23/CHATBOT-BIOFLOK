import os
import google.generativeai as genai
from thresholds import SOP_THRESHOLDS
from drive import get_recent_trends


# Twilio numbers of experts who should receive alerts
EXPERT_NUMBERS = ["+6281224982768"] # [MODIFIKASI] Nomor Pakar diganti ke user

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

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
        model = genai.GenerativeModel("gemini-flash-latest")
        response = model.generate_content(prompt)
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
        model = genai.GenerativeModel("gemini-flash-latest")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"⚠️ Gagal memuat analisa cerdas: {e}"

