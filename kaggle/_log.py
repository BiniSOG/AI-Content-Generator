"""Kaggle-side logger: writes the same runs.jsonl record format as the local pipeline.
The local music stage merges these lines into the repo's runs.jsonl (deduplicated by call_id)."""
import json, time, uuid
from datetime import datetime, timezone
from pathlib import Path

LOG = Path("/kaggle/working/outputs/kaggle/runs_kaggle.jsonl")


def log(**kw):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "call_id": uuid.uuid4().hex,
           "run_id": "kaggle-" + time.strftime("%Y%m%dT%H%M%S"), "provider": "kaggle", "attempts": 1,
           "cost_usd_free_tier": 0.0, "unit": "gpu_s"}
    rec.update(kw)
    rec["units"] = rec.get("gpu_s")
    with open(LOG, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("LOG", json.dumps(rec)[:300])
