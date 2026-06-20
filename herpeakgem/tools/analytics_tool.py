"""Learning Analytics Engine — aggregated study analytics for HerPeakGem.

Competitors like Khan Academy, Coursera, and DeepTutor offer dashboards that
give learners visibility into their study patterns, weak areas, and progress
trends.  HerPeakGem has rich per-turn data (quiz attempts, mastery levels,
error records, spaced-repetition state) but no tool that aggregates it into
actionable analytics.

This tool reads the existing ``LearningService`` / ``LearningStore`` layer and
computes:
  • Overall accuracy and per-module accuracy breakdown
  • Accuracy trend over time (rolling window)
  • Knowledge gap detection (lowest-mastery KPs)
  • Error-type distribution (structural / deviation / application / metacognitive)
  • Study streak and session frequency
  • Spaced-repetition forecast (upcoming reviews)
  • Personalised recommendations based on weak areas
  • Difficulty distribution analysis

Brand: AtomCollide-智械工坊
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter, defaultdict
from typing import Any

from herpeakgem.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Analytics computation helpers (pure logic, no LLM dependency)
# ---------------------------------------------------------------------------

_WINDOW_SECONDS = 7 * 86400  # 7-day rolling window


def _compute_accuracy(attempts: list[dict]) -> dict[str, Any]:
    """Overall and recent accuracy."""
    if not attempts:
        return {"total": 0, "correct": 0, "accuracy_pct": 0.0, "recent_accuracy_pct": 0.0}

    total = len(attempts)
    correct = sum(1 for a in attempts if a.get("is_correct"))
    now = time.time()
    recent = [a for a in attempts if now - a.get("timestamp", 0) < _WINDOW_SECONDS]
    recent_correct = sum(1 for a in recent if a.get("is_correct"))

    return {
        "total": total,
        "correct": correct,
        "accuracy_pct": round(correct / total * 100, 1) if total else 0.0,
        "recent_total": len(recent),
        "recent_correct": recent_correct,
        "recent_accuracy_pct": round(recent_correct / len(recent) * 100, 1) if recent else 0.0,
    }


def _compute_module_breakdown(
    modules: list[dict],
    attempts: list[dict],
    mastery_levels: dict[str, float],
) -> list[dict[str, Any]]:
    """Per-module accuracy and mastery summary."""
    kp_to_module: dict[str, str] = {}
    module_names: dict[str, str] = {}
    for mod in modules:
        module_names[mod["id"]] = mod.get("name", mod["id"])
        for kp in mod.get("knowledge_points", []):
            kp_to_module[kp["id"]] = mod["id"]

    module_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"total": 0, "correct": 0, "kp_mastery_sum": 0.0, "kp_count": 0}
    )
    for a in attempts:
        mid = kp_to_module.get(a.get("knowledge_point_id", ""), "_unknown")
        module_stats[mid]["total"] += 1
        if a.get("is_correct"):
            module_stats[mid]["correct"] += 1

    for kp_id, mid in kp_to_module.items():
        module_stats[mid]["kp_count"] += 1
        module_stats[mid]["kp_mastery_sum"] += mastery_levels.get(kp_id, 0.0)

    result = []
    for mid, stats in module_stats.items():
        total = stats["total"]
        kp_count = max(stats["kp_count"], 1)
        result.append({
            "module_id": mid,
            "name": module_names.get(mid, mid),
            "attempts": total,
            "accuracy_pct": round(stats["correct"] / total * 100, 1) if total else 0.0,
            "avg_mastery_pct": round(stats["kp_mastery_sum"] / kp_count * 100, 1),
            "kp_count": stats["kp_count"],
        })
    result.sort(key=lambda r: r["avg_mastery_pct"])
    return result


def _detect_knowledge_gaps(
    modules: list[dict],
    mastery_levels: dict[str, float],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return the weakest knowledge points."""
    kp_info: dict[str, dict[str, str]] = {}
    for mod in modules:
        for kp in mod.get("knowledge_points", []):
            kp_info[kp["id"]] = {"name": kp.get("name", kp["id"]), "module": mod.get("name", mod["id"])}

    ranked = sorted(mastery_levels.items(), key=lambda kv: kv[1])
    gaps = []
    for kp_id, mastery in ranked[:limit]:
        info = kp_info.get(kp_id, {"name": kp_id, "module": "?"})
        gaps.append({
            "knowledge_point_id": kp_id,
            "name": info["name"],
            "module": info["module"],
            "mastery_pct": round(mastery * 100, 1),
        })
    return gaps


