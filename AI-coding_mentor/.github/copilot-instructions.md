# Copilot instructions for this project

## Working style
- Work within the existing project structure. Do not recreate the project, rewrite it, or start a parallel app.
- Preserve existing functionality and do not break the current backend or frontend.
- Prefer minimal, targeted changes over large refactors.
- Reuse existing routes, schemas, services, components, and APIs before creating new abstractions.
- Keep the feature scope aligned with the current step and do not add unrelated features.

## Safety rules
- Never remove existing working functionality.
- Never replace working logic with a new implementation unless the current code is truly broken and a narrow fix is required.
- Do not change backend contracts unless the existing code and tests clearly require it.
- Do not add broad "cleanup" changes while fixing a specific issue.
- Do not claim live success for services that are external dependencies (MongoDB, Judge0, MLflow, Docker) unless they were verified in this runtime.

## Backend expectations
- Keep FastAPI routes, auth, validation, and database access stable.
- Preserve current security and RBAC patterns.
- Do not introduce unnecessary database migrations or schema churn.
- When debugging, trace the request flow from route to service to database before patching.

## Frontend expectations
- Keep the current React app structure intact.
- Respect existing auth guards, route flow, and API client patterns.
- Avoid duplicate API layers or duplicated page logic.
- Preserve protected routes and unauthenticated redirect behavior.
- Keep UI changes consistent with the existing design language and project conventions.

## Verification
- Validate with the smallest relevant command that checks the changed behavior.
- Run real project checks when possible: targeted tests, frontend build, backend test validation, or a focused API check.
- Report actual status honestly, including missing services or environment requirements.
- If something cannot be verified, say so explicitly instead of claiming it works.

## Scope discipline
- If the request says a feature is out of scope, do not implement it.
- If the ask is a quality or finalization pass, focus on stabilization, testing, and honest reporting rather than adding new feature count.
- Keep work aligned with the active project phase: student experience, admin observability, or final presentation readiness as applicable.

## Output quality
- Keep explanations brief, practical, and grounded in the codebase.
- Prefer direct fixes and evidence-based validation.
- Summaries should mention concrete files, affected behavior, and verification outcomes.
