from fastapi import APIRouter

from app.models.language import ProgrammingLanguage
from app.schemas.language import LanguageOption, LanguagesResponse

router = APIRouter(tags=["languages"])


@router.get("/languages", response_model=LanguagesResponse)
def get_available_languages() -> LanguagesResponse:
    return LanguagesResponse(
        languages=[
            LanguageOption(id=language, name=language.display_name)
            for language in ProgrammingLanguage
        ]
    )
