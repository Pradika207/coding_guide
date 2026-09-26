from pydantic import BaseModel, Field

from app.database.config import settings
from app.models.language import ProgrammingLanguage


class CodeExecutionRequest(BaseModel):
    language: ProgrammingLanguage
    source_code: str = Field(
        min_length=1,
        max_length=settings.max_source_code_bytes,
    )
    stdin: str = Field(
        default="",
        max_length=settings.max_stdin_bytes,
    )


class CodeExecutionResult(BaseModel):
    status: str
    stdout: str
    stderr: str
    compile_output: str
    execution_time: float | None = None
    memory: int | None = None
