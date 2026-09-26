from typing import Any

from app.models.language import ProgrammingLanguage
from app.models.lesson import ContentType, LessonDocument, QuizDocument
from app.models.question import Topic
from app.services.lessons import get_lessons_collection, get_quizzes_collection


def _content(topic: str, example: str, tip: str) -> list[dict[str, str]]:
    return [
        {"type": ContentType.CONCEPT.value, "title": f"What are {topic}?", "text": f"{topic} are a core programming idea used to organize and transform data."},
        {"type": ContentType.EXAMPLE.value, "title": "Simple example", "text": example},
        {"type": ContentType.TIP.value, "title": "Helpful tip", "text": tip},
        {"type": ContentType.SUMMARY.value, "title": "Summary", "text": f"You can now describe the purpose of {topic} and recognize a basic use for them."},
    ]


def _lesson(
    lesson_id: str,
    language: ProgrammingLanguage,
    topic: Topic,
    title: str,
    order: int,
    example: str,
    tip: str,
    question_ids: list[str] | None = None,
) -> dict[str, Any]:
    return LessonDocument.new(
        lesson_id=lesson_id,
        language=language,
        topic=topic,
        title=title,
        description=f"A short beginner lesson about {topic.display_name.lower()}.",
        order=order,
        content=_content(topic.display_name, example, tip),
        quiz_ids=[f"{lesson_id}-quiz-1"],
        question_ids=question_ids or [],
    )


SAMPLE_LESSONS = [
    _lesson("java-fundamentals-01", ProgrammingLanguage.JAVA, Topic.FUNDAMENTALS, "Java Fundamentals", 1, "A Java program starts from a class and a main method.", "Keep the class name and file name aligned when using a simple Java runner."),
    _lesson("java-variables-01", ProgrammingLanguage.JAVA, Topic.VARIABLES, "Java Variables", 1, "int score = 10; stores an integer value in score.", "Choose a type that matches the values your variable can hold."),
    _lesson("java-loops-01", ProgrammingLanguage.JAVA, Topic.LOOPS, "Java Loop Basics", 1, "for (int i = 0; i < 3; i++) repeats a block three times.", "Check the loop condition and update together to avoid an infinite loop."),
    _lesson("java-loops-02", ProgrammingLanguage.JAVA, Topic.LOOPS, "Java Loop Patterns", 2, "A while loop is useful when the number of repetitions depends on input.", "Update the value used by the while condition inside the loop."),
    _lesson("java-arrays-01", ProgrammingLanguage.JAVA, Topic.ARRAYS, "Introduction to Java Arrays", 1, "int[] values = {2, 4, 6}; creates an array with three elements.", "Array indexes start at zero." , ["java-arrays-001"]),
    _lesson("java-arrays-02", ProgrammingLanguage.JAVA, Topic.ARRAYS, "Traversing Java Arrays", 2, "A for loop can visit values[0] through values[values.length - 1].", "Use length rather than a repeated magic number."),
    _lesson("java-strings-01", ProgrammingLanguage.JAVA, Topic.STRINGS, "Java Strings", 1, "String word = \"mentor\"; stores text.", "Use equals for string values instead of comparing object references."),
    _lesson("java-sorting-01", ProgrammingLanguage.JAVA, Topic.SORTING, "Java Sorting Basics", 1, "Compare neighboring values and swap them to practice a simple sort.", "A sorted list has every earlier value less than or equal to the next.", ["java-sorting-001"]),
    _lesson("java-sorting-02", ProgrammingLanguage.JAVA, Topic.SORTING, "Choosing a Sorting Strategy", 2, "Insertion sort grows a sorted prefix one item at a time.", "Start by understanding correctness before optimizing complexity."),
    _lesson("python-fundamentals-01", ProgrammingLanguage.PYTHON, Topic.FUNDAMENTALS, "Python Fundamentals", 1, "print(\"Hello, mentor\") displays text.", "Python uses indentation to define blocks."),
    _lesson("python-variables-01", ProgrammingLanguage.PYTHON, Topic.VARIABLES, "Python Variables", 1, "score = 10 binds a name to an integer.", "Use descriptive names so code communicates intent."),
    _lesson("python-loops-01", ProgrammingLanguage.PYTHON, Topic.LOOPS, "Python Loop Basics", 1, "for value in values visits each item in a collection.", "Prefer a direct loop when you do not need indexes."),
    _lesson("python-loops-02", ProgrammingLanguage.PYTHON, Topic.LOOPS, "Python While Loops", 2, "while count < 3 repeats while its condition is true.", "Change the loop state on every path."),
    _lesson("python-arrays-01", ProgrammingLanguage.PYTHON, Topic.ARRAYS, "Introduction to Python Lists", 1, "values = [2, 4, 6] creates a mutable sequence.", "Lists can grow, while indexing still starts at zero.", ["python-arrays-001"]),
    _lesson("python-arrays-02", ProgrammingLanguage.PYTHON, Topic.ARRAYS, "Traversing Python Lists", 2, "for value in values can process each list item.", "Use enumerate when you need both an index and a value."),
    _lesson("python-strings-01", ProgrammingLanguage.PYTHON, Topic.STRINGS, "Python Strings", 1, "word = \"mentor\" stores text and word[::-1] reverses it.", "Strings are immutable, so transformations return new strings."),
    _lesson("python-sorting-01", ProgrammingLanguage.PYTHON, Topic.SORTING, "Python Sorting Basics", 1, "sorted(values) returns a new sorted list.", "Keep the original list when later code needs its original order.", ["python-sorting-001"]),
    _lesson("python-sorting-02", ProgrammingLanguage.PYTHON, Topic.SORTING, "Sorting with a Key", 2, "sorted(words, key=len) orders words by length.", "A key function describes what should be compared."),
]


def seed_sample_lessons() -> int:
    lessons = get_lessons_collection()
    quizzes = get_quizzes_collection()
    inserted = 0
    for lesson in SAMPLE_LESSONS:
        result = lessons.update_one(
            {"lesson_id": lesson["lesson_id"]},
            {"$setOnInsert": lesson},
            upsert=True,
        )
        inserted += int(result.upserted_id is not None)
        quiz = QuizDocument.new(
            quiz_id=f"{lesson['lesson_id']}-quiz-1",
            lesson_id=lesson["lesson_id"],
            question=f"Which statement best describes this {lesson['topic']} lesson?",
            options=["It introduces a core idea", "It deletes all data", "It requires machine learning", "It is unrelated to programming"],
            correct_option="It introduces a core idea",
            explanation="The lesson focuses on a core programming concept and a small example.",
        )
        quizzes.update_one(
            {"quiz_id": quiz["quiz_id"]},
            {"$setOnInsert": quiz},
            upsert=True,
        )
    return inserted
