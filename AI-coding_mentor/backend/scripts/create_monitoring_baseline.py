"""Generate the deterministic monitoring baseline from prepared DVC data."""

from ml.monitoring.baseline import create_monitoring_baseline


if __name__ == "__main__":
    baseline = create_monitoring_baseline()
    print("Monitoring baseline created.")
    print(f"Baseline version: {baseline['baseline_version']}")
    print(f"Dataset version: {baseline['dataset_version']}")
    print(f"Training source: {baseline['training_source']}")
    print(f"Model version: {baseline['model_version']}")
    print(f"Feature version: {baseline['feature_version']}")
    print(f"Samples: {baseline['sample_count']}")
    print(f"Numeric features: {len(baseline['numeric_features'])}")
    print(f"Categorical features: {len(baseline['categorical_features'])}")