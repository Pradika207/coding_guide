from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class RecommendationDocument:
    collection_name = "recommendations"

    @staticmethod
    def new(*, user_id: str, question: dict[str, Any], score: int, reason: str, breakdown: dict[str, int]) -> dict[str, Any]:
        return {
            "recommendation_id": str(uuid4()),
            "user_id": user_id,
            "question_id": question["question_id"],
            "language": question["language"],
            "topic": question["topic"],
            "difficulty": question["difficulty"],
            "title": question["title"],
            "score": score,
            "reason": reason,
            "source": "rule_based",
            "score_breakdown": breakdown,
            "generated_at": datetime.now(timezone.utc),
            "status": "recommended",
        }
