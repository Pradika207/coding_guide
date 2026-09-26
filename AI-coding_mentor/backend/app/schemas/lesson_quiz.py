from pydantic import BaseModel, Field


class QuizCompletionRequest(BaseModel):
    quiz_id: str = Field(min_length=1)
    selected_option: str = Field(min_length=1)


class QuizCompletionResponse(BaseModel):
    quiz_id: str
    score: int
    total_questions: int
    correct_answers: int
    passed: bool
    xp_awarded: int
