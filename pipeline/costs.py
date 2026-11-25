"""Summarise runs.jsonl into the measured table in COSTS.md (between the AUTO markers)."""
from __future__ import annotations

import json
from collections import defaultdict

from .common import ROOT, RUNS


def run() -> None:
    rows = defaultdict(lambda: {"calls": 0, "ok": 0, "lat": 0.0, "gpu": 0.0, "list": 0.0, "retries": 0, "models": set()})
    if not RUNS.exists():
        raise SystemExit("runs.jsonl is empty; run the pipeline first")
    for line in RUNS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        k = (r["stage"], r["provider"])
        row = rows[k]
        row["calls"] += 1
        row["ok"] += r["status"] == "ok"
        row["lat"] += r.get("latency_s") or 0
        row["gpu"] += r.get("gpu_s") or 0
        row["list"] += r.get("cost_usd_list_price") or 0
        row["retries"] += max((r.get("attempts") or 1) - 1, 0)
        row["models"].add(r["model"])
    lines = ["| Stage | Provider | Models | Calls (ok) | Retries | Total latency s | Mean latency s | GPU min | List-price equiv. USD |",
             "|---|---|---|---|---|---|---|---|---|"]
    tot = {"lat": 0, "gpu": 0, "list": 0, "calls": 0}
    for (stage, prov), r in sorted(rows.items()):
        mean = r["lat"] / r["calls"] if r["calls"] else 0
        lines.append(f"| {stage} | {prov} | {', '.join(sorted(r['models']))} | {r['calls']} ({r['ok']}) | {r['retries']} | "
                     f"{r['lat']:.1f} | {mean:.2f} | {r['gpu']/60:.1f} | {r['list']:.4f} |")
        for k in tot:
            tot[k] += r[k]
    lines.append(f"| **total** | | | {tot['calls']} | | {tot['lat']:.1f} | | {tot['gpu']/60:.1f} | {tot['list']:.4f} |")
    table = "\n".join(lines)
    p = ROOT / "COSTS.md"
    txt = p.read_text(encoding="utf-8")
    a, b = "<!-- AUTO:START -->", "<!-- AUTO:END -->"
    txt = txt[:txt.index(a) + len(a)] + "\n" + table + "\n" + txt[txt.index(b):]
    p.write_text(txt, encoding="utf-8")
    print(table)
    print("\nCOSTS.md updated.")
