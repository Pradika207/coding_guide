"""Run one internal candidate retraining/evaluation/promotion decision."""

from __future__ import annotations

import argparse
import json

from ml.retraining.retraining_service import RetrainingService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Request a manual retraining run; the promotion gate still applies.",
    )
    parser.add_argument(
        "--no-mlflow",
        action="store_true",
        help="Run in explicit offline mode without MLflow logging or model registration.",
    )
    arguments = parser.parse_args()

    report = RetrainingService().run(
        force=arguments.force,
        enable_mlflow=not arguments.no_mlflow,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] == "promoted":
        print("Candidate passed the validation gate and was promoted.")
    elif report["status"] == "rejected":
        print("Candidate was rejected; the active model was preserved.")
    elif report["status"] == "not_required":
        print("No retraining trigger was met; no candidate was trained.")
    else:
        print("Retraining did not complete; the active model was preserved.")
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
