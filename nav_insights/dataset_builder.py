#!/usr/bin/env python3
"""
dataset_builder.py
Create chat-style supervised fine-tuning records from PaidSearchNav audits.
Input layout (one subdir per audit case):
  <input_root>/<case_id>/findings.json         # AuditFindings JSON
  <input_root>/<case_id>/actions.json          # list[Action] JSON (from rules)
  <input_root>/<case_id>/label_insight.json    # (optional) ground-truth Insight JSON

Outputs:
  - train.jsonl, eval.jsonl with records:
      {
        "messages": [
          {"role":"system","content": "...Insight schema..."},
          {"role":"user","content": "...Findings + Actions..."}
        ],
        "label": "<minified Insight JSON>"
      }

Notes:
  - No external deps; does not import pydantic. We keep the format flexible.
  - If label_insight.json is missing, a *synthetic* minimal Insight is generated
    (valid JSON shape but simple text). Replace with real labels when available.
"""

import argparse
import json
import os
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def minijson(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def build_system_prompt(schema_json: str | None, tone: str) -> str:
    tone_line = (
        "Tone: executive-friendly, concise."
        if tone == "exec"
        else "Tone: hands-on operator, step-by-step."
    )
    if schema_json:
        return (
            "You produce ONLY MINIFIED JSON that validates against the Insight schema. "
            "No code fences, no prose outside JSON. "
            + tone_line
            + "\nInsight schema:\n"
            + schema_json
        )
    # fallback (schema omitted)
    return (
        "You produce ONLY MINIFIED JSON that conforms to the Insight shape: "
        '{"executive_summary": str, "sections": '
        '[{"title": str, "bullets": [str], "metrics_highlights": {}}], '
        '"actions": [Action], "metadata": {}}. ' + tone_line
    )


def build_user_prompt(findings: Dict[str, Any], actions: List[Dict[str, Any]]) -> str:
    return (
        "Here is the audit Facts object (Findings IR):\n"
        + minijson(findings)
        + "\nTriggered Actions (deterministic rules):\n"
        + minijson(actions)
        + "\nWrite the final Insight JSON. It must be valid and reference the facts/actions above."
    )


def synthetic_label(findings: Dict[str, Any], actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Create a minimal, valid Insight label. Replace with real labels as they become available.
    account_name = (findings.get("account", {}) or {}).get("account_name") or findings.get(
        "account", {}
    ).get("account_id", "account")
    date_range = findings.get("date_range", {})
    dr = f"{date_range.get('start_date', '')} to {date_range.get('end_date', '')}"
    summary = (
        f"[AUTO] Summary for {account_name} ({dr}). {len(actions)} actions proposed based on rules."
    )
    sections = [
        {
            "title": "Highlights",
            "bullets": [],
            "metrics_highlights": findings.get("totals", {}) or {},
        }
    ]
    insight = {
        "executive_summary": summary,
        "sections": sections,
        "actions": actions,  # propagate as-is
        "metadata": {"source": "synthetic", "rules_count": len(actions)},
    }
    return insight


def load_case(case_dir: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any] | None]:
    f_find = case_dir / "findings.json"
    f_act = case_dir / "actions.json"
    f_lbl = case_dir / "label_insight.json"
    if not f_find.exists() or not f_act.exists():
        raise FileNotFoundError(f"Missing findings.json or actions.json in {case_dir}")
    findings = read_json(f_find)
    actions = read_json(f_act)
    label = read_json(f_lbl) if f_lbl.exists() else None
    return findings, actions, label


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_root", required=True, help="Directory containing case subfolders")
    ap.add_argument("--schema_path", default="", help="Optional path to Insight JSON schema file")
    ap.add_argument("--tone", default="exec", choices=["exec", "operator"])
    ap.add_argument("--out_train", default="train.jsonl")
    ap.add_argument("--out_eval", default="eval.jsonl")
    ap.add_argument("--eval_split", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)

    schema_json = ""
    if args.schema_path:
        try:
            with open(args.schema_path, "r", encoding="utf-8") as f:
                schema_json = f.read()
        except Exception as e:
            print(f"[WARN] Could not read schema from {args.schema_path}: {e}", file=sys.stderr)

    system_prompt = build_system_prompt(schema_json or None, args.tone)

    input_root = Path(args.input_root)
    case_dirs = sorted([p for p in input_root.iterdir() if p.is_dir()])

    records = []
    for d in case_dirs:
        try:
            findings, actions, label = load_case(d)
        except Exception as e:
            print(f"[SKIP] {d.name}: {e}", file=sys.stderr)
            continue
        user_prompt = build_user_prompt(findings, actions)
        if label is None:
            label_obj = synthetic_label(findings, actions)
        else:
            label_obj = label
        rec = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "label": minijson(label_obj),
        }
        records.append(rec)

    # Split train/eval
    random.shuffle(records)
    n_eval = max(1, int(len(records) * args.eval_split)) if records else 0
    eval_set = records[:n_eval]
    train_set = records[n_eval:]

    with open(args.out_train, "w", encoding="utf-8") as ftr:
        for r in train_set:
            ftr.write(minijson(r) + "\n")
    with open(args.out_eval, "w", encoding="utf-8") as fev:
        for r in eval_set:
            fev.write(minijson(r) + "\n")

    print(f"[OK] Wrote {len(train_set)} train and {len(eval_set)} eval records.")
    print(f"       {os.path.abspath(args.out_train)}")
    print(f"       {os.path.abspath(args.out_eval)}")


if __name__ == "__main__":
    main()
