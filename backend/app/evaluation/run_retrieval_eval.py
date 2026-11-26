import argparse
import json
from pathlib import Path
from app.evaluation.metrics import evaluate_records

ARRAY_FIELDS = ("retrieved_chunk_ids", "relevant_chunk_ids", "cited_chunk_ids")

def load_dataset(path: Path) -> list[dict]:
    records = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON on line {line_no}: {exc}")
        if not isinstance(record, dict):
            raise SystemExit(f"Line {line_no}: each JSONL record must be an object.")
        for field in ARRAY_FIELDS:
            if field not in record:
                raise SystemExit(f"Line {line_no}: missing required field {field}.")
            value = record.get(field)
            if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
                raise SystemExit(f"Line {line_no}: {field} must be an array of non-empty strings.")
        if "answer_supported" in record and not isinstance(record["answer_supported"], bool):
            raise SystemExit(f"Line {line_no}: answer_supported must be true/false.")
        records.append(record)
    return records

def main():
    parser = argparse.ArgumentParser(description="Offline DocuMind retrieval and citation evaluation.")
    parser.add_argument("dataset", help="JSONL dataset")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--output", help="Optional JSON report path")
    parser.add_argument("--strict", action="store_true", help="Fail if dataset has no cases")
    parser.add_argument("--fail-below", type=float, help="Fail if selected metric is below threshold")
    parser.add_argument("--metric", choices=("precision_at_k", "recall_at_k", "mrr", "hit_rate", "ndcg_at_k"), default="mrr")
    args = parser.parse_args()
    if args.k < 1:
        parser.error("--k must be at least 1")
    if args.fail_below is not None and not 0 <= args.fail_below <= 1:
        parser.error("--fail-below must be between 0 and 1")
    records = load_dataset(Path(args.dataset))
    if args.strict and not records:
        raise SystemExit("Strict evaluation requires at least one labeled case.")
    report = evaluate_records(records, args.k)
    report["dataset"] = str(Path(args.dataset))
    report["k"] = args.k
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    if args.fail_below is not None and records and report[args.metric] < args.fail_below:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
