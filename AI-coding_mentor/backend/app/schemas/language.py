from pydantic import BaseModel

from app.models.language import ProgrammingLanguage


class LanguageOption(BaseModel):
    id: ProgrammingLanguage
    name: str


class LanguagesResponse(BaseModel):
    languages: list[LanguageOption]


class SelectLanguageRequest(BaseModel):
    language: ProgrammingLanguage


class CurrentLanguageResponse(BaseModel):
    selected_language: ProgrammingLanguage | None = None
