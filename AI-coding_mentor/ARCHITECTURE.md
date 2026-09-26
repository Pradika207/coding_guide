# AI Coding Mentor — System Architecture

## 1. High-level logical architecture

```text
                    STUDENT
                       |
                       v
                React Frontend
                       |
          +------------+-------------+
          |            |             |
          v            v             v
       Auth       Learning       Practice
          |            |             |
          +------------+-------------+
                       |
                       v
                  FastAPI API
                       |
        +--------------+---------------+
        |              |               |
        v              v               v
    MongoDB          Judge0        ML Services
                                      |
                         +------------+-------------+
                         |            |             |
                         v            v             v
                    Prediction   Monitoring    Retraining
                         |            |             |
                         +------------+-------------+
                                      |
                                  MLOps Layer
                              +-------+-------+
                              |               |
                             DVC           MLflow
```

## 2. Layer responsibilities

### Student experience layer
- React + Vite frontend handles dashboard, learning flow, practice workspace, auth, and routing.
- The frontend uses centralized API calls and JWT-based session handling.
- Protected routes redirect unauthenticated users to the login flow.

### Application API layer
- FastAPI exposes endpoints for auth, assessment, lessons, roadmap, recommendations, gamification, code execution, AI tutor, ML skills, and admin monitoring.
- The API enforces authentication and, where needed, authorization checks.
- The service layer coordinates business logic without duplicating the underlying data or ML systems.

### Data layer
- MongoDB stores user records, assessment sessions, lesson progress, gamification data, prediction logs, and supporting application state.
- The project is designed around a persisted backend state rather than a frontend-only state model.

### Execution and intelligence layer
- Judge0 executes submitted student code for assessment and practice tasks.
- ML serving components generate skill predictions from validated feature data.
- Monitoring services compare prediction and feature distributions against baseline metrics.
- Retraining logic evaluates candidate models and is kept internal to the existing MLOps flow.

### MLOps layer
- DVC versions the dataset and prepared data artifacts.
- MLflow tracks experiments, metrics, and registered model metadata.
- The model serving and monitoring components depend on local metadata and artifacts already present in the repository structure.

## 3. Request flow

### Student sign-in and onboarding
1. User registers.
2. User logs in with email/password.
3. JWT token is stored in session storage.
4. The app fetches the current user profile.
5. The user selects a programming language for personalization.

### Assessment and personalization
1. Assessment begins using the selected language.
2. Questions are evaluated and scored.
3. Results are stored with the user session.
4. Personalization services generate roadmap and skill recommendations.

### Learning and practice
1. Roadmap unlocks recommended lessons.
2. Lessons and quizzes update user progress and gamification.
3. Recommendations are refreshed using the existing student state.
4. Practice questions are loaded with public-only question data.
5. Judge0 executes code and returns normalized status responses.
6. The AI tutor provides progressive hints without exposing hidden test data or executable solutions.

### MLOps and admin
1. Model predictions are generated from validated server-side features.
2. Monitoring evaluates model drift and baseline stability.
3. Retraining remains an internal pipeline, not a public route.
4. Admin routes expose observability without allowing unsafe retraining or model mutation from the browser.

## 4. Data and service boundaries

- Frontend should never own the source of truth for user progress, gamification, or ML metadata.
- Backend services continue to validate auth, ownership, and language selection before exposing data.
- ML prediction is server-controlled and validated rather than accepting untrusted arbitrary feature payloads.
- Admin routes are restricted to authenticated admin users and are read-only with respect to model management.

## 5. Deployment and environment assumptions

This project is designed for local and containerized development. Live backend dependencies such as MongoDB, Judge0, MLflow, and Docker-based runtime services may require local configuration and are not assumed to be running automatically in every environment.

This architecture document reflects the implemented project structure and the validated code paths, not a claim of fully live external-service operation across all environments.
