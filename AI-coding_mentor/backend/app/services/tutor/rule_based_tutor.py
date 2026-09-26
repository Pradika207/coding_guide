"""Deterministic progressive programming hints; never emits executable answers."""

from __future__ import annotations

import re
from typing import Any, NamedTuple

from app.database.config import settings
from app.models.question import Difficulty, Topic
from app.schemas.tutor import TutorRequest, TutorResponse


class TutorGuidance(NamedTuple):
    concept: str
    conceptual: str
    debugging: str
    detailed: str
    pseudocode: str


_GUIDANCE: dict[Topic, TutorGuidance] = {
    Topic.FUNDAMENTALS: TutorGuidance("Programming fundamentals", "Restate the inputs, required output, and the rule connecting them.", "Check the order of operations and the value at each step.", "Try the smallest valid input and compare each intermediate value with what the task requires.", "Outline: read the input → apply the stated rule → produce the required output."),
    Topic.VARIABLES: TutorGuidance("Variables and state", "Track what each variable represents as the program runs.", "Check initialization, reassignment, scope, and whether a value is overwritten too early.", "Trace each assignment in order and confirm the variable still represents the quantity its later use expects.", "Outline: initialize state → update it only when the relevant condition holds → use the final state."),
    Topic.CONDITIONALS: TutorGuidance("Conditional logic", "Compare the decision branches with the cases described by the question.", "Check condition boundaries, branch order, and whether every case reaches the intended branch.", "Test values just below, on, and just above each boundary; watch for overlapping or missing cases.", "Outline: check each condition in order → handle its matching case → provide a fallback case."),
    Topic.LOOPS: TutorGuidance("Loop iteration", "Consider which items or steps the loop should visit.", "Check the initial value, stopping condition, update step, and inclusive/exclusive boundary.", "Trace two or three iterations and verify the loop advances, terminates, and visits the final required item.", "Outline: initialize → while items remain, process the current item and advance → return the accumulated result."),
    Topic.FUNCTIONS: TutorGuidance("Function inputs and outputs", "Check the contract between the function's inputs and its return value.", "Inspect parameter use, return paths, and whether a value is returned rather than only displayed.", "Follow one representative input through the function and compare the returned value with the contract.", "Outline: validate/use parameters → compute the result → return it on every required path."),
    Topic.ARRAYS: TutorGuidance("Array traversal", "Check how the loop visits each element and maintains the result so far.", "Inspect the first and last indexes, loop bound, initialization, and updates inside the loop.", "Trace a short array including one-element and boundary cases; note the index and accumulated value after every iteration.", "Outline: initialize an accumulator → visit each valid index → update from the current element → return the accumulator."),
    Topic.STRINGS: TutorGuidance("String processing", "Consider whether the task operates on characters, substrings, or the whole string.", "Check empty and one-character strings, index boundaries, and case/whitespace assumptions.", "Trace a short string character by character and compare the expected handling of repeated or boundary characters.", "Outline: initialize result → process each required character or range → apply the stated rule → return the result."),
    Topic.SEARCHING: TutorGuidance("Search strategy", "Clarify what it means for the target to be found and what to return otherwise.", "Check the search range, comparison direction, and the not-found result.", "Test a target at the beginning, middle, end, and absent; for a narrowed range, verify each update keeps the answer possible.", "Outline: choose a candidate range → compare the target → return or shrink the range → report not found if empty."),
    Topic.SORTING: TutorGuidance("Ordering and sorting", "Check the required ordering and how each step moves items toward it.", "Inspect the comparison direction, swapped range, and whether each pass makes progress.", "Trace a tiny unsorted input with duplicates and verify the ordering invariant after each pass.", "Outline: establish an ordering invariant → repeatedly place or select the next item → verify adjacent items."),
    Topic.RECURSION: TutorGuidance("Recursion", "Identify the smallest subproblem and how the problem becomes smaller.", "Check the base case, progress toward it, and how each recursive result is combined.", "Trace a small input down to the base case and back; confirm every call changes the input toward termination.", "Outline: if the base case holds, return its result; otherwise solve a smaller input and combine the result."),
    Topic.LINKED_LISTS: TutorGuidance("Linked-list traversal", "Follow the links from the head and track which node each reference represents.", "Check null/end conditions and preserve the next reference before changing links.", "Draw a few nodes and update one link at a time; include empty and single-node lists.", "Outline: start at the head → process the current node → advance using its next link → stop at the end."),
    Topic.STACK: TutorGuidance("Stack operations", "Check whether the operation follows last-in, first-out order.", "Inspect empty-stack handling and the order of push/pop operations.", "Trace the stack contents after each operation, especially when it becomes empty or has one item.", "Outline: apply each operation to the top → guard empty access → read the top result when required."),
    Topic.QUEUE: TutorGuidance("Queue operations", "Check whether items are processed in first-in, first-out order.", "Inspect front/rear updates and empty-queue behavior.", "Trace the front and back after enqueue/dequeue operations, including wrap-around if using a fixed buffer.", "Outline: add at the rear → remove from the front → update indices → handle empty state."),
    Topic.HASHING: TutorGuidance("Hash maps and sets", "Decide what key or membership fact should be stored for each item.", "Check key choice, lookup-before-update order, and duplicate handling.", "Trace a tiny input with a repeated key and verify the stored value or membership result after each step.", "Outline: derive a key → query/update the map or set → use the recorded state to decide the result."),
    Topic.TREES: TutorGuidance("Tree traversal", "Identify which nodes the task needs and the required traversal order.", "Check null-child handling, recursive/iterative visit order, and whether each child is processed.", "Draw a small tree and mark the exact order nodes should be visited for the chosen traversal.", "Outline: handle an empty node → visit/process in the required order → combine child results."),
    Topic.GRAPHS: TutorGuidance("Graph traversal", "Clarify the graph representation and what counts as reaching a node.", "Check visited-state timing, neighbor iteration, and disconnected components.", "Trace a small graph with a cycle; mark when nodes become visited so they are not repeatedly explored.", "Outline: initialize a frontier and visited set → explore neighbors → add unseen nodes → stop when the goal or frontier condition is met."),
    Topic.DYNAMIC_PROGRAMMING: TutorGuidance("Dynamic programming", "Look for repeated subproblems and define what one state means.", "Check state meaning, base values, transition dependencies, and iteration order.", "Write the recurrence for a tiny input and fill a few states manually before implementing the transition.", "Outline: define state → initialize base cases → compute each state from smaller states → read the requested state."),
    Topic.OBJECT_ORIENTED_PROGRAMMING: TutorGuidance("Object-oriented design", "Consider which data belongs together and which operation owns each behavior.", "Check object initialization, method parameters, instance state, and visibility/override behavior.", "Trace object creation and a method call, noting which instance fields are read or changed.", "Outline: define the object's state → initialize it → expose focused methods that maintain its invariants."),
}


