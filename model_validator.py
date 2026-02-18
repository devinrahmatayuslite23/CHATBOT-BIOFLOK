"""
Model Validator Module
======================
Modul untuk validasi prediksi model dan generate confusion matrix.

Fitur:
1. Log prediksi model ke spreadsheet
2. Collect actual outcomes untuk validasi
3. Generate confusion matrix
4. Hitung accuracy, precision, recall per kategori
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import Counter
import json

# Import from existing modules
# Import from existing modules
try:
    import drive
except ImportError:
    drive = None


# === CONFIGURATION ===

# Prediction categories
PREDICTION_CATEGORIES = {
    "DO": ["NORMAL", "LOW", "CRITICAL"],
    "pH": ["NORMAL", "DRIFT_UP", "DRIFT_DOWN", "SENSOR_STUCK", "HIGH_NOISE"],
    "FEED": ["NORMAL", "INCREASE", "DECREASE"],
    "AERATION": ["ADEQUATE", "INCREASE_NEEDED", "CRITICAL_LOW"],
}

# Headers for Model Predictions tab
PREDICTIONS_HEADERS = [
    "Timestamp",
    "Prediction_Type",     # DO, pH, FEED, AERATION, etc.
    "Input_Data",          # JSON string of input data
    "Prediction",          # Predicted category
    "Confidence",          # Confidence score (0-1)
    "Actual_Outcome",      # Filled later
    "Is_Correct",          # 1 if correct, 0 if wrong, empty if not validated
    "Validated_At",        # When actual was entered
    "Notes"
]

# Initialize worksheet
predictions_tab = drive.get_worksheet("Model_Predictions", PREDICTIONS_HEADERS) if (drive and getattr(drive, 'dashboard', None)) else None


# === PREDICTION LOGGING ===

def log_prediction(
    prediction_type: str,
    input_data: Dict,
    prediction: str,
    confidence: float = 0.0,
    notes: str = ""
) -> Optional[str]:
    """
    Log prediksi model ke spreadsheet.
    
    Args:
        prediction_type: Tipe prediksi (DO, pH, FEED, AERATION)
        input_data: Dict data input yang digunakan untuk prediksi
        prediction: Hasil prediksi
        confidence: Confidence score (0-1)
        notes: Catatan tambahan
    
    Returns:
        Prediction ID (timestamp-based) atau None jika gagal
    """
    if not predictions_tab:
        print("⚠️ Model_Predictions tab not available")
        return None
    
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        row = [
            timestamp,
            prediction_type,
            json.dumps(input_data, ensure_ascii=False),
            prediction,
            round(confidence, 3),
            "",  # Actual_Outcome (empty)
            "",  # Is_Correct (empty)
            "",  # Validated_At (empty)
            notes
        ]
        
        predictions_tab.append_row(row)
        print(f"✅ Prediction logged: {prediction_type}={prediction}")
        return timestamp
        
    except Exception as e:
        print(f"⚠️ Error logging prediction: {e}")
        return None


def update_actual_outcome(
    timestamp: str,
    actual_outcome: str,
    notes: str = ""
) -> bool:
    """
    Update actual outcome untuk prediksi tertentu.
    
    Args:
        timestamp: Timestamp prediksi yang akan diupdate
        actual_outcome: Hasil aktual yang diamati
        notes: Catatan tambahan
    
    Returns:
        True jika berhasil, False jika gagal
    """
    if not predictions_tab:
        return False
    
    try:
        all_data = predictions_tab.get_all_values()
        if len(all_data) < 2:
            return False
        
        # Find row with matching timestamp
        for idx, row in enumerate(all_data[1:], start=2):  # Start from 2 (1-indexed, skip header)
            if len(row) > 0 and row[0] == timestamp:
                # Update columns: Actual_Outcome (6), Is_Correct (7), Validated_At (8), Notes (9)
                prediction = row[3] if len(row) > 3 else ""
                is_correct = "1" if prediction == actual_outcome else "0"
                validated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Update cells
                predictions_tab.update_cell(idx, 6, actual_outcome)
                predictions_tab.update_cell(idx, 7, is_correct)
                predictions_tab.update_cell(idx, 8, validated_at)
                if notes:
                    predictions_tab.update_cell(idx, 9, notes)
                
                print(f"✅ Outcome updated: {timestamp} → {actual_outcome} (Correct: {is_correct})")
                return True
        
        print(f"⚠️ Prediction not found: {timestamp}")
        return False
        
    except Exception as e:
        print(f"⚠️ Error updating outcome: {e}")
        return False


# === CONFUSION MATRIX ===

def get_validated_predictions(prediction_type: Optional[str] = None) -> List[Dict]:
    """
    Ambil semua prediksi yang sudah divalidasi (punya actual outcome).
    
    Args:
        prediction_type: Filter by tipe prediksi (optional)
    
    Returns:
        List of dicts dengan keys: prediction, actual, is_correct
    """
    if not predictions_tab:
        return []
    
    try:
        all_data = predictions_tab.get_all_values()
        if len(all_data) < 2:
            return []
        
        validated = []
        for row in all_data[1:]:
            try:
                pred_type = row[1] if len(row) > 1 else ""
                prediction = row[3] if len(row) > 3 else ""
                actual = row[5] if len(row) > 5 else ""
                is_correct = row[6] if len(row) > 6 else ""
                
                # Skip if not validated
                if not actual or actual == "":
                    continue
                
                # Filter by type if specified
                if prediction_type and pred_type != prediction_type:
                    continue
                
                validated.append({
                    "type": pred_type,
                    "prediction": prediction,
                    "actual": actual,
                    "is_correct": is_correct == "1"
                })
            except (IndexError, ValueError):
                continue
        
        return validated
        
    except Exception as e:
        print(f"⚠️ Error getting validated predictions: {e}")
        return []


def generate_confusion_matrix(prediction_type: str) -> Dict:
    """
    Generate confusion matrix untuk tipe prediksi tertentu.
    
    Args:
        prediction_type: Tipe prediksi (DO, pH, FEED, AERATION)
    
    Returns:
        Dict dengan matrix, categories, dan metrics
    """
    validated = get_validated_predictions(prediction_type)
    
    if len(validated) < 5:
        return {
            "status": "INSUFFICIENT_DATA",
            "data_count": len(validated),
            "message": f"Perlu minimal 5 data tervalidasi (saat ini: {len(validated)})"
        }
    
    # Get categories for this type
    categories = PREDICTION_CATEGORIES.get(prediction_type, [])
    if not categories:
        # Auto-detect categories from data
        categories = list(set(
            [v["prediction"] for v in validated] + 
            [v["actual"] for v in validated]
        ))
    
    # Initialize confusion matrix
    n = len(categories)
    matrix = [[0] * n for _ in range(n)]
    cat_to_idx = {cat: i for i, cat in enumerate(categories)}
    
    # Fill matrix
    for v in validated:
        pred = v["prediction"]
        actual = v["actual"]
        
        if pred in cat_to_idx and actual in cat_to_idx:
            pred_idx = cat_to_idx[pred]
            actual_idx = cat_to_idx[actual]
            matrix[actual_idx][pred_idx] += 1
    
    # Calculate metrics
    metrics = calculate_metrics(matrix, categories)
    
    return {
        "status": "SUCCESS",
        "prediction_type": prediction_type,
        "categories": categories,
        "matrix": matrix,
        "data_count": len(validated),
        "metrics": metrics
    }


def calculate_metrics(matrix: List[List[int]], categories: List[str]) -> Dict:
    """
    Hitung accuracy, precision, recall dari confusion matrix.
    """
    n = len(categories)
    total = sum(sum(row) for row in matrix)
    
    if total == 0:
        return {"error": "No data in matrix"}
    
    # Overall accuracy
    correct = sum(matrix[i][i] for i in range(n))
    accuracy = correct / total
    
    # Per-class metrics
    per_class = {}
    for i, cat in enumerate(categories):
        # True Positives
        tp = matrix[i][i]
        
        # False Positives (predicted as this class but actually other)
        fp = sum(matrix[j][i] for j in range(n) if j != i)
        
        # False Negatives (actually this class but predicted as other)
        fn = sum(matrix[i][j] for j in range(n) if j != i)
        
        # True Negatives
        tn = total - tp - fp - fn
        
        # Precision = TP / (TP + FP)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        
        # Recall = TP / (TP + FN)
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        
        # F1 Score
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        per_class[cat] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1_score": round(f1, 3),
            "support": sum(matrix[i])
        }
    
    return {
        "accuracy": round(accuracy, 3),
        "total_predictions": total,
        "correct_predictions": correct,
        "per_class": per_class
    }


# === MODEL REFINEMENT ===

def identify_improvement_areas(confusion_result: Dict) -> List[Dict]:
    """
    Identifikasi area yang perlu improvement berdasarkan confusion matrix.
    
    Returns:
        List of improvement suggestions sorted by priority
    """
    if confusion_result.get("status") != "SUCCESS":
        return []
    
    metrics = confusion_result.get("metrics", {})
    per_class = metrics.get("per_class", {})
    
    improvements = []
    
    for category, class_metrics in per_class.items():
        precision = class_metrics.get("precision", 1)
        recall = class_metrics.get("recall", 1)
        f1 = class_metrics.get("f1_score", 1)
        
        # Low precision = too many false positives
        if precision < 0.7:
            improvements.append({
                "category": category,
                "issue": "LOW_PRECISION",
                "value": precision,
                "priority": "HIGH" if precision < 0.5 else "MEDIUM",
                "suggestion": f"Terlalu banyak false positive untuk '{category}'. Perketat threshold deteksi."
            })
        
        # Low recall = too many false negatives
        if recall < 0.7:
            improvements.append({
                "category": category,
                "issue": "LOW_RECALL",
                "value": recall,
                "priority": "HIGH" if recall < 0.5 else "MEDIUM",
                "suggestion": f"Sering miss deteksi '{category}'. Perlonggar threshold atau tambah features."
            })
    
    # Sort by priority
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    improvements.sort(key=lambda x: priority_order.get(x["priority"], 2))
    
    return improvements


# === CHATBOT INTEGRATION ===

def format_confusion_matrix_response(prediction_type: str, lang: str = "id") -> str:
    """
    Format confusion matrix untuk response chatbot.
    """
    result = generate_confusion_matrix(prediction_type)
    
    if result["status"] == "INSUFFICIENT_DATA":
        return f"⚠️ {result['message']}\n\nTip: Gunakan 'lapor hasil [tipe] [nilai]' untuk input data aktual."
    
    categories = result["categories"]
    matrix = result["matrix"]
    metrics = result["metrics"]
    
    # Format matrix as table
    message = f"""📊 Confusion Matrix: {prediction_type}

