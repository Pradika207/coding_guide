from typing import Any

from app.models.assessment import AssessmentSubmissionDocument, AssessmentStatus
from app.models.language import ProgrammingLanguage
from app.services import judge0
from app.services import questions as question_service
from app.services import assessment as assessment_service
from app.services import badges, gamification


def _aggregate_execution_results(results: list[judge0.NormalizedExecutionResult]) -> judge0.NormalizedExecutionResult:
    first_result = results[0]
    status = "accepted"
    for result in results:
        if result.status != "accepted":
            status = result.status
            break
    execution_times = [result.execution_time for result in results if result.execution_time is not None]
    memories = [result.memory for result in results if result.memory is not None]
    return judge0.NormalizedExecutionResult(
        status=status,
        stdout=first_result.stdout,
        stderr=first_result.stderr,
        compile_output=first_result.compile_output,
        execution_time=sum(execution_times) if execution_times else None,
        memory=max(memories) if memories else None,
    )


def submit_assessment_code(
    *,
    session_id: str,
    user_id: str,
    question_id: str,
    source_code: str,
    stdin: str,
) -> dict[str, Any]:
    session = assessment_service.get_owned_session(session_id=session_id, user_id=user_id)
    if session["status"] != AssessmentStatus.IN_PROGRESS.value:
        raise assessment_service.AssessmentStateError(
            "Assessment session is already completed or abandoned"
        )
    if question_id not in session["question_ids"]:
        raise assessment_service.AssessmentQuestionError(
            "Question does not belong to this assessment"
        )

    question = question_service.find_question(question_id)
    if question is None:
        raise assessment_service.AssessmentQuestionError("Question not found")

    language = ProgrammingLanguage(session["language"])
    results = [
        judge0.execute_code(
            language=language,
            source_code=source_code,
            stdin=test_case["input"],
            expected_output=test_case["expected_output"],
        )
        for test_case in question.get("test_cases", [])
    ]
    if not results:
        raise assessment_service.AssessmentQuestionError(
            "Question has no executable test cases"
        )

    result = _aggregate_execution_results(results)
    submissions = assessment_service.get_assessment_submissions_collection()
    attempt_number = submissions.count_documents(
        {"session_id": session_id, "question_id": question_id}
    ) + 1
    submission = AssessmentSubmissionDocument.new(
        session_id=session_id,
        user_id=user_id,
        question_id=question_id,
        source_code=source_code,
        stdin=stdin,
        status=result.status,
        attempt_number=attempt_number,
        execution_time=result.execution_time,
        memory=result.memory,
    )
    submissions.insert_one(submission)

    if result.status == "accepted":
        event_type = {
            "easy": "coding_easy_completed",
            "medium": "coding_medium_completed",
            "hard": "coding_hard_completed",
        }.get(question.get("difficulty"))
        if event_type is not None:
            try:
                activity = gamification.record_activity(
                    user_id=user_id,
                    event_type=event_type,
                    source_id=question_id,
                )
                badges.evaluate_badges(user_id=user_id, profile=activity["profile"])
            except Exception:
                pass

    return {
        "question_id": question_id,
        **result.as_dict(),
        "attempt_number": attempt_number,
    }
