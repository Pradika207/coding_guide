# Backend

FastAPI foundation for AI Coding Mentor.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Endpoints:

- `GET /` returns the API running message.
- `GET /health` returns the service health status.

Copy `.env.example` to `.env` and provide local environment values when MongoDB is introduced. No database connection is required for the current health endpoints.

### Sandboxed Code Execution

Assessment and practice code run through the backend's Judge0 client; submitted
source code is never executed inside FastAPI. The sample `.env.example` selects
the official hosted Judge0 CE endpoint. If using that public endpoint, no API
key is required. For a managed RapidAPI Judge0 CE subscription, set
`JUDGE0_URL=https://judge0-ce.p.rapidapi.com` and put the account key in
`JUDGE0_API_KEY` in the ignored local `.env`; the backend sends RapidAPI headers
server-side. Direct authenticated Judge0 CE instances use `X-Auth-Token`.

Restart the backend after changing these variables. An admin can check
`GET /admin/health` for `not_configured`, `configured_unreachable`, or
`configured_reachable`. Health responses never include the endpoint credentials.

## MLOps Development Setup

The skill model training script records parameters, weighted classification metrics, metadata, and the sklearn model in the MLflow experiment `AI-Coding-Mentor-Skill-Prediction`. If the configured tracking server is not running, training falls back to the ignored local `mlruns/` file store.

1. Install dependencies from this directory with `pip install -r requirements.txt`.
2. Optionally set `MLFLOW_TRACKING_URI=http://127.0.0.1:5000` in `.env`.
3. In Terminal 1, start the independent tracking server: `mlflow server --host 127.0.0.1 --port 5000`.
4. In Terminal 2, run `python -m scripts.train_skill_model`.
5. Open `http://127.0.0.1:5000` in a browser.
6. Select the `AI-Coding-Mentor-Skill-Prediction` experiment to view runs, parameters, metrics, and the logged sklearn model artifact.

The current development run uses explicitly labeled `synthetic_development_data` when real topic-level training rows are unavailable. Its metrics are not real-world performance estimates. MLflow tracking is a training-time concern; FastAPI inference continues to use `ml/artifacts/skill_model.joblib`.

## MLOps Data Versioning with DVC

DVC tracks data inputs and preparation output hashes so a training dataset can
be reproduced independently from model experiments. The committed generator
produces only fictional, deterministic `synthetic_development_data`; do not put
real student data in this repository. DVC uses a local cache, with no remote
storage provider configured.

Install the project dependencies from this directory, including DVC:

```powershell
pip install -r requirements.txt
```

Data locations:

- `data/raw/skill_training_data.csv` — original synthetic development snapshot.
- `data/processed/skill_training_data_processed.csv` — normalized training
	data; `data/processed/dataset_metadata.json` records the dataset version,
	source, row count, feature columns, target, and random state.

`dvc.yaml` defines `generate_data` (raw CSV generation) and `prepare_data`
(validation, normalization, processed CSV and metadata). `dvc.lock` records the
resolved input/output hashes. Generate and prepare explicitly or reproduce the
full DAG, then inspect status and stage order:

```powershell
python -m ml.data.generate_synthetic_dataset
python -m ml.data.prepare_skill_dataset
dvc repro
dvc status
dvc dag
```

The training command keeps its synthetic fallback unless a dataset path is
configured. To use the prepared file:

```powershell
$env:SKILL_TRAINING_DATA_PATH = "data/processed/skill_training_data_processed.csv"
python -m scripts.train_skill_model
```

DVC answers **“What data/version was used?”** and MLflow answers **“What
model/experiment was produced from that data?”** DVC owns dataset versioning;
MLflow continues tracking model parameters, metrics, experiment runs, and the
registered model. Dataset-backed MLflow runs include `dataset_version`,
`dataset_path`, `training_source`, `sample_count`, and `feature_count`. The
relationship is `dataset-v1 → processed data → MLflow run → skill-model-v1 →
registered model`.

In the future, a MongoDB-derived export can replace the synthetic raw snapshot
without rewriting the preparation stage or trainer. Keep the expected columns,
map the target to one of `beginner`, `intermediate`, or `advanced`, mark the
actual source accurately, and rerun `dvc repro`. The raw and processed outputs
are generated and excluded from Git; DVC keeps their local content in its
ignored cache.

## MLOps Containerization with Docker

Docker packages the backend and its Python dependencies into a consistent
environment. It reduces differences between development machines, makes builds
repeatable, isolates dependencies, and makes later deployment easier. The image
uses a minimal Python base and runs the API as a non-root user.

