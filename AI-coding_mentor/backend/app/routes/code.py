from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.code_execution import CodeExecutionRequest, CodeExecutionResult
from app.services import judge0
from app.services.security import get_current_user

router = APIRouter(prefix="/code", tags=["code execution"])


@router.post("/execute", response_model=CodeExecutionResult)
def execute_code(
    request: CodeExecutionRequest,
    _: dict = Depends(get_current_user),
) -> CodeExecutionResult:
    try:
        result = judge0.execute_code(
            language=request.language,
            source_code=request.source_code,
            stdin=request.stdin,
        )
    except judge0.Judge0ConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Code execution service is not configured",
        ) from error
    except judge0.Judge0TimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Code execution timed out",
        ) from error
    except judge0.Judge0RequestError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Code execution service is unavailable",
        ) from error

    return CodeExecutionResult.model_validate(result.as_dict())
