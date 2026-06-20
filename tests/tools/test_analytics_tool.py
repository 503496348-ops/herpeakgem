"""Tests for the Learning Analytics Engine tool."""

from __future__ import annotations

import time
import pytest

from herpeakgem.tools.analytics_tool import (
    LearningAnalyticsTool,
    compute_analytics,
    _compute_accuracy,
    _detect_knowledge_gaps,
    _error_type_distribution,
    _generate_recommendations,
    _study_streak,
)


class TestComputeAccuracy:
    def test_empty(self):
        result = _compute_accuracy([])
        assert result["total"] == 0
        assert result["accuracy_pct"] == 0.0

    def test_basic(self):
        now = time.time()
        attempts = [
            {"is_correct": True, "timestamp": now},
            {"is_correct": False, "timestamp": now},
            {"is_correct": True, "timestamp": now},
        ]
        result = _compute_accuracy(attempts)
        assert result["total"] == 3
        assert result["correct"] == 2
        assert abs(result["accuracy_pct"] - 66.7) < 0.1

    def test_recent_window(self):
        now = time.time()
        old_ts = now - 10 * 86400  # 10 days ago
        attempts = [
            {"is_correct": True, "timestamp": old_ts},
            {"is_correct": True, "timestamp": now},
            {"is_correct": False, "timestamp": now},
        ]
        result = _compute_accuracy(attempts)
        assert result["total"] == 3
        assert result["recent_total"] == 2
        assert result["recent_accuracy_pct"] == 50.0


class TestDetectKnowledgeGaps:
    def test_returns_weakest(self):
        modules = [
            {
                "id": "m0",
                "name": "Module A",
                "knowledge_points": [
                    {"id": "kp1", "name": "Concept 1"},
                    {"id": "kp2", "name": "Concept 2"},
                    {"id": "kp3", "name": "Concept 3"},
                ],
            }
        ]
        mastery = {"kp1": 0.9, "kp2": 0.2, "kp3": 0.5}
        gaps = _detect_knowledge_gaps(modules, mastery, limit=2)
        assert len(gaps) == 2
        assert gaps[0]["knowledge_point_id"] == "kp2"
        assert gaps[0]["mastery_pct"] == 20.0

    def test_empty(self):
        gaps = _detect_knowledge_gaps([], {})
        assert gaps == []


class TestErrorDistribution:
    def test_counts(self):
        records = [
            {"status": "active", "error_type": "structural"},
            {"status": "active", "error_type": "deviation"},
            {"status": "active", "error_type": "structural"},
            {"status": "graduated", "error_type": "application"},
        ]
        dist = _error_type_distribution(records)
        assert dist["structural"] == 2
        assert dist["deviation"] == 1
        assert "application" not in dist  # graduated, not active


class TestStudyStreak:
    def test_empty(self):
        result = _study_streak([])
        assert result["current_streak_days"] == 0
        assert result["total_study_days"] == 0

    def test_single_day(self):
        now = time.time()
        result = _study_streak([{"timestamp": now}])
        assert result["total_study_days"] == 1
        assert result["current_streak_days"] >= 1


class TestRecommendations:
    def test_low_accuracy(self):
        accuracy = {"accuracy_pct": 40, "recent_accuracy_pct": 40}
        recs = _generate_recommendations([], [], {}, accuracy)
        assert any("60%" in r for r in recs)

    def test_good_performance(self):
        accuracy = {"accuracy_pct": 95, "recent_accuracy_pct": 95}
        recs = _generate_recommendations([], [], {}, accuracy)
        assert any("Great progress" in r for r in recs)


class TestComputeAnalytics:
    def test_full_pipeline(self):
        now = time.time()
        progress = {
            "book_id": "test-book",
            "quiz_attempts": [
                {"is_correct": True, "timestamp": now, "knowledge_point_id": "kp1"},
                {"is_correct": False, "timestamp": now, "knowledge_point_id": "kp2"},
            ],
            "modules": [
                {
                    "id": "m0",
                    "name": "Module A",
                    "knowledge_points": [
                        {"id": "kp1", "name": "Concept 1"},
                        {"id": "kp2", "name": "Concept 2"},
                    ],
                }
            ],
            "mastery_levels": {"kp1": 0.9, "kp2": 0.3},
            "error_records": [],
            "repetition_states": {},
        }
        result = compute_analytics(progress)
        assert result["book_id"] == "test-book"
        assert result["summary"]["total_knowledge_points"] == 2
        assert result["accuracy"]["total"] == 2
        assert len(result["module_breakdown"]) == 1
        assert len(result["knowledge_gaps"]) == 2
        assert len(result["recommendations"]) > 0


class TestLearningAnalyticsTool:
    @pytest.mark.asyncio
    async def test_definition(self):
        tool = LearningAnalyticsTool()
        defn = tool.get_definition()
        assert defn.name == "learning_analytics"
        assert "analytics" in defn.description.lower()
        assert len(defn.parameters) >= 1