_ERROR_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"arrayindexoutofbound|index out of bounds|list index out of range", re.I), "Check array/list index boundaries and confirm the index stays between the first and last valid positions.", "Trace the index at the first and final loop iterations, including empty and one-element inputs."),
    (re.compile(r"nullpointer|null reference|noneType|undefined is not an object", re.I), "Check whether the referenced value is initialized before it is accessed.", "Trace where the value is assigned and add a safe path for missing or empty values."),
    (re.compile(r"syntaxerror|syntax error|expected .*token|missing .*semicolon", re.I), "The code did not compile or parse, so inspect syntax before the algorithm.", "Check the reported location, then review brackets, indentation, punctuation, and statement structure nearby."),
    (re.compile(r"nameerror|undefined symbol|undeclared identifier|cannot find symbol", re.I), "Check the spelling, declaration, and scope of the referenced name.", "Compare the name at the use site with its declaration and confirm it is visible there."),
    (re.compile(r"typeerror|incompatible types|cannot convert|operand type", re.I), "Check whether the operation receives values of compatible types.", "Inspect the types at the operation and convert or handle values according to the language's rules."),
    (re.compile(r"division by zero|divide by zero|zerodivision", re.I), "Check whether the divisor can be zero before performing the division.", "Trace the divisor for boundary inputs and decide how the zero case should be handled."),
    (re.compile(r"maximum recursion|stack overflow|recursion depth", re.I), "Check that recursive calls make progress toward a terminating base case.", "Trace the input at each call and confirm it becomes smaller or otherwise reaches the base condition."),
    (re.compile(r"time limit|timed out", re.I), "The program may be doing more work than the input limits allow.", "Estimate how the work grows with input size and look for repeated scans or nested loops."),
)


def _error_guidance(request: TutorRequest) -> tuple[str, str] | None:
    if request.submission_status == "compilation_error":
        detail = request.compiler_error
        if detail:
            for pattern, explanation, next_step in _ERROR_RULES:
                if pattern.search(detail):
                    return explanation, next_step
            return (
                "Compilation stopped before execution. A compiler diagnostic was provided, but its raw text is not repeated here.",
                "Read the first compiler diagnostic and inspect the indicated code location for syntax, type, import, or declaration issues.",
            )
        return (
            "Compilation stopped before the program could run. Start by checking syntax, declarations, imports, and type compatibility.",
            "Compile again after reviewing the first reported diagnostic; do not debug runtime logic until compilation succeeds.",
        )
    if request.submission_status in {"runtime_error", "time_limit_exceeded", "memory_limit_exceeded"}:
        detail = request.runtime_error or request.compiler_error
        if detail:
            for pattern, explanation, next_step in _ERROR_RULES:
                if pattern.search(detail):
                    return explanation, next_step
            return (
                "The program started but did not complete successfully. A runtime diagnostic was provided, but its raw text is not repeated here.",
                "Trace the values immediately before the failing operation and check boundary, empty-input, and termination cases.",
            )
        return (
            "The program started but did not complete successfully. Check the operation that fails at runtime and the state it receives.",
            "Trace the execution with a small input and check bounds, missing values, division, and termination conditions.",
        )
    return None