def _error_type_distribution(error_records: list[dict]) -> dict[str, int]:
    """Count errors by type."""
    counter: Counter[str] = Counter()
    for rec in error_records:
        if rec.get("status") in ("active", "retrying"):
            counter[rec.get("error_type", "unknown")] += 1
    return dict(counter)


def _review_forecast(repetition_states: dict[str, dict], limit: int = 10) -> list[dict[str, Any]]:
    """Upcoming spaced-repetition reviews."""
    now = time.time()
    upcoming = []
    for kp_id, state in repetition_states.items():
        due_at = state.get("next_review_at", 0)
        if due_at > now:
            upcoming.append({
                "knowledge_point_id": kp_id,
                "due_in_hours": round((due_at - now) / 3600, 1),
            })
        else:
            upcoming.append({
                "knowledge_point_id": kp_id,
                "due_in_hours": 0,
                "overdue": True,
            })
    upcoming.sort(key=lambda r: r["due_in_hours"])
    return upcoming[:limit]


def _study_streak(attempts: list[dict]) -> dict[str, Any]:
    """Compute current and max study streaks (days with at least 1 attempt)."""
    if not attempts:
        return {"current_streak_days": 0, "max_streak_days": 0, "total_study_days": 0}

    day_set = set()
    for a in attempts:
        ts = a.get("timestamp", 0)
        if ts:
            day_set.add(int(ts // 86400))

    sorted_days = sorted(day_set, reverse=True)
    today = int(time.time() // 86400)

    current_streak = 0
    for i, day in enumerate(sorted_days):
        expected = today - i
        if day == expected:
            current_streak += 1
        elif day == expected - 1:
            # Allow one day gap (yesterday was studied)
            current_streak += 1
        else:
            break

    # Max streak
    max_streak = 0
    streak = 0
    prev_day = None
    for day in sorted(day_set):
        if prev_day is not None and day == prev_day + 1:
            streak += 1
        else:
            streak = 1
        max_streak = max(max_streak, streak)
        prev_day = day

    return {
        "current_streak_days": current_streak,
        "max_streak_days": max(max_streak, current_streak),
        "total_study_days": len(day_set),
    }


def _generate_recommendations(
    gaps: list[dict],
    module_breakdown: list[dict],
    error_dist: dict[str, int],
    accuracy: dict[str, Any],
) -> list[str]:
    """Generate actionable study recommendations."""
    recs: list[str] = []

    if accuracy.get("accuracy_pct", 0) < 60:
        recs.append("🎯 Overall accuracy is below 60%. Consider reviewing foundational concepts before attempting new material.")

    if accuracy.get("recent_accuracy_pct", 0) < accuracy.get("accuracy_pct", 0) - 10:
        recs.append("📉 Recent accuracy has dropped significantly. Take a review session to consolidate earlier material.")

    if gaps:
        weakest = gaps[0]
        recs.append(f"🔍 Focus on **{weakest['name']}** (mastery {weakest['mastery_pct']}%) — this is your weakest knowledge point.")

    if module_breakdown:
        weakest_mod = module_breakdown[0]
        if weakest_mod["avg_mastery_pct"] < 50:
            recs.append(f"📖 Module **{weakest_mod['name']}** needs attention (avg mastery {weakest_mod['avg_mastery_pct']}%).")

    top_error = max(error_dist.items(), key=lambda kv: kv[1]) if error_dist else None
    if top_error:
        error_type = top_error[0]
        _ERROR_TIPS = {
            "structural": "🧱 You have many structural errors — revisit the underlying knowledge framework.",
            "deviation": "🔄 Understanding deviations detected — try explaining concepts in your own words (Feynman technique).",
            "application": "⚙️ Application errors suggest you understand theory but struggle with practice — try more exercises.",
            "metacognitive": "🧠 Metacognitive errors found — slow down and double-check your reasoning process.",
        }
        recs.append(_ERROR_TIPS.get(error_type, f"⚠️ Most common error type: {error_type}."))

    if not recs:
        recs.append("✅ Great progress! Keep up with your spaced-repetition reviews to maintain mastery.")

    return recs


def compute_analytics(progress_data: dict[str, Any]) -> dict[str, Any]:
    """Main analytics computation — takes raw progress dict, returns analytics."""
    attempts = progress_data.get("quiz_attempts", [])
    modules = progress_data.get("modules", [])
    mastery_levels = progress_data.get("mastery_levels", {})
    error_records = progress_data.get("error_records", [])
    rep_states = progress_data.get("repetition_states", {})
    book_id = progress_data.get("book_id", "unknown")

    accuracy = _compute_accuracy(attempts)
    module_breakdown = _compute_module_breakdown(modules, attempts, mastery_levels)
    gaps = _detect_knowledge_gaps(modules, mastery_levels)
    error_dist = _error_type_distribution(error_records)
    forecast = _review_forecast(rep_states)
    streak = _study_streak(attempts)
    recommendations = _generate_recommendations(gaps, module_breakdown, error_dist, accuracy)

    total_kps = sum(len(m.get("knowledge_points", [])) for m in modules)
    mastered_kps = sum(1 for kp_list in modules for kp in kp_list.get("knowledge_points", []) if mastery_levels.get(kp["id"], 0) >= 0.7)

    return {
        "book_id": book_id,
        "summary": {
            "total_knowledge_points": total_kps,
            "mastered_knowledge_points": mastered_kps,
            "mastery_completion_pct": round(mastered_kps / total_kps * 100, 1) if total_kps else 0.0,
            "total_attempts": accuracy["total"],
            "active_errors": sum(1 for r in error_records if r.get("status") in ("active", "retrying")),
        },
        "accuracy": accuracy,
        "module_breakdown": module_breakdown,
        "knowledge_gaps": gaps,
        "error_distribution": error_dist,
        "review_forecast": forecast,
        "study_streak": streak,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Tool class (registered in BUILTIN_TOOL_TYPES)
# ---------------------------------------------------------------------------

class LearningAnalyticsTool(BaseTool):
    """Compute aggregated learning analytics from mastery path data."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="learning_analytics",
            description=(
                "Compute comprehensive learning analytics for a mastery path: "
                "accuracy trends, knowledge gap detection, module-level breakdown, "
                "error-type distribution, study streak, spaced-repetition forecast, "
                "and personalised study recommendations. Call with a mastery_path_id "
                "to analyse that path, or omit to get a cross-path overview."
            ),
            parameters=[
                ToolParameter(
                    name="mastery_path_id",
                    type="string",
                    description=(
                        "The mastery path to analyse. Omit or pass empty to get "
                        "an overview of ALL paths."
                    ),
                    required=False,
                    default="",
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        path_id = str(kwargs.get("mastery_path_id") or "").strip()

        from herpeakgem.learning.service import LearningService
        from herpeakgem.learning.storage import LearningStore

        service = LearningService(LearningStore())

        if path_id:
            # Single-path analytics
            progress = service.get_or_create(path_id)
            data = progress.model_dump(mode="json")
            analytics = compute_analytics(data)
            return ToolResult(
                content=json.dumps(analytics, ensure_ascii=False, indent=2),
                metadata={"learning_analytics": analytics},
            )
        else:
            # Cross-path overview
            store = LearningStore()
            all_ids = store.list_all()
            if not all_ids:
                return ToolResult(
                    content="No mastery paths found. Start a mastery path first to see analytics.",
                    metadata={"learning_analytics": {"paths": [], "count": 0}},
                )

            path_summaries = []
            total_attempts = 0
            total_correct = 0
            total_kps = 0
            total_mastered = 0

            for bid in all_ids:
                progress = store.load(bid)
                if progress is None:
                    continue
                data = progress.model_dump(mode="json")
                analytics = compute_analytics(data)
                path_summaries.append({
                    "book_id": bid,
                    "total_kps": analytics["summary"]["total_knowledge_points"],
                    "mastered_kps": analytics["summary"]["mastered_knowledge_points"],
                    "mastery_completion_pct": analytics["summary"]["mastery_completion_pct"],
                    "total_attempts": analytics["accuracy"]["total"],
                    "accuracy_pct": analytics["accuracy"]["accuracy_pct"],
                    "study_streak_days": analytics["study_streak"]["current_streak_days"],
                })
                total_attempts += analytics["accuracy"]["total"]
                total_correct += analytics["accuracy"]["correct"]
                total_kps += analytics["summary"]["total_knowledge_points"]
                total_mastered += analytics["summary"]["mastered_knowledge_points"]

            overview = {
                "paths_count": len(path_summaries),
                "overall_accuracy_pct": round(total_correct / total_attempts * 100, 1) if total_attempts else 0.0,
                "overall_mastery_pct": round(total_mastered / total_kps * 100, 1) if total_kps else 0.0,
                "total_attempts": total_attempts,
                "total_knowledge_points": total_kps,
                "total_mastered": total_mastered,
                "paths": path_summaries,
            }
            return ToolResult(
                content=json.dumps(overview, ensure_ascii=False, indent=2),
                metadata={"learning_analytics": overview},
            )


__all__ = ["LearningAnalyticsTool", "compute_analytics"]
