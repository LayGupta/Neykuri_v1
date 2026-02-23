<p align="center">
  <samp><b>🔬 Neykuri v1</b></samp><br>
  <samp>Edge AI Siddha Diagnostic System</samp>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Jetson_Nano_4GB-76B900?style=flat-square&logo=nvidia" />
  <img src="https://img.shields.io/badge/TensorFlow-2.16.2-FF6F00?style=flat-square&logo=tensorflow" />
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat-square&logo=fastapi" />
  <img src="https://img.shields.io/badge/Streamlit-1.30+-FF4B4B?style=flat-square&logo=streamlit" />
  <img src="https://img.shields.io/badge/Python-3.10-3776AB?style=flat-square&logo=python" />
</p>

---

## What is Neykuri?

Neykuri is an **Edge AI medical diagnostic system** rooted in **Siddha medicine** (traditional Tamil medicine). It analyses **biological fluid sample images** (urine) to classify the patient's **Dosha** state — a key diagnostic indicator in Siddha practice.

The system processes up to **9 sequential images per patient** over a **72-hour monitoring window**, tracking disease progression in real time — entirely on-device with no cloud dependency.

### Dosha Classes (5-class output)

| Class | Name | Icon | Interpretation |
|-------|------|------|----------------|
| 0 | **Kabam** | 💧 | Kapha-dominant — heaviness, congestion, fluid retention |
| 1 | **Pithakabam** | 🌀 | Pitta-Kapha — inflammatory tendency with mucosal congestion |
| 2 | **Pithalipitham** | 🔥 | Pitta-Lipid — metabolic heat with fat-metabolism disruption |
| 3 | **Pitham** | ⚡ | Pitta-dominant — acute heat, sharp inflammatory activity |
| 4 | **Pithavatham** | 🌿 | Pitta-Vata — dryness, volatility, erratic inflammation |

---

## Architecture

```
┌───────────────────────┐       HTTP        ┌──────────────────────────┐
│  Streamlit Frontend   │◄─────────────────►│   FastAPI Backend        │
│  (app.py :8501)       │  /analyze         │   (api.py :8000)         │
│                       │  /history/{pid}   │                          │
│  • File upload / cam  │  /health          │  • DenseNet121 inference  │
│  • Result display     │                   │  • SQLite persistence     │
│  • 72-hour timeline   │                   │  • Image file storage     │
│  • Dosha legend       │                   │                          │
└───────────────────────┘                   └──────────────────────────┘
                                                       │
                                            ┌──────────┴──────────┐
                                            │                     │
                                    neykuri_database.db    storage/saved_samples/
                                    (path strings only)    (physical .jpg files)
```

### Hardware Constraint Rules

> [!IMPORTANT]
> These three rules are **non-negotiable** to prevent OOM on the 4 GB Jetson Nano.

| # | Rule | How it's enforced |
|---|------|-------------------|
| 1 | **Model loaded once** at startup | FastAPI `lifespan` context manager → `app_state["model"]` |
| 2 | **Frontend never imports TF/Keras** | `requirements_ui.txt` omits TF entirely; frontend uses `requests` only |
| 3 | **Images stored as .jpg files** | `PIL.Image.save()` writes JPEG; SQLite stores the file path string, not binary blobs |

---

## Project Structure

