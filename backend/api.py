"""
Neykuri v1 - Edge AI Medical Diagnostic Backend
Optimized for NVIDIA Jetson Nano (4GB RAM)

Model facts (from neykuri_densenet121.ipynb):
  - Architecture : DenseNet121 + custom head (5-class softmax)
  - Preprocessing: DenseNet's preprocess_input is BUILT INTO the model graph
                   Input must be raw 0-255 RGB, NOT scaled to 0-1
  - Saved format : .keras (Keras 3 native)
  - Requires     : TensorFlow 2.16+ with Keras 3

CRITICAL: Model is loaded ONCE at startup using lifespan context manager.
"""

import os
import sqlite3
import numpy as np
from datetime import datetime
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image
import io

# ─────────────────────────────────────────────────────────────────────────────
# PATHS & CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(BASE_DIR, "neykuri_database.db")
MODEL_PATH  = os.path.join(BASE_DIR, "neykuri_model_v1.keras")
STORAGE_DIR = os.path.abspath(os.path.join(BASE_DIR, "../storage/saved_samples"))
IMG_SIZE    = (224, 224)
CLASS_NAMES = ["Kabam", "Pithakabam", "Pithalipitham", "Pitham", "Pithavatham"]

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL STATE — model lives here, loaded exactly once
# ─────────────────────────────────────────────────────────────────────────────
app_state: dict = {"model": None}


# ─────────────────────────────────────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    os.makedirs(STORAGE_DIR, exist_ok=True)
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patient_records (
                record_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT    NOT NULL,
                timestamp  TEXT    NOT NULL,
                image_path TEXT    NOT NULL,
                prediction TEXT    NOT NULL,
                confidence REAL    NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_patient_timestamp
                ON patient_records (patient_id, record_id DESC)
        """)
        conn.commit()
        print("[DB] Table 'patient_records' is ready.")
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# LIFESPAN — model + db init happen ONCE on startup
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──────────────────────────────────────────────────────────────
    print("[Startup] Initialising database …")
    init_db()

    print(f"[Startup] Loading model from: {MODEL_PATH}")
    if not os.path.exists(MODEL_PATH):
        raise RuntimeError(
            f"Model file not found at {MODEL_PATH}. "
            "Place neykuri_model_v1.keras in the backend/ directory."
        )

    # Keras 3 (TF 2.16+) — import and load
    import tensorflow as tf  # noqa: PLC0415
    print(f"[Startup] TensorFlow version : {tf.__version__}")

    # compile=False — inference only, no need to restore optimizer state
    app_state["model"] = tf.keras.models.load_model(MODEL_PATH, compile=False)
    print("[Startup] Model loaded successfully. Server is ready.")
    print(f"[Startup] Input shape  : {app_state['model'].input_shape}")
    print(f"[Startup] Output shape : {app_state['model'].output_shape}")

    yield  # ── application runs ─────────────────────────────────────────────

    # ── SHUTDOWN ─────────────────────────────────────────────────────────────
    print("[Shutdown] Releasing model from memory …")
    app_state["model"] = None


# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI APPLICATION
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Neykuri Diagnostic API",
    description="Edge AI urine-sample analyser — DenseNet121 backbone",
    version="1.0.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT: POST /analyze
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/analyze", summary="Analyse a urine-sample image")
async def analyze(
    patient_id: str = Form(...),
    file: UploadFile = File(...),
):
    model = app_state.get("model")
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded.")

    # ── 1. Read uploaded file ─────────────────────────────────────────────
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read image: {exc}") from exc

    # ── 2. Save physical .jpg (SQLite stores path string only) ────────────
    timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    safe_pid      = "".join(c if c.isalnum() or c in "-_" else "_" for c in patient_id)
    filename      = f"{safe_pid}_{timestamp_str}.jpg"
    save_path     = os.path.join(STORAGE_DIR, filename)

    os.makedirs(STORAGE_DIR, exist_ok=True)
    pil_image.save(save_path, format="JPEG", quality=90)

    # ── 3. Preprocess ─────────────────────────────────────────────────────
    # IMPORTANT: DenseNet's preprocess_input is built INSIDE the model graph.
    # We only need to:
    #   a) Resize to 224x224
    #   b) Convert to float32
    #   c) Keep pixel values in range 0–255  ← do NOT divide by 255
    img_resized = pil_image.resize(IMG_SIZE, Image.LANCZOS)
    img_array   = np.array(img_resized, dtype=np.float32)   # shape: (224, 224, 3)
    img_batch   = np.expand_dims(img_array, axis=0)          # shape: (1, 224, 224, 3)

    # ── 4. Inference ──────────────────────────────────────────────────────
    predictions = model.predict(img_batch, verbose=0)        # shape: (1, 5)
    class_idx   = int(np.argmax(predictions[0]))
    confidence  = float(predictions[0][class_idx])
    label       = CLASS_NAMES[class_idx]

    # ── 5. Persist metadata to SQLite ────────────────────────────────────
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO patient_records
                (patient_id, timestamp, image_path, prediction, confidence)
            VALUES (?, ?, ?, ?, ?)
            """,
            (patient_id, timestamp_str, save_path, label, confidence),
        )
        conn.commit()
    finally:
        conn.close()

    return JSONResponse(status_code=200, content={
        "patient_id":  patient_id,
        "timestamp":   timestamp_str,
        "diagnosis":   label,
        "confidence":  round(confidence * 100, 2),
        "image_saved": save_path,
    })


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT: GET /history/{patient_id}
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/history/{patient_id}", summary="Last 9 records for a patient")
def get_history(patient_id: str):
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT record_id, patient_id, timestamp, image_path, prediction, confidence
            FROM   patient_records
            WHERE  patient_id = ?
            ORDER  BY record_id DESC
            LIMIT  9
            """,
            (patient_id,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No records found for patient '{patient_id}'.",
        )

    return JSONResponse(status_code=200, content={
        "patient_id":    patient_id,
        "total_records": len(rows),
        "records": [
            {
                "record_id":  row["record_id"],
                "timestamp":  row["timestamp"],
                "image_path": row["image_path"],
                "prediction": row["prediction"],
                "confidence": round(row["confidence"] * 100, 2),
            }
            for row in rows
        ],
    })


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT: GET /health
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health", summary="Health probe")
def health_check():
    model_ready = app_state.get("model") is not None
    return {"status": "ok" if model_ready else "loading", "model_loaded": model_ready}


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)