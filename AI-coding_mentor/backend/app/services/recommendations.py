from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo.collection import Collection

from app.database.mongodb import get_database
from app.models.language import ProgrammingLanguage
from app.models.question import Difficulty, Topic
from app.models.recommendation import RecommendationDocument
from app.services import assessment as assessment_service
from app.services import assessment_results as result_service
from app.services import questions as question_service
from app.services import roadmap as roadmap_service

SCORING = {
	"weak_topic": 50,
	"developing_topic": 30,
	"roadmap_topic": 35,
	"unseen": 20,
	"appropriate_difficulty": 20,
	"too_difficult": -20,
	"far_too_difficult": -40,
	"recent_attempt": -30,
}


class RecommendationError(RuntimeError):
	pass


class AssessmentRequiredError(RecommendationError):
	pass


class RecommendationScorer(ABC):
	@abstractmethod
	def score(self, question: dict[str, Any], context: dict[str, Any]) -> tuple[int, str, dict[str, int]]:
		raise NotImplementedError


class RuleBasedRecommendationScorer(RecommendationScorer):
	def score(self, question: dict[str, Any], context: dict[str, Any]) -> tuple[int, str, dict[str, int]]:
		topic = Topic(question["topic"]).display_name
		difficulty = Difficulty(question["difficulty"])
		weak = topic in context["weak_topics"]
		developing = topic in context["developing_topics"]
		roadmap_topic = topic == context.get("current_topic")
		recent = question["question_id"] in context["recent_attempts"]
		unseen = question["question_id"] not in context["attempted"]
		allowed = context["allowed_difficulties"].get(topic, {Difficulty.EASY})
		difficulty_score = (
			SCORING["appropriate_difficulty"]
			if difficulty in allowed
			else SCORING["far_too_difficult"]
			if difficulty == Difficulty.HARD and allowed == {Difficulty.EASY}
			else SCORING["too_difficult"]
		)
		breakdown = {
			"weak_topic_bonus": SCORING["weak_topic"] if weak else 0,
			"developing_topic_bonus": SCORING["developing_topic"] if developing else 0,
			"roadmap_bonus": SCORING["roadmap_topic"] if roadmap_topic else 0,
			"unseen_bonus": SCORING["unseen"] if unseen else 0,
			"difficulty_bonus": difficulty_score,
			"recent_attempt_penalty": SCORING["recent_attempt"] if recent else 0,
		}
		score = sum(breakdown.values())
		if weak:
			reason = f"Recommended because {topic} is one of your weak topics."
		elif developing:
			reason = f"Recommended to strengthen your developing {topic} skills."
		elif roadmap_topic:
			reason = "Recommended to strengthen your current roadmap topic."
		elif recent:
			reason = f"Recommended for revision because {topic} needs more practice."
		else:
			reason = "Recommended as the next difficulty step after your recent progress."
		return score, reason, breakdown


def get_recommendations_collection() -> Collection:
	collection = get_database()[RecommendationDocument.collection_name]
	collection.create_index("user_id")
	collection.create_index([("user_id", 1), ("status", 1)])
	collection.create_index([("user_id", 1), ("question_id", 1), ("status", 1)])
	return collection


def _allowed_difficulties(topic_scores: dict[str, int]) -> dict[str, set[Difficulty]]:
	allowed = {}
	for topic, score in topic_scores.items():
		if score < 50:
			allowed[topic] = {Difficulty.EASY}
		elif score < 80:
			allowed[topic] = {Difficulty.EASY, Difficulty.MEDIUM}
		else:
			allowed[topic] = {Difficulty.MEDIUM}
	return allowed


def _context(*, user_id: str, language: ProgrammingLanguage, result: dict[str, Any]) -> dict[str, Any]:
	submissions = assessment_service.get_assessment_submissions_collection()
	user_submissions = list(submissions.find({"user_id": user_id}))
	attempted = {item["question_id"] for item in user_submissions}
	solved = {item["question_id"] for item in user_submissions if item.get("status") == "accepted"}
	cutoff = datetime.now(timezone.utc) - timedelta(days=7)
	recent = {
		item["question_id"] for item in user_submissions
		if isinstance(item.get("submitted_at"), datetime) and item["submitted_at"] >= cutoff
	}
	topic_scores = result.get("topic_scores", {})
	developing = {topic for topic, score in topic_scores.items() if 50 <= score < 80}
	current_topic = None
	try:
		current_topic = roadmap_service.get_current_topic(user_id=user_id).get("topic")
	except Exception:
		pass
	return {
		"language": language,
		"attempted": attempted,
		"solved": solved,
		"recent_attempts": recent,
		"weak_topics": set(result.get("weak_topics", [])),
		"developing_topics": developing,
		"current_topic": current_topic,
		"allowed_difficulties": _allowed_difficulties(topic_scores),
	}


def generate_recommendations(*, user_id: str, language: ProgrammingLanguage, limit: int = 5) -> dict[str, Any]:
	result = result_service.get_assessment_results_collection().find_one({"user_id": user_id}, sort=[("created_at", -1)])
	if result is None:
		raise AssessmentRequiredError("Complete your coding assessment to receive personalized recommendations.")
	context = _context(user_id=user_id, language=language, result=result)
	scorer = RuleBasedRecommendationScorer()
	try:
		roadmap = roadmap_service.get_roadmap(user_id=user_id)
		locked = {item["topic"] for item in roadmap["topics"] if item["status"] == "locked"}
	except Exception:
		locked = set()
	scored = []
	for question in question_service.find_questions(language=language):
		if question.get("language") != language.value:
			continue
		topic = Topic(question["topic"]).display_name
		if question["question_id"] in context["solved"] or topic in locked:
			continue
		score, reason, breakdown = scorer.score(question, context)
		scored.append((score, question["difficulty"], question["question_id"], reason, breakdown, question))
	scored.sort(key=lambda item: (-item[0], item[1], item[2]))
	collection = get_recommendations_collection()
	collection.delete_many({"user_id": user_id, "status": "recommended"})
	documents = []
	for score, _difficulty, _id, reason, breakdown, question in scored[:limit]:
		document = RecommendationDocument.new(user_id=user_id, question=question, score=score, reason=reason, breakdown=breakdown)
		collection.insert_one(document)
		documents.append(document)
	return {"status": "ready", "language": language.value, "recommendations": documents, "generated_at": datetime.now(timezone.utc)}


def get_current_recommendations(*, user_id: str, language: ProgrammingLanguage, limit: int = 5) -> dict[str, Any]:
	collection = get_recommendations_collection()
	existing = list(collection.find({"user_id": user_id, "status": "recommended"}).sort("score", -1).limit(limit))
	if not existing:
		return generate_recommendations(user_id=user_id, language=language, limit=limit)
	return {"status": "ready", "language": language.value, "recommendations": existing, "generated_at": existing[0].get("generated_at")}
