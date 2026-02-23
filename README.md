<p align="center">
  <samp><b>🔬 Neykuri v1</b></samp><br>
  <samp>Edge AI Siddha Diagnostic System</samp>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Jetson_Nano_4GB-76B900?style=flat-square&logo=nvidia" />
  <img src="https://img.shields.io/badge/TensorFlow-2.16.2-FF6F00?style=flat-square&logo=tensorflow" />
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat-square&logo=fastapi" />
  <img src="https://img.shields.io/badge/Streamlit-1.30+-FF4B4B?style=flat-square&logo=streamlit" />
  <img src="https://img.shields.io/badge/Supabase-Cloud_Sync-3ECF8E?style=flat-square&logo=supabase" />
  <img src="https://img.shields.io/badge/Python-3.10-3776AB?style=flat-square&logo=python" />
</p>

---

## What is Neykuri?

Neykuri is an **Edge AI medical diagnostic system** rooted in **Siddha medicine** (traditional Tamil medicine). It analyses **biological fluid sample images** (urine) to classify the patient's **Dosha** state — a key diagnostic indicator in Siddha practice.

The system processes up to **9 sequential images per patient** over a **72-hour monitoring window**, tracking disease progression in real time — entirely on-device with no cloud dependency.

**New in v1.1:** Offline-first **Supabase cloud sync** — records are diagnosed locally on the Jetson, then batch-uploaded to Supabase for cloud backup and remote access.

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
│  Streamlit Frontend   │◄─────────────────►│   FastAPI Backend v1.1   │
│  (app.py :8501)       │  /analyze         │   (api.py :8000)         │
│                       │  /history/{pid}   │                          │
│  • File upload / cam  │  /sync-status     │  • DenseNet121 inference  │
│  • Result display     │  /health          │  • SQLite persistence     │
│  • 72-hour timeline   │                   │  • Image file storage     │
│  • Dosha legend       │                   │  • is_synced tracking     │
└───────────────────────┘                   └──────────────────────────┘
                                                       │
                                            ┌──────────┼──────────┐
                                            │          │          │
                                    SQLite DB    storage/    sync_to_cloud.py
                                    (+ is_synced)  .jpg files     │
                                                                  ▼
                                                        ┌──────────────────┐
                                                        │  Supabase Cloud  │
                                                        │  • Storage bucket│
                                                        │  • cloud_records │
                                                        └──────────────────┘
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
│   ├── api.py                    # FastAPI backend v1.1 — endpoints + model loading
│   ├── db_viewer.py              # Streamlit DB viewer (port 8502)
│   ├── sync_to_cloud.py          # Supabase cloud sync worker (v1.3)
│   ├── supabase_setup.sql        # SQL to create cloud_records table in Supabase
│   ├── .env                      # Supabase credentials (gitignored)
│   ├── .env.example              # Template for .env — safe to commit
│   ├── neykuri_model_v1.keras    # DenseNet121 trained model (gitignored)
│   ├── neykuri_database.db       # SQLite database (gitignored, auto-created)
│   └── requirements_api.txt      # Backend Python dependencies
├── frontend/
│   ├── app.py                    # Streamlit diagnostic UI (port 8501)
│   └── requirements_ui.txt       # Frontend Python dependencies (no TF!)
├── storage/
│   └── saved_samples/            # Runtime .jpg images (gitignored)
│       └── .gitkeep
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
- (Optional) Supabase project for cloud sync

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
[DB] Schema v1.1 ready (patient_records + is_synced column).
[Startup] TensorFlow version : 2.16.2
[Startup] Model loaded. Server is ready.
[Startup] Input  : (None, 224, 224, 3)
[Startup] Output : (None, 5)
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

## Supabase Cloud Sync

Neykuri uses an **offline-first** design: diagnoses run locally on the Jetson, then records are batch-synced to Supabase when connectivity is available.

### Setup

