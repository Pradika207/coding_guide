from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.assessment import router as assessment_router
from app.routes.code import router as code_router
from app.routes.health import router as health_router
from app.routes.languages import router as languages_router
from app.routes.gamification import router as gamification_router
from app.routes.lessons import router as lessons_router
from app.routes.questions import router as questions_router
from app.routes.recommendations import router as recommendations_router
from app.routes.skill_ml import router as skill_ml_router
from app.routes.roadmap import router as roadmap_router
from app.routes.tutor import router as tutor_router

app = FastAPI(
    title="AI Coding Mentor API",
    description="Backend foundation for the AI Coding Mentor platform.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(assessment_router)
app.include_router(code_router)
app.include_router(languages_router)
app.include_router(lessons_router)
app.include_router(gamification_router)
app.include_router(questions_router)
app.include_router(recommendations_router)
app.include_router(skill_ml_router)
app.include_router(roadmap_router)
app.include_router(tutor_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "AI Coding Mentor API is running"}
