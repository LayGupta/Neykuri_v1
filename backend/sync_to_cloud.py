"""
Neykuri v1 — Supabase Cloud Sync Worker (v1.3)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Changes in v1.3:
  - Fixed signed URL key: signedURL (correct for supabase-py 2.28.0)
  - Duplicate prevention: checks if patient_id + timestamp already exists
    in Supabase before inserting — safe to run multiple times
  - If record already in cloud: marks local SQLite as synced and skips insert
  - Storage upload uses upsert=true so image re-upload is also safe

Run this script:
  python sync_to_cloud.py           # sync all pending records
  python sync_to_cloud.py --status  # show counts only
  python sync_to_cloud.py --dry-run # show what would sync, no uploads
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "sync.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("neykuri_sync")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    log.warning("python-dotenv not installed. Reading env vars from OS environment.")

SUPABASE_URL       = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY       = os.getenv("SUPABASE_SERVICE_KEY", "")
BUCKET_NAME        = os.getenv("SUPABASE_BUCKET", "neykuri_samples")
CLOUD_TABLE        = os.getenv("SUPABASE_TABLE", "cloud_records")
DB_PATH            = os.getenv("DB_PATH", os.path.join(BASE_DIR, "neykuri_database.db"))
IST_OFFSET         = timedelta(hours=5, minutes=30)
SIGNED_URL_EXPIRY  = 60 * 60 * 24 * 365 * 10   # 10 years in seconds


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def validate_config() -> bool:
    if not SUPABASE_URL or "supabase.co" not in SUPABASE_URL:
        log.error("SUPABASE_URL is not set correctly in .env")
        return False
    if not SUPABASE_KEY or len(SUPABASE_KEY) < 20:
        log.error("SUPABASE_SERVICE_KEY is not set correctly in .env")
        return False
    if not os.path.exists(DB_PATH):
        log.error(f"SQLite database not found: {DB_PATH}")
        return False
    return True


def to_ist(timestamp_str: str) -> str:
    try:
        dt_utc = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S_%f")
        dt_ist = dt_utc + IST_OFFSET
        return dt_ist.strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return timestamp_str


def get_signed_url(supabase, cloud_path: str) -> str:
    """
    Generate a signed URL. Works with supabase-py 2.28.0.
    Response dict has key 'signedURL' (capital URL).
    """
    try:
        response = supabase.storage.from_(BUCKET_NAME).create_signed_url(
            path=cloud_path,
            expires_in=SIGNED_URL_EXPIRY,
        )
        # supabase-py 2.28.0 returns both 'signedURL' and 'signedUrl'
        # Use 'signedURL' as primary — it is always present
        url = (
            response.get("signedURL")
            or response.get("signedUrl")
            or ""
        )
        if url:
            log.info(f"  ✅ Signed URL generated.")
        else:
            log.warning(f"  ⚠️  No URL in response: {response}")
        return url
    except Exception as exc:
        log.warning(f"  ⚠️  Signed URL generation failed: {exc}")
        return ""


def already_in_cloud(supabase, patient_id: str, timestamp: str) -> bool:
    """
    Check if this exact record already exists in Supabase.
    Uses patient_id + timestamp as a unique combination.
    Prevents duplicate rows when sync is run multiple times.
    """
    try:
        result = supabase.table(CLOUD_TABLE).select("id").eq(
            "patient_id", patient_id
        ).eq(
            "timestamp", timestamp
        ).execute()
        return len(result.data) > 0
    except Exception as exc:
        log.warning(f"  Duplicate check failed: {exc} — will attempt insert anyway.")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN SYNC
# ─────────────────────────────────────────────────────────────────────────────
def sync_records() -> dict:
    summary = {"total": 0, "success": 0, "failed": 0,
               "skipped": 0, "already_synced": 0}

    if not validate_config():
        return summary

    try:
        from supabase import create_client, Client
    except ImportError:
        log.error("supabase not installed. Run: pip install supabase")
        return summary

    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        log.info(f"Connected to Supabase: {SUPABASE_URL}")
    except Exception as exc:
        log.error(f"Cannot connect to Supabase: {exc}")
        return summary

    # Fetch all unsynced local records
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT record_id, patient_id, timestamp, image_path, prediction, confidence
            FROM   patient_records
            WHERE  is_synced = 0
            ORDER  BY record_id ASC
            """
        ).fetchall()
    except sqlite3.OperationalError as exc:
        log.error(f"SQLite error: {exc}. Restart api.py to apply schema v1.1.")
        conn.close()
        return summary

    summary["total"] = len(rows)

    if not rows:
        log.info("✅ All records are synced. Nothing to do.")
        conn.close()
        return summary

    log.info(f"Found {len(rows)} unsynced record(s). Starting upload…")

    for row in rows:
        record_id  = row["record_id"]
        patient_id = row["patient_id"]
        timestamp  = row["timestamp"]
        image_path = row["image_path"]
        prediction = row["prediction"]
        confidence = row["confidence"]

        log.info(f"[Record {record_id}] Processing {patient_id} — {prediction} — {to_ist(timestamp)}")

        # ── DUPLICATE CHECK — skip if already in Supabase ─────────────────
        if already_in_cloud(supabase, patient_id, timestamp):
            log.info(f"[Record {record_id}] ⏭  Already exists in cloud — marking synced locally.")
            conn.execute(
                "UPDATE patient_records SET is_synced = 1 WHERE record_id = ?",
                (record_id,),
            )
            conn.commit()
            summary["already_synced"] += 1
            summary["success"] += 1
            continue

        # ── STEP A: Upload image to Supabase Storage ──────────────────────
        if not os.path.exists(image_path):
            log.warning(f"[Record {record_id}] ❌ Image file missing: {image_path} — skipping.")
            summary["skipped"] += 1
            continue

        file_name          = os.path.basename(image_path)
        cloud_storage_path = f"{patient_id}/{file_name}"

        try:
            with open(image_path, "rb") as f:
                supabase.storage.from_(BUCKET_NAME).upload(
                    file=f,
                    path=cloud_storage_path,
                    file_options={"content-type": "image/jpeg", "upsert": "true"},
                )
            log.info(f"[Record {record_id}] ✅ Image uploaded → {cloud_storage_path}")
        except Exception as exc:
            log.error(f"[Record {record_id}] ❌ Storage upload failed: {exc}")
            summary["failed"] += 1
            continue

        # ── STEP B: Generate signed URL ───────────────────────────────────
        image_url = get_signed_url(supabase, cloud_storage_path)

        # ── STEP C: Insert metadata into Supabase DB ──────────────────────
        now_ist = datetime.utcnow() + IST_OFFSET
        payload = {
            "patient_id":   patient_id,
            "timestamp":    timestamp,
            "prediction":   prediction,
            "confidence":   round(confidence, 6),
            "storage_path": cloud_storage_path,
            "image_url":    image_url,
            "synced_at":    now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        }

        try:
            supabase.table(CLOUD_TABLE).insert(payload).execute()
            log.info(f"[Record {record_id}] ✅ Metadata inserted into '{CLOUD_TABLE}'")
        except Exception as exc:
            log.error(f"[Record {record_id}] ❌ DB insert failed: {exc}")
            summary["failed"] += 1
            continue

        # ── STEP D: Mark as synced in local SQLite ────────────────────────
        try:
            conn.execute(
                "UPDATE patient_records SET is_synced = 1 WHERE record_id = ?",
                (record_id,),
            )
            conn.commit()
            log.info(f"[Record {record_id}] ✅ Marked synced locally.")
            summary["success"] += 1
        except Exception as exc:
            log.error(f"[Record {record_id}] ❌ Local SQLite update failed: {exc}")
            summary["failed"] += 1

    conn.close()
    log.info(
        f"━━━ Sync complete — "
        f"{summary['success']} synced  "
        f"({summary['already_synced']} already existed)  "
        f"| {summary['failed']} failed  "
        f"| {summary['skipped']} skipped ━━━"
    )
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# STATUS CHECK
# ─────────────────────────────────────────────────────────────────────────────
def check_status():
    if not os.path.exists(DB_PATH):
        log.error(f"Database not found: {DB_PATH}")
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        total   = conn.execute("SELECT COUNT(*) FROM patient_records").fetchone()[0]
        synced  = conn.execute("SELECT COUNT(*) FROM patient_records WHERE is_synced=1").fetchone()[0]
        pending = total - synced
    finally:
        conn.close()
    log.info("─── Sync Status ───────────────────────")
    log.info(f"  Total records : {total}")
    log.info(f"  Synced        : {synced}")
    log.info(f"  Pending       : {pending}")
    log.info("───────────────────────────────────────")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Neykuri Supabase Sync Worker v1.3")
    parser.add_argument("--status",  action="store_true",
                        help="Show sync status without uploading")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would sync without actually uploading")
    args = parser.parse_args()

    if args.status:
        check_status()

    elif args.dry_run:
        if not os.path.exists(DB_PATH):
            log.error(f"Database not found: {DB_PATH}")
            sys.exit(1)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT record_id, patient_id, prediction, timestamp "
            "FROM patient_records WHERE is_synced=0"
        ).fetchall()
        conn.close()
        log.info(f"DRY RUN — {len(rows)} record(s) pending:")
        for row in rows:
            log.info(
                f"  #{row['record_id']} | {row['patient_id']} | "
                f"{row['prediction']} | {to_ist(row['timestamp'])}"
            )

    else:
        sync_records()