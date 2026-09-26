from typing import Any

from app.models.question import Difficulty, QuestionDocument, Topic
from app.models.language import ProgrammingLanguage
from app.services.questions import get_questions_collection


def _question(
    question_id: str,
    title: str,
    description: str,
    language: ProgrammingLanguage,
    topic: Topic,
    difficulty: Difficulty,
    sample_input: str,
    sample_output: str,
    hidden_input: str,
    hidden_output: str,
    constraints: list[str],
) -> dict[str, Any]:
    return QuestionDocument.new(
        question_id=question_id,
        title=title,
        description=description,
        language=language,
        topic=topic,
        difficulty=difficulty,
        sample_input=sample_input,
        sample_output=sample_output,
        test_cases=[
            {"input": sample_input, "expected_output": sample_output, "is_hidden": False},
            {"input": hidden_input, "expected_output": hidden_output, "is_hidden": True},
        ],
        constraints=constraints,
        time_limit=2,
        memory_limit=256,
    )


SAMPLE_QUESTIONS = [
    _question("java-arrays-001", "Find the Maximum Element", "Find the largest value in an integer array.", ProgrammingLanguage.JAVA, Topic.ARRAYS, Difficulty.EASY, "5\n2 8 3 10 4", "10", "3\n-5 -2 -9", "-2", ["1 <= n <= 100000"]),
    _question("python-loops-001", "Sum the Positive Values", "Calculate the sum of all positive integers in a list.", ProgrammingLanguage.PYTHON, Topic.LOOPS, Difficulty.EASY, "5\n-2 4 0 3 -1", "7", "4\n-8 -2 0 -4", "0", ["1 <= n <= 100000"]),
    _question("python-variables-001", "Average of Two Scores", "Read two numbers and print their average.", ProgrammingLanguage.PYTHON, Topic.VARIABLES, Difficulty.EASY, "10\n20", "15", "4\n8", "6", ["Values are integers."]),
    _question("python-conditionals-001", "Check the Grade", "Print whether a score is passing.", ProgrammingLanguage.PYTHON, Topic.CONDITIONALS, Difficulty.EASY, "75", "pass", "40", "fail", ["Score is an integer from 0 to 100."]),
    _question("python-functions-001", "Square a Number", "Write a function to return the square of an integer.", ProgrammingLanguage.PYTHON, Topic.FUNCTIONS, Difficulty.EASY, "8", "64", "0", "0", ["Input is an integer."]),
    _question("python-fundamentals-001", "Print the Name", "Read a name and print it exactly as entered.", ProgrammingLanguage.PYTHON, Topic.FUNDAMENTALS, Difficulty.EASY, "mentor", "mentor", "alice", "alice", ["Input is a single word."]),
    _question("cpp-strings-001", "Reverse a Word", "Print the characters of a word in reverse order.", ProgrammingLanguage.CPP, Topic.STRINGS, Difficulty.EASY, "mentor", "rotnem", "abc", "cba", ["The word contains only letters."]),
    _question("javascript-functions-001", "Count Vowels", "Count the vowels in a lowercase word.", ProgrammingLanguage.JAVASCRIPT, Topic.FUNCTIONS, Difficulty.EASY, "coding", "2", "rhythm", "0", ["The input contains lowercase letters only."]),
    _question("c-fundamentals-001", "Classify a Number", "Print whether an integer is even or odd.", ProgrammingLanguage.C, Topic.FUNDAMENTALS, Difficulty.EASY, "14", "even", "-7", "odd", ["-1000000 <= n <= 1000000"]),
    _question("java-arrays-002", "Find the Second Largest", "Find the second distinct largest value in an integer array.", ProgrammingLanguage.JAVA, Topic.ARRAYS, Difficulty.MEDIUM, "5\n4 1 9 9 6", "6", "4\n-1 -4 -2 -1", "-2", ["The array has at least two distinct values."]),
    _question("python-strings-001", "Check a Palindrome", "Determine whether a word reads the same forwards and backwards.", ProgrammingLanguage.PYTHON, Topic.STRINGS, Difficulty.MEDIUM, "level", "yes", "mentor", "no", ["The word contains lowercase letters only."]),
    _question("python-variables-002", "Find the Average", "Compute the average of three numbers and print it.", ProgrammingLanguage.PYTHON, Topic.VARIABLES, Difficulty.MEDIUM, "3\n10 20 30", "20", "4\n8 12 16", "12", ["Use integer arithmetic for the calculation."]),
    _question("python-conditionals-002", "Check a Leap Year", "Print whether a year is a leap year.", ProgrammingLanguage.PYTHON, Topic.CONDITIONALS, Difficulty.MEDIUM, "2024", "yes", "1900", "no", ["Year is a positive integer."]),
    _question("cpp-searching-001", "Locate a Target", "Return the zero-based index of a target in a sorted array, or -1 if absent.", ProgrammingLanguage.CPP, Topic.SEARCHING, Difficulty.MEDIUM, "5\n1 3 5 7 9\n7", "3", "4\n2 4 6 8\n5", "-1", ["The array is sorted in ascending order."]),
    _question("javascript-sorting-001", "Sort Three Values", "Print three integers in nondecreasing order.", ProgrammingLanguage.JAVASCRIPT, Topic.SORTING, Difficulty.MEDIUM, "3 1 2", "1 2 3", "9 -1 4", "-1 4 9", ["The input contains exactly three integers."]),
    _question("c-functions-001", "Greatest Common Divisor", "Compute the greatest common divisor of two positive integers.", ProgrammingLanguage.C, Topic.FUNCTIONS, Difficulty.EASY, "18 24", "6", "35 49", "7", ["1 <= a, b <= 1000000000"]),
    _question("java-recursion-001", "Fibonacci Term", "Compute the nth Fibonacci number using a recursive definition or an equivalent method.", ProgrammingLanguage.JAVA, Topic.RECURSION, Difficulty.HARD, "10", "55", "15", "610", ["0 <= n <= 30"]),
    _question("python-sorting-001", "Merge Sorted Lists", "Merge two sorted integer lists into one sorted list.", ProgrammingLanguage.PYTHON, Topic.SORTING, Difficulty.HARD, "3\n1 4 8\n3\n2 3 9", "1 2 3 4 8 9", "2\n-4 7\n4\n-3 0 5 6", "-4 -3 0 5 6 7", ["Both input lists are sorted."]),
    _question("python-functions-002", "Find the Maximum of Three Numbers", "Read three integers and print the largest value.", ProgrammingLanguage.PYTHON, Topic.FUNCTIONS, Difficulty.HARD, "5\n9 2 7", "9", "3\n-5 -2 -9", "-2", ["All numbers are integers."]),
    _question("cpp-linked-lists-001", "Remove Adjacent Duplicates", "Remove consecutive duplicate values from a sequence while preserving order.", ProgrammingLanguage.CPP, Topic.LINKED_LISTS, Difficulty.HARD, "7\n1 1 2 3 3 3 4", "1 2 3 4", "5\n5 5 5 5 5", "5", ["1 <= n <= 100000"]),
    _question("javascript-hashing-001", "First Unique Character", "Print the first character that appears exactly once, or -1 if none exists.", ProgrammingLanguage.JAVASCRIPT, Topic.HASHING, Difficulty.MEDIUM, "swiss", "w", "aabbcc", "-1", ["The string contains lowercase letters only."]),
    _question("c-loops-001", "Count Prime Numbers", "Count the prime numbers from 2 through n.", ProgrammingLanguage.C, Topic.LOOPS, Difficulty.MEDIUM, "10", "4", "1", "0", ["1 <= n <= 100000"]),
]


def seed_sample_questions() -> int:
    questions = get_questions_collection()
    inserted_count = 0
    for question in SAMPLE_QUESTIONS:
        result = questions.update_one(
            {"question_id": question["question_id"]},
            {"$setOnInsert": question},
            upsert=True,
        )
        inserted_count += int(result.upserted_id is not None)
    return inserted_count
