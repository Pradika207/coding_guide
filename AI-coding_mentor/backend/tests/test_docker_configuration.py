from pathlib import Path
import re

import yaml


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_uses_supported_python_and_exposes_api_port():
    dockerfile = (BACKEND_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"(?m)^FROM python:3\.12-slim\s*$", dockerfile)
    assert re.search(r"(?m)^EXPOSE 8000\s*$", dockerfile)
    assert '"--host", "0.0.0.0", "--port", "8000"' in dockerfile


def test_compose_defines_backend_api_service():
    compose_path = BACKEND_ROOT / "docker-compose.yml"
    assert compose_path.exists()
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    api = compose["services"]["api"]
    assert api["build"]["dockerfile"] == "Dockerfile"
    assert "8000:8000" in api["ports"]
    assert api["env_file"] == [".env"]
    assert api["restart"] == "unless-stopped"


def test_healthcheck_probes_health_endpoint_without_database():
    dockerfile = (BACKEND_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "HEALTHCHECK" in dockerfile
    assert "http://127.0.0.1:8000/health" in dockerfile
    assert "b'healthy'" in dockerfile


def test_image_configuration_does_not_embed_secrets():
    dockerfile = (BACKEND_ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (BACKEND_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    environment_example = (BACKEND_ROOT / ".env.example").read_text(encoding="utf-8")
    for content in (dockerfile, compose):
        assert not re.search(r"(?m)^(?:ARG|ENV)\s+JWT_SECRET\s*=\s*\S+", content)
        assert "JUDGE0_API_KEY=" not in content
    assert re.search(r"(?m)^JWT_SECRET=\s*$", environment_example)
    assert re.search(r"(?m)^JUDGE0_URL=https://ce\.judge0\.com\s*$", environment_example)
    assert re.search(r"(?m)^JUDGE0_API_KEY=\s*$", environment_example)
    assert "MLFLOW_TRACKING_URI=" in environment_example
    assert "SKILL_TRAINING_DATA_PATH=" in environment_example


def test_dockerignore_excludes_local_artifacts_but_keeps_model_path():
    dockerignore = (BACKEND_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    normalized = {line.strip("/") for line in dockerignore if line and not line.startswith("!")}
    assert ".venv" in normalized
    assert "__pycache__" in normalized
    assert ".pytest_cache" in normalized
    assert ".git" in normalized
    assert "mlruns" in normalized
    assert ".dvc/cache" in normalized
    assert "data/raw" in normalized
    assert "data/processed" in normalized
    assert not any("ml/artifacts" in pattern for pattern in dockerignore)


def test_missing_model_is_created_from_reproducible_relative_training_code():
    dockerfile = (BACKEND_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "ml/artifacts/skill_model.joblib" in dockerfile
    assert "train_skill_model(enable_tracking=False)" in dockerfile
    assert "C:\\Users\\" not in dockerfile
    assert "COPY --chown=app:app . ." in dockerfile


def test_existing_image_includes_local_model_serving_without_mlflow_server():
    dockerfile = (BACKEND_ROOT / "Dockerfile").read_text(encoding="utf-8")
    serving_module = BACKEND_ROOT / "ml" / "serving" / "skill_model_service.py"
    route_module = BACKEND_ROOT / "app" / "routes" / "skill_ml.py"

    assert serving_module.is_file()
    assert route_module.is_file()
    assert "mlflow server" not in dockerfile
    assert "COPY --chown=app:app . ." in dockerfile


def test_judge0_environment_name_preserves_legacy_configuration():
    from app.database.config import Settings

    api_url_settings = Settings(_env_file=None, JUDGE0_API_URL="https://judge0.example")
    legacy_url_settings = Settings(_env_file=None, JUDGE0_URL="https://legacy.example")

    assert api_url_settings.judge0_url == "https://judge0.example"
    assert legacy_url_settings.judge0_url == "https://legacy.example"