Data: {result['data_count']} prediksi tervalidasi
Accuracy: {metrics['accuracy']*100:.1f}%

Matrix (Aktual↓ vs Prediksi→):
"""
    
    # Header
    header = "        " + " ".join(f"{cat[:6]:>6}" for cat in categories)
    message += header + "\n"
    
    # Rows
    for i, cat in enumerate(categories):
        row_str = f"{cat[:6]:>6}  " + " ".join(f"{val:>6}" for val in matrix[i])
        message += row_str + "\n"
    
    # Per-class metrics
    message += "\nMetrik per kategori:\n"
    for cat, m in metrics["per_class"].items():
        message += f"• {cat}: P={m['precision']:.2f} R={m['recall']:.2f} F1={m['f1_score']:.2f}\n"
    
    # Improvement suggestions
    improvements = identify_improvement_areas(result)
    if improvements:
        message += "\n🔧 Area Improvement:\n"
        for imp in improvements[:3]:  # Top 3
            message += f"• [{imp['priority']}] {imp['suggestion']}\n"
    
    return message


def format_lapor_hasil_response(
    prediction_type: str,
    actual_value: str,
    timestamp: Optional[str] = None,
    lang: str = "id"
) -> str:
    """
    Format response untuk command 'lapor hasil'.
    """
    if timestamp:
        # Update specific prediction
        success = update_actual_outcome(timestamp, actual_value)
        if success:
            return f"✅ Hasil aktual '{actual_value}' untuk {prediction_type} telah disimpan."
        else:
            return f"⚠️ Gagal menyimpan. Pastikan timestamp ({timestamp}) valid."
    else:
        # Update most recent prediction of this type
        validated = get_validated_predictions()
        
        # Find most recent unvalidated prediction of this type
        if predictions_tab:
            try:
                all_data = predictions_tab.get_all_values()
                for row in reversed(all_data[1:]):
                    if len(row) > 5 and row[1].upper() == prediction_type.upper() and row[5] == "":
                        ts = row[0]
                        success = update_actual_outcome(ts, actual_value)
                        if success:
                            return f"✅ Hasil aktual '{actual_value}' untuk prediksi {prediction_type} ({ts}) telah disimpan."
                        break
            except:
                pass
        
        return f"⚠️ Tidak ada prediksi {prediction_type} yang belum divalidasi."


if __name__ == "__main__":
    # Test module
    print("=== Model Validator Test ===")
    
    # Test logging
    log_prediction(
        prediction_type="DO",
        input_data={"do_value": 4.5, "drop_rate": -0.2},
        prediction="LOW",
        confidence=0.85
    )
    
    # Test confusion matrix
    print(format_confusion_matrix_response("DO"))
