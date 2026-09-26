# AI Coding Mentor — An Intelligent Learning and Problem Recommendation Platform using Machine Learning and MLOps

## Project title
AI Coding Mentor — An Intelligent Learning and Problem Recommendation Platform using Machine Learning and MLOps

## Project overview
AI Coding Mentor is a full-stack adaptive programming learning platform designed to help students improve their coding skills through assessment, personalized learning, coding practice, and ML-based skill prediction. The project connects student-facing learning workflows with backend services, Judge0 code execution, gamification, and MLOps observability in a single integrated system.

## Problem statement
Many learners struggle to find a programming path that matches their current skill level, learning pace, and language preference. Generic tutorials and disconnected practice systems often fail to translate assessment outcomes into meaningful progression. Students also need a platform that supports learning, code execution, repeated practice, and feedback without exposing hidden evaluation data or internal system details.

## Proposed solution
AI Coding Mentor combines:
- authentication and onboarding,
- coding assessment and result generation,
- personalized roadmap and lesson flow,
- quizzes and progress tracking,
- practice problems and execution,
- progressive AI tutor hints,
- gamification and streak tracking,
- ML skill prediction,
- admin-only MLOps observability.

## Key features
- Register, login, JWT authentication, and user profiles
- Programming language selection persisted per user
- Coding assessment with score and result generation
- Personalized roadmap generation from assessment strengths and weaknesses
- Lesson-driven learning and quiz progression
- XP, streaks, badges, and goals
- Recommendations based on student state and roadmap progress
- Practice workspace with public-only question data
- Judge0-powered code execution and status handling
- Progressive AI tutor hints without exposing hidden tests or internal logic
- ML skill prediction from validated server-side features
- Monitoring, drift detection, DVC tracking, MLflow observability, and admin-only MLOps dashboard

## System architecture
See [ARCHITECTURE.md](ARCHITECTURE.md) for the detailed logical architecture.

## Technology stack
### Frontend
- React
- Vite
- React Router
- lucide-react

### Backend
- FastAPI
- Pydantic
- PyMongo
- JWT auth
- Python

### ML / MLOps
- scikit-learn
- DVC
- MLflow
- local joblib artifacts
- monitoring and retraining services

### Execution and runtime
- Judge0 for code execution
- MongoDB for persistence
- Docker support for local backend runtime

## Application workflow
1. User registers and logs in.
2. User selects a preferred programming language.
3. User completes a coding assessment.
4. Assessment result generates skill and roadmap insights.
5. Student progresses through lessons and quizzes.
6. Gamification updates XP, streaks, and badges.
7. Recommendations refresh from current state and performance.
8. Student completes coding practice and runs code in the workspace.
9. AI tutor provides progressive hints when needed.
10. ML skill prediction continues to update the student view when model data is available.
11. Admin users can inspect MLOps health and monitoring data.

## ML pipeline
The ML pipeline includes:
- synthetic or prepared training data,
- feature engineering,
- model training,
- artifact generation,
- metadata serialization,
- prediction serving,
- monitoring and drift analysis.

## MLOps pipeline
The MLOps flow includes:
- DVC for dataset versioning,
- MLflow for experiment tracking,
- model metadata and artifact management,
- monitoring baseline generation,
- feature and prediction drift comparisons,
- retraining candidate validation,
- safe promotion and rollback logic,
- admin-only observability dashboard.

## Database overview
MongoDB stores application state for:
- users and auth data
- assessments and code submissions
- lesson progress and quizzes
- roadmap data
- gamification records
- recommendation context
- ML prediction logs

## API overview
The backend exposes routes for:
- auth and language selection
- assessment and grading
- roadmap and lessons
- quizzes and lesson progress
- recommendations
- code execution and judge integration
- AI tutor hints
- ML prediction and health
- admin MLOps monitoring

## Frontend structure
The frontend is organized into:
- auth/
- components/
- hooks/
- pages/
- services/
- styles

## Backend structure
The backend includes:
- app/main.py
- app/routes/
- app/services/
- app/models/
- app/schemas/
- app/database/
- ml/
- scripts/
- tests/

## Installation and setup
From the project root:

```powershell
cd AI-coding_mentor
```

### Backend setup
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Frontend setup
```powershell
cd frontend
npm install
```

## Environment variables
Create the backend environment file:

```powershell
cd backend
Copy-Item .env.example .env
```

Important variables include:
- MONGODB_URL
- DATABASE_NAME
- JWT_SECRET
- JWT_ALGORITHM
- JWT_EXPIRATION_MINUTES
- JUDGE0_API_URL
- JUDGE0_API_KEY
- MLFLOW_TRACKING_URI
- SKILL_TRAINING_DATA_PATH
- monitoring and retraining configuration

> MongoDB/Judge0/MLflow/Docker live integration may require local configuration and is not assumed to be active in every environment.

## Running the backend
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Running the frontend
```powershell
cd frontend
npm run dev
```

## Running tests
### Backend
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

### Frontend
```powershell
cd frontend
npm test -- --run
```

### Production build
```powershell
cd frontend
npm run build
```

## Training the ML model
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m scripts.train_skill_model
```

## DVC workflow
```powershell
cd backend
python -m ml.data.generate_synthetic_dataset
python -m ml.data.prepare_skill_dataset
dvc repro
dvc status
dvc dag
```

## MLflow workflow
```powershell
cd backend
mlflow server --host 127.0.0.1 --port 5000
python -m scripts.train_skill_model
```

## Docker information
```powershell
cd backend
docker build -t ai-coding-mentor-backend .
docker run --env-file .env -p 8000:8000 ai-coding-mentor-backend
```

## Security considerations
- JWT-based auth is used for protected routes.
- Admin routes are protected by backend RBAC checks.
- Student ownership and route access are validated server-side.
- Hidden test data and evaluator internals are not exposed to the frontend.
- Secrets remain environment-based and are not committed to source control.
- Token storage is kept in session storage rather than localStorage.

## Limitations
- This project is designed as an academic final-year platform and demonstration app, not a production SaaS deployment.
- Live MongoDB, Judge0, MLflow, and Docker service availability depends on local configuration.
- Model artifacts and monitoring data are local and deterministic rather than industrial-scale telemetry.
- DVC/MLflow/Docker are configuration and observability tools, not replacements for real deployment infrastructure.

## Future enhancements
- More advanced student analytics and recommendation tuning
- Stronger production hardening and monitoring
- Broader deployment automation
- Further admin controls and operational dashboards

## Project status
The project is in a final-year demonstration-ready state with:
- validated backend and frontend regression suites,
- successful frontend production build,
- working student experience and admin MLOps observability,
- configuration-dependent live external services for MongoDB, Judge0, and MLflow.

This project should be presented honestly as a working local platform prototype with ML/MLOps integration while clearly noting that live external service integration may require local setup.
