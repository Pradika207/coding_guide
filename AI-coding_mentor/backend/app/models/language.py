from enum import Enum


class ProgrammingLanguage(str, Enum):
    C = "c"
    CPP = "cpp"
    JAVA = "java"
    PYTHON = "python"
    JAVASCRIPT = "javascript"

    @property
    def display_name(self) -> str:
        return {
            ProgrammingLanguage.C: "C",
            ProgrammingLanguage.CPP: "C++",
            ProgrammingLanguage.JAVA: "Java",
            ProgrammingLanguage.PYTHON: "Python",
            ProgrammingLanguage.JAVASCRIPT: "JavaScript",
        }[self]