From this directory, create a local environment file if you do not already have
one, then set a private JWT secret there before using authenticated features:

```powershell
Copy-Item .env.example .env
```

Build and start the API image:

```powershell
docker build -t ai-coding-mentor-backend .
docker run --env-file .env -p 8000:8000 ai-coding-mentor-backend
```

Or use the backend-only Compose service (it does not require MongoDB):

```powershell
docker compose up --build
```

The API listens on `0.0.0.0:8000` in the container. The image health check
requests `GET /health` and checks for `healthy`; it does not depend on MongoDB.
MongoDB and Judge0 are only needed by the routes that use those services, and
neither is started or contacted during API startup. MLflow is not started in
the container and is not required for the API to start. DVC is not run during
the image build or container startup, and its cache plus generated datasets are
excluded from the build context.

The model is kept at the project-relative path `ml/artifacts/skill_model.joblib`
when it is present in the build context. Since generated model artifacts may
not be present in a clean checkout, the Docker build checks for that file and,
only if missing, trains the existing deterministic synthetic fallback model
with MLflow tracking disabled. It does not use a developer-specific absolute
path or require MongoDB, Judge0, an MLflow server, DVC data, or cloud model
storage. A supplied model artifact is not overwritten.

These tools have separate roles: **DVC** versions datasets, **MLflow** tracks
training experiments and models, and **Docker** packages the runtime
environment. Containerization does not replace DVC/MLflow or alter prediction
logic. `.env` is passed at runtime and excluded from the image; never put real
secrets in the Dockerfile or `.env.example`.

## CI/CD with GitHub Actions

GitHub Actions automatically checks the backend on every push and pull request.
The workflow is [../.github/workflows/backend-ci.yml](../.github/workflows/backend-ci.yml)
and runs on GitHub-hosted Ubuntu with Python 3.12. It installs this directory's
`requirements.txt` and uses pip dependency caching only.

The CI sequence runs backend tests, checks tracked configuration for accidental
credentials, validates DVC with `dvc status` and `dvc dag`, generates and
prepares deterministic **synthetic development data**, imports the MLflow
configuration, trains with MLflow tracking disabled, builds the Docker image,
and smoke-tests the API. It does not require MongoDB, Judge0, an MLflow server,
cloud DVC storage, or registry credentials. Docker smoke tests expect public
routes to return 200 and unauthenticated protected routes to return 401. The
workflow does not publish or deploy the image.

DVC versions data; MLflow tracks experiments and models; Docker packages the
runtime; GitHub Actions automates the checks. No status badge is shown because
no GitHub repository URL is available in this checkout.

## ML Model Serving

Training produces `ml/artifacts/skill_model.joblib` and its
`skill_metadata.json`. MLflow tracks training experiments; it is not needed to
serve predictions. FastAPI uses a thread-safe, lazy singleton to load the local
model and metadata once per application process. It does not access MongoDB or
train a model while loading or predicting. If the model or its metadata is
missing or invalid, readiness and prediction report an unavailable service
instead of silently creating a replacement model.

`POST /ml/predict-skill` requires the existing JWT bearer authentication. The
request uses the existing language and topic values and the current model's
features. `assessment_accuracy` is a percentage from 0 to 100; success and
completion rates are fractions from 0 to 1; counts must be non-negative
integers. `topic_count` is accepted and validated as request context, but the
current model metadata does not list it as a trained feature, so it is not sent
to the classifier. Extra fields such as `student_id` are rejected.

Example request:

```json
{
	"language": "python",
	"topic": "arrays",
	"assessment_accuracy": 74,
	"easy_success_rate": 0.8,
	"medium_success_rate": 0.5,
	"hard_success_rate": 0.25,
	"overall_success_rate": 0.6,
	"failure_rate": 0.4,
	"recent_success_rate": 0.7,
	"lesson_completion_rate": 0.65,
	"attempt_count": 12,
	"topic_count": 3
}
```

The response includes the prediction and versions read from local model
metadata:

```json
{
	"prediction": "intermediate",
	"model_version": "skill-model-v1",
	"feature_version": "features-v1",
	"model_status": "ready"
}
```

`GET /ml/health` is intentionally public and independent of MongoDB. It reports
`healthy` with model/feature versions when ready, or returns HTTP 503 with an
`unavailable` status if model files cannot be loaded. The existing authenticated
`GET /ml/skill-profile` remains available and retains its assessment/report
behavior.

Training/versioning and serving remain separate: DVC versions the dataset,
training produces the artifact and MLflow tracks that experiment, then FastAPI
serves the local artifact through the prediction service.

