"""
Neykuri v1 - Edge AI Medical Diagnostic Backend
Optimized for NVIDIA Jetson Nano (4GB RAM)

Model facts (from neykuri_densenet121.ipynb):
  - Architecture : DenseNet121 + custom head (5-class softmax)
  - Preprocessing: DenseNet's preprocess_input is BUILT INTO the model graph
                   Input must be raw 0-255 RGB, NOT scaled to 0-1
  - Saved format : .keras (Keras 3 native)
  - Requires     : TensorFlow 2.16+ with Keras 3

Schema change v1.1:
  - Added is_synced (INTEGER DEFAULT 0) column for Supabase cloud sync
  - 0 = not yet uploaded, 1 = successfully synced to cloud

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
    """
    Create tables and indexes. Safe to run on every startup.
    v1.1: Added is_synced column — tracks whether a record has been
          pushed to Supabase cloud. 0 = pending, 1 = synced.
    """
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
                confidence REAL    NOT NULL,
                is_synced  INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Safely add is_synced to existing databases that were created
        # before v1.1 — ALTER TABLE is ignored if column already exists
        try:
            conn.execute("ALTER TABLE patient_records ADD COLUMN is_synced INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists — safe to ignore

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_patient_timestamp
                ON patient_records (patient_id, record_id DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_unsynced
                ON patient_records (is_synced)
                WHERE is_synced = 0
        """)
        conn.commit()
        print("[DB] Schema v1.1 ready (patient_records + is_synced column).")
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# LIFESPAN — model + db init happen ONCE on startup
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Startup] Initialising database …")
    init_db()

    print(f"[Startup] Loading model from: {MODEL_PATH}")
    if not os.path.exists(MODEL_PATH):
        raise RuntimeError(f"Model file not found at {MODEL_PATH}.")

    import tensorflow as tf
    print(f"[Startup] TensorFlow version : {tf.__version__}")
    app_state["model"] = tf.keras.models.load_model(MODEL_PATH, compile=False)
    print("[Startup] Model loaded. Server is ready.")
    print(f"[Startup] Input  : {app_state['model'].input_shape}")
    print(f"[Startup] Output : {app_state['model'].output_shape}")

    yield

    print("[Shutdown] Releasing model …")
    app_state["model"] = None


# ─────────────────────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Neykuri Diagnostic API",
    description="Edge AI urine-sample analyser — DenseNet121 · Offline-first with Supabase sync",
    version="1.1.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────────────────────────────────
# POST /analyze
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/analyze")
async def analyze(
    patient_id: str = Form(...),
    file: UploadFile = File(...),
):
    model = app_state.get("model")
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file.")

    try:
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read image: {exc}")

    # Save physical jpg
    timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    safe_pid      = "".join(c if c.isalnum() or c in "-_" else "_" for c in patient_id)
    filename      = f"{safe_pid}_{timestamp_str}.jpg"
    save_path     = os.path.join(STORAGE_DIR, filename)
    os.makedirs(STORAGE_DIR, exist_ok=True)
    pil_image.save(save_path, format="JPEG", quality=90)

    # Preprocess — DenseNet preprocessing is inside the model, pass raw 0-255
    img_array = np.array(pil_image.resize(IMG_SIZE, Image.LANCZOS), dtype=np.float32)
    img_batch = np.expand_dims(img_array, axis=0)

    # Inference
    predictions = model.predict(img_batch, verbose=0)
    class_idx   = int(np.argmax(predictions[0]))
    confidence  = float(predictions[0][class_idx])
    label       = CLASS_NAMES[class_idx]

    # Persist — is_synced defaults to 0 (pending cloud sync)
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO patient_records
                (patient_id, timestamp, image_path, prediction, confidence, is_synced)
            VALUES (?, ?, ?, ?, ?, 0)
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
        "is_synced":   False,
    })


# ─────────────────────────────────────────────────────────────────────────────
# GET /history/{patient_id}
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/history/{patient_id}")
def get_history(patient_id: str):
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT record_id, patient_id, timestamp, image_path,
                   prediction, confidence, is_synced
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
        raise HTTPException(status_code=404,
                            detail=f"No records for '{patient_id}'.")

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
                "is_synced":  bool(row["is_synced"]),
            }
            for row in rows
        ],
    })


# ─────────────────────────────────────────────────────────────────────────────
# GET /sync-status
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/sync-status")
def sync_status():
    """Returns count of synced vs pending records — useful for monitoring."""
    conn = get_db()
    try:
        total   = conn.execute("SELECT COUNT(*) FROM patient_records").fetchone()[0]
        synced  = conn.execute("SELECT COUNT(*) FROM patient_records WHERE is_synced=1").fetchone()[0]
        pending = total - synced
    finally:
        conn.close()

    return {
        "total_records":   total,
        "synced_to_cloud": synced,
        "pending_sync":    pending,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    model_ready = app_state.get("model") is not None
    return {"status": "ok" if model_ready else "loading", "model_loaded": model_ready}


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)