from pathlib import Path
import re

import yaml


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "backend-ci.yml"


def _workflow_text() -> str:
    assert WORKFLOW_PATH.is_file()
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _workflow() -> dict:
    return yaml.load(_workflow_text(), Loader=yaml.BaseLoader)


def _steps() -> list[dict]:
    return _workflow()["jobs"]["backend-ci"]["steps"]


def test_workflow_exists_and_triggers_on_push_and_pull_request():
    workflow = _workflow()
    assert "push" in workflow["on"]
    assert "pull_request" in workflow["on"]


def test_workflow_uses_python_312_and_installs_backend_requirements():
    text = _workflow_text()
    assert 'python-version: "3.12"' in text
    install_step = next(step for step in _steps() if step["name"] == "Install backend dependencies")
    assert "python -m pip install --upgrade pip" in install_step["run"]
    assert "python -m pip install -r requirements.txt" in install_step["run"]
    assert _workflow()["jobs"]["backend-ci"]["defaults"]["run"]["working-directory"] == "backend"


def test_workflow_runs_pytest_and_dvc_validation():
    steps = _steps()
    test_step = next(step for step in steps if step["name"] == "Run backend tests")
    dvc_step = next(step for step in steps if step["name"] == "Validate DVC pipeline configuration")
    assert "pytest -q" in test_step["run"]
    assert "dvc status" in dvc_step["run"]
    assert "dvc dag" in dvc_step["run"]


def test_workflow_generates_data_and_trains_without_external_mlflow():
    steps = _steps()
    data_step = next(step for step in steps if step["name"] == "Generate and prepare synthetic development data")
    training_step = next(step for step in steps if step["name"] == "Validate model training without an MLflow server")
    assert "python -m ml.data.generate_synthetic_dataset" in data_step["run"]
    assert "python -m ml.data.prepare_skill_dataset" in data_step["run"]
    assert "data/processed/skill_training_data_processed.csv" in data_step["run"]
    assert "python -m scripts.train_skill_model" in training_step["run"]
    assert training_step["env"]["SKILL_TRAINING_ENABLE_MLFLOW"] == "false"
    assert training_step["env"]["SKILL_TRAINING_DATA_PATH"] == "data/processed/skill_training_data_processed.csv"
    assert "synthetic_development_data" in training_step["run"]


def test_workflow_generates_monitoring_baseline_after_training():
    steps = _steps()
    training_index = next(index for index, step in enumerate(steps) if step["name"] == "Validate model training without an MLflow server")
    baseline_index = next(index for index, step in enumerate(steps) if step["name"] == "Generate monitoring baseline")
    baseline_step = steps[baseline_index]

    assert baseline_index > training_index
    assert "python -m scripts.create_monitoring_baseline" in baseline_step["run"]
    assert "ml/artifacts/monitoring_baseline.json" in baseline_step["run"]


def test_workflow_builds_and_smoke_tests_docker_image():
    steps = _steps()
    build_step = next(step for step in steps if step["name"] == "Build backend Docker image")
    smoke_step = next(step for step in steps if step["name"] == "Start container and smoke-test API")
    assert "docker build -t ai-coding-mentor-backend:ci ./backend" in build_step["run"]
    for endpoint in ("/", "/health", "/languages"):
        assert endpoint in smoke_step["run"]
    assert "401" in smoke_step["run"]
    assert "/ml/skill-profile" in smoke_step["run"]
    assert "/recommendations" in smoke_step["run"]


def test_embedded_workflow_python_snippets_are_valid_syntax():
    snippets = []
    for step in _steps():
        snippets.extend(
            re.findall(r"(?ms)^python - <<'PY'\r?\n(.*?)^PY\s*$", step.get("run", ""))
        )

    assert len(snippets) >= 3
    for index, snippet in enumerate(snippets):
        compile(snippet, f"backend-ci-inline-{index}.py", "exec")


def test_workflow_has_no_obvious_hardcoded_secrets_or_remote_cache():
    text = _workflow_text()
    security_step = next(
        step for step in _steps()
        if step["name"] == "Check tracked configuration for accidental secrets"
    )
    secret_assignment = re.compile(
        r"(?im)^\s*(?:JWT_SECRET|JUDGE0_API_KEY|MONGODB_URL|MLFLOW_TRACKING_URI)\s*[:=]\s*['\"]?\S+"
    )
    assert not secret_assignment.search(text)
    assert '"git", "ls-files"' in security_step["run"]
    assert '"JWT_SECRET"' in security_step["run"]
    assert '"JUDGE0_API_KEY"' in security_step["run"]
    assert '"MONGODB_URL"' in security_step["run"]
    assert '"MLFLOW_TRACKING_URI"' in security_step["run"]
    assert "dvc push" not in text
    assert "actions/cache" not in text
    assert "cache: pip" in text