1. Create a [Supabase](https://supabase.com) project
2. Run `backend/supabase_setup.sql` in the Supabase SQL Editor to create the `cloud_records` table
3. Create a **private** storage bucket named `neykuri_samples` (Dashboard → Storage → New Bucket)
4. Copy `backend/.env.example` to `backend/.env` and fill in your credentials:
   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_KEY=eyJhbGciOiJI...
   ```
5. Install sync dependencies:
   ```bash
   pip install supabase python-dotenv
   ```

### Usage

```bash
cd backend

# Sync all pending records to Supabase
python sync_to_cloud.py

# Show sync counts without uploading
python sync_to_cloud.py --status

# Preview what would sync (no uploads)
python sync_to_cloud.py --dry-run
```

### How it works

1. New records are inserted with `is_synced = 0` (pending)
2. `sync_to_cloud.py` queries all unsynced records
3. For each: uploads `.jpg` to Supabase Storage → generates signed URL → inserts metadata into `cloud_records` → marks `is_synced = 1` locally
4. Duplicate-safe: checks `patient_id + timestamp` before inserting, uses `upsert=true` for image uploads

> [!NOTE]
> The sync worker uses the **Supabase service role key** (not anon key) to bypass Row Level Security. Never expose this key in the frontend.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/analyze` | Submit image + patient ID → returns Dosha + confidence + `is_synced` |
| `GET` | `/history/{patient_id}` | Last 9 records for a patient (72-hour window), includes `is_synced` per record |
| `GET` | `/sync-status` | Count of total / synced / pending records |
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
  "image_saved": "D:\\neykuri_v1\\storage\\saved_samples\\PT-00142_20260221_120000_000000.jpg",
  "is_synced": false
}
```

### Example: `/sync-status`

```bash
curl http://localhost:8000/sync-status
```

Response:
```json
{
  "total_records": 6,
  "synced_to_cloud": 6,
  "pending_sync": 0
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

### Local SQLite — `patient_records`

| Column | Type | Description |
|--------|------|-------------|
| `record_id` | `INTEGER PK AUTOINCREMENT` | Unique record ID |
| `patient_id` | `TEXT NOT NULL` | Patient identifier (e.g. PT-00142) |
| `timestamp` | `TEXT NOT NULL` | UTC timestamp (`YYYYMMDD_HHMMSS_ffffff`) |
| `image_path` | `TEXT NOT NULL` | Absolute path to saved .jpg file |
| `prediction` | `TEXT NOT NULL` | Dosha class name |
| `confidence` | `REAL NOT NULL` | Raw confidence (0.0–1.0) |
| `is_synced` | `INTEGER NOT NULL DEFAULT 0` | 0 = pending, 1 = synced to Supabase |

**Indexes:**
- `idx_patient_timestamp` on `(patient_id, record_id DESC)` — optimises `/history`
- `idx_unsynced` on `(is_synced) WHERE is_synced = 0` — partial index for sync queries

> [!NOTE]
> Confidence is stored as raw 0–1 in the database. API endpoints multiply by 100 before returning to clients.

### Supabase Cloud — `cloud_records`

| Column | Type | Description |
|--------|------|-------------|
| `id` | `BIGSERIAL PK` | Auto-generated |
| `patient_id` | `TEXT NOT NULL` | Patient identifier |
| `timestamp` | `TEXT NOT NULL` | Original UTC timestamp |
| `prediction` | `TEXT NOT NULL` | Dosha class (constrained to 5 valid values) |
| `confidence` | `FLOAT8 NOT NULL` | Raw confidence (0.0–1.0) |
| `storage_path` | `TEXT NOT NULL` | Path in Supabase Storage bucket |
| `image_url` | `TEXT` | Signed URL for image access |
| `synced_at` | `TEXT NOT NULL` | IST timestamp of when sync occurred |

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

### Cloud Sync (optional, install manually)

| Package | Purpose |
|---------|---------|
| `supabase` | Supabase Python client |
| `python-dotenv` | Load `.env` credentials |

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