def _status_guidance(request: TutorRequest) -> tuple[str, str]:
    if request.submission_status == "accepted":
        if request.difficulty == Difficulty.HARD:
            return (
                "Your solution passed. Review whether the approach scales to the largest stated inputs and whether its invariant is clear.",
                "Explain the time and space complexity, then check one boundary case from the constraints.",
            )
        return (
            "Your solution passed. A useful next step is to make the key idea easy to explain and check one boundary case.",
            "Describe the approach in a sentence and review the constraints for a simpler or more efficient alternative.",
        )
    if request.submission_status == "wrong_answer":
        return (
            "The program ran, but its result differs from the expected behavior. Recheck the logic and the cases around its boundaries.",
            "Trace one failing or small example and verify initialization, loop conditions, updates, and the returned value.",
        )
    return (
        "The submission is still pending or did not produce a final result. Wait for the execution result before changing the algorithm.",
        "Once execution finishes, use its final status and any reported error to choose the next debugging step.",
    )


def _code_specific_hint(request: TutorRequest, level: int) -> str | None:
    if request.submission_status != "wrong_answer" or request.topic not in {Topic.ARRAYS, Topic.LOOPS}:
        return None
    code = request.code
    if re.search(r"<=\s*len\s*\(|range\s*\(\s*len\s*\([^)]*\)\s*\+\s*1", code):
        if level >= 3:
            return "Trace the final loop index and compare it with the last valid array index; the loop may advance one position too far."
        return "Check whether the loop condition includes an index equal to the array length; that is one past the final valid index."
    return None


def _question_specific_hint(question_context: dict[str, Any] | None) -> str | None:
    if not question_context:
        return None
    prompt = " ".join((
        str(question_context.get("title", "")),
        str(question_context.get("description", "")),
        " ".join(str(value) for value in question_context.get("constraints", [])),
    )).lower()
    if any(word in prompt for word in ("maximum", "largest", "greatest")):
        return "For this question, consider maintaining the best value seen so far as you traverse the input."
    if any(word in prompt for word in ("minimum", "smallest", "least")):
        return "For this question, consider maintaining the smallest value seen so far as you traverse the input."
    if any(word in prompt for word in ("frequency", "occurrences", "how many times")):
        return "For this question, decide what state records the count for each relevant value."
    if "sorted" in prompt or "in ascending order" in prompt:
        return "For this question, check the required ordering and how each step establishes it."
    return None


class RuleBasedTutorProvider:
    name = "rule_based"

    def provide_hint(
        self,
        request: TutorRequest,
        *,
        hint_level: int | None = None,
        question_context: dict[str, Any] | None = None,
    ) -> TutorResponse:
        level = hint_level or request.hint_level
        guidance = _GUIDANCE[request.topic]
        error = _error_guidance(request)
        if error:
            explanation, next_step = error
        else:
            explanation, next_step = _status_guidance(request)

        if level == 1:
            hint = f"Start with the main idea for {guidance.concept.lower()}."
            if error:
                hint = "First understand what the reported error says; then connect it to the relevant concept."
            elif request.submission_status == "wrong_answer":
                hint = "Focus on the logic that transforms the input, then test a small edge case."
            elif request.submission_status == "accepted":
                hint = "Your approach passed; consider what invariant makes it correct."
        elif level == 2:
            hint = guidance.conceptual
            if error:
                hint = explanation
        elif level == 3:
            hint = guidance.debugging
            if error:
                hint = next_step
        else:
            hint = guidance.pseudocode

        code_hint = _code_specific_hint(request, level)
        if code_hint and not error:
            hint = code_hint
        question_hint = _question_specific_hint(question_context)
        if question_hint and level == 2 and not error and not code_hint:
            hint = question_hint

        if level == 1 and not error:
            next_step = guidance.conceptual
        elif level == 2 and not error:
            next_step = guidance.debugging
        elif level == 3 and not error:
            next_step = guidance.pseudocode
        elif level == 4:
            next_step = "Implement one step of the outline at a time, then test it with a small input and a boundary case."

        if request.submission_status == "accepted":
            explanation, next_step = _status_guidance(request)

        return TutorResponse(
            hint=hint,
            explanation=explanation,
            concept=guidance.concept,
            next_step=next_step,
            hint_level=level,
            provider=self.name,
            can_request_next_hint=level < settings.tutor_max_hint_level,
        )
