"""Tests for the Adaptive Flashcard Generator tool."""

from __future__ import annotations

import time

import pytest

from herpeakgem.tools.flashcard_tool import (
    FlashcardTool,
    _deck_schema,
    _flashcard_schema,
    _get_due_cards,
    _hours_until_next,
    _sm2_review,
)


class TestFlashcardSchema:
    def test_blank_template(self):
        card = _flashcard_schema()
        assert card["front"] == ""
        assert card["back"] == ""
        assert card["ease_factor"] == 2.5
        assert card["repetitions"] == 0
        assert card["lapses"] == 0

    def test_deck_template(self):
        deck = _deck_schema()
        assert deck["cards"] == []
        assert deck["card_count"] == 0


class TestSM2Review:
    def _make_card(self, **overrides) -> dict:
        card = _flashcard_schema()
        card["id"] = "test"
        card.update(overrides)
        return card

    def test_perfect_recall(self):
        card = self._make_card()
        result = _sm2_review(card, 5)
        assert result["repetitions"] == 1
        assert result["interval_days"] == 1
        assert result["ease_factor"] > 2.5  # Perfect recall increases ease
        assert result["difficulty"] == 1  # easy

    def test_good_recall(self):
        card = self._make_card()
        result = _sm2_review(card, 4)
        assert result["repetitions"] == 1
        assert result["interval_days"] == 1
        assert result["difficulty"] == 1  # easy

    def test_barely_passing(self):
        card = self._make_card()
        result = _sm2_review(card, 3)
        assert result["repetitions"] == 1
        assert result["interval_days"] == 1
        assert result["difficulty"] == 2  # medium

    def test_failure_resets(self):
        card = self._make_card(repetitions=3, interval_days=14)
        result = _sm2_review(card, 1)
        assert result["repetitions"] == 0
        assert result["interval_days"] == 1
        assert result["lapses"] == 1
        assert result["difficulty"] >= 2

    def test_consecutive_success_increases_interval(self):
        card = self._make_card()
        _sm2_review(card, 4)
        assert card["interval_days"] == 1
        _sm2_review(card, 4)
        assert card["interval_days"] == 6
        _sm2_review(card, 4)
        assert card["interval_days"] > 6

    def test_ease_factor_minimum(self):
        card = self._make_card(ease_factor=1.3)
        _sm2_review(card, 3)
        assert card["ease_factor"] >= 1.3

    def test_next_review_set(self):
        card = self._make_card()
        before = time.time()
        _sm2_review(card, 4)
        assert card["next_review"] > before
        assert card["last_review"] >= before


class TestGetDueCards:
    def test_new_cards_are_due(self):
        cards = [_flashcard_schema() for _ in range(3)]
        for i, c in enumerate(cards):
            c["id"] = f"card_{i}"
            c["front"] = f"Q{i}"
        due = _get_due_cards(cards)
        assert len(due) == 3

    def test_future_cards_not_due(self):
        cards = [_flashcard_schema() for _ in range(3)]
        future = time.time() + 86400 * 30
        for i, c in enumerate(cards):
            c["id"] = f"card_{i}"
            c["next_review"] = future
        due = _get_due_cards(cards)
        assert len(due) == 0

    def test_limit(self):
        cards = [_flashcard_schema() for _ in range(20)]
        for i, c in enumerate(cards):
            c["id"] = f"card_{i}"
        due = _get_due_cards(cards, limit=5)
        assert len(due) == 5


class TestHoursUntilNext:
    def test_empty(self):
        assert _hours_until_next([]) == 0.0

    def test_all_past(self):
        cards = [{"next_review": time.time() - 100}]
        assert _hours_until_next(cards) == 0.0

    def test_future(self):
        cards = [{"next_review": time.time() + 3600}]
        result = _hours_until_next(cards)
        assert 0.9 < result < 1.1


class TestFlashcardTool:
    def test_definition(self):
        tool = FlashcardTool()
        defn = tool.get_definition()
        assert defn.name == "flashcard"
        assert "flashcard" in defn.description.lower()
        # Should have action parameter
        action_param = next(p for p in defn.parameters if p.name == "action")
        assert action_param.enum == ["generate", "review", "stats", "export"]

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        tool = FlashcardTool()
        result = await tool.execute(action="invalid")
        assert not result.success
        assert "Unknown action" in result.content

    @pytest.mark.asyncio
    async def test_generate_no_text(self):
        tool = FlashcardTool()
        result = await tool.execute(action="generate")
        assert not result.success
        assert "source_text is required" in result.content

    @pytest.mark.asyncio
    async def test_review_no_deck(self):
        tool = FlashcardTool()
        result = await tool.execute(action="review")
        assert not result.success
        assert "deck_id is required" in result.content

    @pytest.mark.asyncio
    async def test_stats_no_deck_lists_all(self):
        tool = FlashcardTool()
        result = await tool.execute(action="stats")
        assert result.success
        assert "list_decks" in result.content

    @pytest.mark.asyncio
    async def test_export_no_deck(self):
        tool = FlashcardTool()
        result = await tool.execute(action="export")
        assert not result.success
        assert "deck_id is required" in result.content