## ML Monitoring and Drift Detection

The prediction service records a successful inference to the separate
`ml_predictions` MongoDB collection. Each record has a UTC timestamp, prediction
ID, model and feature versions, language, topic, predicted class, and only the
numeric model features used for inference. It deliberately omits student IDs,
passwords, tokens, authentication headers, and source code. MongoDB storage is
best-effort: if it is unavailable, inference still returns its prediction. The
collection uses indexes for prediction ID, timestamp, and version-filtered
time-window queries.

Create the deterministic baseline from the processed DVC dataset and current
local model artifact:

```powershell
python -m scripts.create_monitoring_baseline
```

This writes the versioned `ml/artifacts/monitoring_baseline.json` artifact. It
contains numeric means, population standard deviations, ranges, quantiles, and
histogram proportions; categorical frequency distributions; and the reference
prediction distribution. It records the DVC `dataset_version`, baseline
version, and model/feature versions from existing metadata. The baseline is not
a copy or modification of the DVC dataset. GitHub Actions also generates and
checks this artifact after synthetic model training.

```text
Training dataset (dataset-v1)
	↓
Monitoring baseline (baseline-v1)
	↓
Model predictions (skill-model-v1 / features-v1)
	↓
Last-N monitoring window
	↓
PSI feature and prediction comparisons
	↓
Aggregate monitoring report
```

Numeric features, categorical inputs, and predicted classes are compared with
the baseline using **Population Stability Index (PSI)**. The centralized
thresholds are warning at PSI $\geq 0.10$ and drift at PSI $\geq 0.20$. These
are simple initial thresholds, not calibrated real-world performance claims.
Each report measures at most the last `ML_MONITORING_WINDOW_SIZE` predictions
(default 500), matched to the baseline's model and feature versions. The
minimum sample count is configurable with `ML_MONITORING_MINIMUM_PREDICTIONS`
(default 30). Below that minimum the status is `insufficient_data`: no stable
or drift conclusion is calculated.

Both endpoints require JWT authentication and return aggregate information,
not raw prediction records:

- `GET /ml/monitoring` returns the current measured window, versions, feature
  drift results, prediction-distribution comparison, and status. If MongoDB or
  the matching model/baseline is unavailable, it reports `unavailable`.
- `GET /ml/monitoring/baseline` returns baseline metadata and statistics.

An `stable` status means only that measured PSI scores in that window are below
the configured thresholds; it does not mean the model is accurate, healthy, or
free from other risks. This backend currently has no admin/RBAC role system, so
these routes are authenticated but not admin-only. Add admin authorization
before exposing monitoring information in a production deployment. This is a
monitoring foundation only; it does not trigger retraining or claim production
drift detection accuracy.

## Automated Retraining and Model Promotion

Retraining is an **internal command/service**, not an API route. The monitoring
endpoint never starts training. A run may be triggered by detected feature
drift, a configured increase in processed training rows, or a manual force
request. `insufficient_data` or unavailable monitoring does not automatically
trigger a run. Manual force bypasses the trigger decision, but never bypasses
dataset validation or the promotion gate.

From this directory, run the decision pipeline (which may return
`not_required`):

```powershell
python -m scripts.retrain_skill_model
```

To request a manual candidate run, still subject to all quality gates:

```powershell
python -m scripts.retrain_skill_model --force
```

To explicitly run without MLflow logging/registration, for tests or offline
work, add `--no-mlflow`. Otherwise, the existing MLflow integration tracks the
candidate in `AI-Coding-Mentor-Skill-Prediction` and attempts to register it in
`AI-Coding-Mentor-Skill-Predictor`. Tracking or registry unavailability is
reported honestly and is never represented as successful registration.

```text
Monitoring report / new-data check / manual force
	↓
Retraining trigger
	↓
DVC-prepared dataset → isolated candidate training
	↓
Current and candidate evaluation on the same deterministic holdout
	↓
Promotion gate
	↓
Promote OR reject
	↓
Versioned backup and internal rollback foundation
```

The command reads `data/processed/skill_training_data_processed.csv` (or the
existing `SKILL_TRAINING_DATA_PATH` override) and its dataset metadata. It
rejects missing/invalid columns, insufficient rows, invalid labels, or missing
classes before candidate training. The candidate uses the existing
`RandomForestClassifier`, feature version, random seed, stratified 80/20 split,
and the same validation rows as the current artifact. Candidate files are kept
under `ml/artifacts/candidates/`; they do not overwrite the active model during
training.