```
neykuri_v1/
├── backend/
│   ├── api.py                    # FastAPI backend — endpoints + model loading
│   ├── db_viewer.py              # Streamlit DB viewer (port 8502)
│   ├── neykuri_model_v1.keras    # DenseNet121 trained model (gitignored)
│   ├── neykuri_database.db       # SQLite database (gitignored, auto-created)
│   └── requirements_api.txt      # Backend Python dependencies
├── frontend/
│   ├── app.py                    # Streamlit diagnostic UI (port 8501)
│   └── requirements_ui.txt       # Frontend Python dependencies (no TF!)
├── storage/
│   └── saved_samples/            # Runtime .jpg images (gitignored)
├── utils/
│   ├── fix_model.py              # Flatten DTypePolicy in .h5 model config
│   ├── get_size.py               # Print hidden layer sizes from .h5
│   └── xray.py                   # Inspect last 10 layers of .h5 model
├── .gitignore
└── README.md
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- The trained model file `neykuri_model_v1.keras` placed in `backend/`

### 1. Create virtual environment

```bash
python -m venv venv310
source venv310/bin/activate        # Linux / macOS / Jetson
# or
venv310\Scripts\activate           # Windows
```

### 2. Install dependencies

```bash
pip install -r backend/requirements_api.txt
pip install -r frontend/requirements_ui.txt
```

### 3. Start the backend

```bash
cd backend
python api.py
# → Uvicorn starts on http://0.0.0.0:8000
```

On startup you'll see:
```
[Startup] TensorFlow version : 2.16.2
[Startup] Model loaded successfully. Server is ready.
[Startup] Input shape  : (None, 224, 224, 3)
[Startup] Output shape : (None, 5)
```

### 4. Start the frontend (new terminal)

```bash
cd frontend
streamlit run app.py
# → Opens at http://localhost:8501
```

### 5. (Optional) Start the DB viewer

```bash
cd backend
streamlit run db_viewer.py --server.port 8502
# → Opens at http://localhost:8502
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/analyze` | Submit image + patient ID → returns Dosha + confidence |
| `GET` | `/history/{patient_id}` | Last 9 records for a patient (72-hour window) |
| `GET` | `/health` | Health probe — checks model readiness |

### Example: `/analyze`

```bash
curl -X POST http://localhost:8000/analyze \
  -F "patient_id=PT-00142" \
  -F "file=@sample.jpg"
```

Response:
```json
{
  "patient_id": "PT-00142",
  "timestamp": "20260221_120000_000000",
  "diagnosis": "Pitham",
  "confidence": 92.34,
  "image_saved": "D:\\neykuri_v1\\storage\\saved_samples\\PT-00142_20260221_120000_000000.jpg"
}
```

---

## ML Model Details

| Property | Value |
|----------|-------|
| Architecture | DenseNet121 + custom classification head |
| Input | 224 × 224 × 3 RGB (raw 0–255, **not** scaled to 0–1) |
| Output | 5-class softmax |
| Format | `.keras` (Keras 3 native) |
| Preprocessing | `preprocess_input` is **built into the model graph** |
| Training env | Google Colab, TensorFlow 2.16.2 |
| Load method | `tf.keras.models.load_model(path, compile=False)` |

> [!NOTE]
> The `compile=False` flag is intentional — only inference is needed, so optimizer/loss state is not restored. This saves RAM and startup time on the Jetson.

---

## Database Schema

**Table: `patient_records`**

| Column | Type | Description |
|--------|------|-------------|
| `record_id` | `INTEGER PK AUTOINCREMENT` | Unique record ID |
| `patient_id` | `TEXT NOT NULL` | Patient identifier (e.g. PT-00142) |
| `timestamp` | `TEXT NOT NULL` | UTC timestamp (`YYYYMMDD_HHMMSS_ffffff`) |
| `image_path` | `TEXT NOT NULL` | Absolute path to saved .jpg file |
| `prediction` | `TEXT NOT NULL` | Dosha class name |
| `confidence` | `REAL NOT NULL` | Raw confidence (0.0–1.0) |

**Index:** `idx_patient_timestamp` on `(patient_id, record_id DESC)` — optimises the `/history` query.

> [!NOTE]
> Confidence is stored as raw 0–1 in the database. Both API endpoints multiply by 100 before returning to clients.

---

## Dependencies

### Backend (`requirements_api.txt`)

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework for API endpoints |
| `uvicorn[standard]` | ASGI server |
| `python-multipart` | Form/file upload parsing |
| `tensorflow==2.16.2` | ML inference (pinned to match Colab training env) |
| `numpy` | Array operations for image preprocessing |
| `Pillow` | Image I/O and resizing |

### Frontend (`requirements_ui.txt`)

| Package | Purpose |
|---------|---------|
| `streamlit` | Web UI framework |
| `requests` | HTTP calls to backend API |
| `pandas` | DataFrame display and charting |

> [!CAUTION]
> **Never add TensorFlow or Keras to the frontend requirements.** This would load a second copy of the model into RAM and cause OOM on the Jetson Nano.

---

## Utilities (`utils/`)

Helper scripts for model debugging during development (not used at runtime):

| Script | Purpose |
|--------|---------|
| `fix_model.py` | Flatten `DTypePolicy` objects in `.h5` model config for backward compatibility |
| `get_size.py` | Print hidden dense-layer weight shapes from `.h5` |
| `xray.py` | Inspect the last 10 layers of an `.h5` model file |

---

## License

This project is proprietary. All rights reserved.
