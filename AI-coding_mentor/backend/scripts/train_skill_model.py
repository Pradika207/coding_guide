import json
import os

from ml.models.skill_predictor import train_skill_model


if __name__ == "__main__":
    tracking_setting = os.getenv("SKILL_TRAINING_ENABLE_MLFLOW", "true").strip().lower()
    enable_tracking = tracking_setting not in {"0", "false", "no", "off"}
    result = train_skill_model(enable_tracking=enable_tracking)
    metadata = result["metadata"]
    tracking = result["tracking"]
    print("Training completed.")
    print(f"Model: {metadata['model_name']}")
    print(f"Model version: {metadata['model_version']}")
    print(f"Training source: {metadata['training_source']}")
    print(f"Samples: {metadata['training_sample_count']}")
    print(f"Accuracy: {metadata['metrics']['accuracy']:.4f}")
    print(f"F1 (weighted): {metadata['metrics']['f1']:.4f}")
    print(f"MLflow: {tracking['status']}")
    if tracking.get("status") == "tracked":
        print(f"Experiment: {tracking['experiment_name']}")
        print(f"Run ID: {tracking['run_id']}")
        print(f"Tracking URI: {tracking['tracking_uri']}")
        print(f"Registry: {tracking['registry_status']}")
    else:
        print(f"Tracking detail: {tracking.get('reason', 'unavailable')}")
    print(f"Artifact: {result['model_path']}")
    print(f"Metadata: {result['metadata_path']}")