Promotion requires available metrics, candidate accuracy and weighted F1 at or
above `MIN_CANDIDATE_ACCURACY` / `MIN_CANDIDATE_F1` (both default to 0.60), and
candidate accuracy no lower than the current model on that same holdout. These
are simple development gates, not production quality guarantees or evidence of
real-world improvement. A rejected candidate leaves the active model and
metadata unchanged.

On acceptance, model, metadata, and matching monitoring baseline are staged
and replaced with rollback-on-error behavior. Existing artifacts are retained
in `ml/artifacts/backups/`; candidate files and retraining reports are kept
apart from the active serving artifact. Serving reloads the new model only
after its versioned artifact set passes validation. The internal
`RollbackService` can restore a matching model/metadata/baseline backup; no
student-facing rollback or retraining endpoint is exposed.

`ml/artifacts/retraining_report.json` records the trigger, dataset/model
versions, current and candidate metrics, decision, and MLflow status. DVC
remains responsible for dataset versioning; MLflow tracks candidate
experiments/registration attempts. This is a development/MLOps foundation only,
not scheduled retraining, production auto-deployment, or a real-world
performance guarantee.

## AI Coding Tutor / Intelligent Hints

The tutor is a deterministic **rule-based intelligent coding tutor**, not an
external LLM-powered service. It acts as a mentor: it points students toward
the concepts and debugging steps needed to solve a problem rather than
returning a complete executable solution.

The provider boundary is `TutorProvider` → `RuleBasedTutorProvider`. Configure
`TUTOR_PROVIDER=rule_based` (the default). Selecting `TUTOR_PROVIDER=llm` does
not create a network client or require an API key in this step; because no LLM
provider is implemented, it safely falls back to the rule-based provider. A
future provider can implement the same interface without changing the route.

Authenticated endpoints:

- `POST /tutor/hint` requests the supplied `hint_level` (defaults to 1).
- `POST /tutor/next-hint` increments the submitted level. Re-send the question
	and current submission context to continue; progression is stateless. Level 4
	is the maximum and a further request returns HTTP 409.

Hint progression is conceptual cue → more specific debugging guidance →
detailed reasoning → structured pseudocode/steps. Even level 4 does not generate
executable solution code. Common compilation/runtime messages (bounds, null or
uninitialized values, syntax, names/scope, type mismatch, division by zero,
recursion termination, and timeouts) map to concise guidance. Other diagnostics
are not echoed raw because they may contain source excerpts or local paths.

Example request to `POST /tutor/hint`:

```json
{
	"question_id": "<id from the question bank>",
	"language": "python",
	"code": "def solve(values):\\n    return values[0]\\n",
	"submission_status": "wrong_answer",
	"compiler_error": null,
	"runtime_error": null,
	"topic": "arrays",
	"difficulty": "easy",
	"hint_level": 1
}
```

Example response:

```json
{
	"hint": "Focus on the logic that transforms the input, then test a small edge case.",
	"explanation": "The program ran, but its result differs from the expected behavior. Recheck the logic and the cases around its boundaries.",
	"concept": "Array traversal",
	"next_step": "Check how the loop visits each element and maintains the result so far.",
	"hint_level": 1,
	"provider": "rule_based",
	"can_request_next_hint": true
}
```

The endpoint verifies the question exists in the shared question bank and that
its language/topic/difficulty match the request. The question bank currently
has no per-user ownership field; access is limited to authenticated users and
known questions. The tutor uses existing `ProgrammingLanguage`, `Topic`, and
`Difficulty` enums. Extra request fields (including hidden tests, expected
outputs, credentials, or model paths) are forbidden.

The response contains `hint`, `explanation`, `concept`, `next_step`,
`hint_level`, `provider`, and `can_request_next_hint`. `TUTOR_MAX_CODE_LENGTH`
defaults to 50000 characters and `TUTOR_MAX_HINT_LEVEL` defaults to 4. Submitted
source is processed in memory for the request only: the tutor does not store it
or log it. Authentication headers and hidden evaluator data are never passed to
providers. Run tutor tests with `python -m pytest -q tests/test_ai_tutor.py`; the
suite requires no MongoDB, Judge0, internet access, or LLM API key (question
lookup and authentication are mocked).

Submission status values are limited to `accepted`, `wrong_answer`,
`compilation_error`, `runtime_error`, `time_limit_exceeded`,
`memory_limit_exceeded`, `pending`, `processing`, and `internal_error`. The
next-hint endpoint is stateless: send the same request with the current
`hint_level`, and the server returns the next level; at level 4 it responds
with HTTP 409 rather than generating more detail.
