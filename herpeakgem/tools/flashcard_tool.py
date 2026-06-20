"""Adaptive Flashcard Generator — auto-generate and manage spaced-repetition flashcards.

Anki-style flashcard generation is one of the most requested features in
education AI.  HerPeakGem has spaced-repetition scheduling (``learning.scheduler``)
and quiz generation, but no dedicated tool to:

  • Auto-generate flashcard decks from study materials (text, KB sources)
  • Manage flashcard decks with CRUD operations
  • Track flashcard review performance with SM-2 intervals
  • Export decks in standard formats (JSON, Anki-compatible CSV)

This tool provides a complete flashcard lifecycle: generate → review → track.

Brand: AtomCollide-智械工坊
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from herpeakgem.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Flashcard data model (JSON-serialisable, stored on disk)
# ---------------------------------------------------------------------------

def _flashcard_schema() -> dict[str, Any]:
    """Return a blank flashcard template."""
    return {
        "id": "",
        "front": "",       # Question / prompt side
        "back": "",        # Answer side
        "tags": [],        # Topic tags for filtering
        "difficulty": 0,   # 0=new, 1=easy, 2=medium, 3=hard
        "interval_days": 0,
        "ease_factor": 2.5,  # SM-2 ease factor
        "repetitions": 0,
        "lapses": 0,       # Times forgotten after being learned
        "next_review": 0.0,  # Unix timestamp
        "last_review": 0.0,
        "created_at": 0.0,
        "source": "",      # Where the card was generated from
    }


def _deck_schema() -> dict[str, Any]:
    """Return a blank deck template."""
    return {
        "id": "",
        "name": "",
        "description": "",
        "cards": [],
        "created_at": 0.0,
        "updated_at": 0.0,
        "card_count": 0,
        "tags": [],
    }


# ---------------------------------------------------------------------------
# Deck storage (file-based, under workspace)
# ---------------------------------------------------------------------------

def _get_decks_dir() -> Path:
    """Resolve the flashcard decks directory under the workspace."""
    from herpeakgem.services.path_service import get_path_service
    decks_dir = get_path_service().get_workspace_dir() / "flashcards"
    decks_dir.mkdir(parents=True, exist_ok=True)
    return decks_dir


def _save_deck(deck: dict[str, Any]) -> None:
    decks_dir = _get_decks_dir()
    path = decks_dir / f"{deck['id']}.json"
    deck["updated_at"] = time.time()
    path.write_text(json.dumps(deck, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_deck(deck_id: str) -> dict[str, Any] | None:
    path = _get_decks_dir() / f"{deck_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _list_decks() -> list[dict[str, Any]]:
    decks_dir = _get_decks_dir()
    decks = []
    for f in sorted(decks_dir.glob("*.json")):
        try:
            deck = json.loads(f.read_text(encoding="utf-8"))
            decks.append({
                "id": deck["id"],
                "name": deck["name"],
                "description": deck.get("description", ""),
                "card_count": len(deck.get("cards", [])),
                "tags": deck.get("tags", []),
                "updated_at": deck.get("updated_at", 0),
            })
        except Exception:
            logger.warning("Skipping corrupt deck file: %s", f)
    return decks


# ---------------------------------------------------------------------------
# SM-2 spaced repetition engine (standalone, mirrors learning/scheduler.py logic)
# ---------------------------------------------------------------------------

def _sm2_review(card: dict[str, Any], quality: int) -> dict[str, Any]:
    """Apply SM-2 algorithm to a flashcard after review.

    Args:
        card: The flashcard dict.
        quality: Review quality 0-5 (0=complete blackout, 5=perfect recall).

    Returns:
        Updated card dict.
    """
    now = time.time()
    card["last_review"] = now

    if quality < 3:
        # Failed — reset interval, increment lapses
        card["lapses"] += 1
        card["repetitions"] = 0
        card["interval_days"] = 1
        card["difficulty"] = max(card.get("difficulty", 2), 2)
    else:
        # Passed
        if card["repetitions"] == 0:
            card["interval_days"] = 1
        elif card["repetitions"] == 1:
            card["interval_days"] = 6
        else:
            card["interval_days"] = int(card["interval_days"] * card["ease_factor"])
        card["repetitions"] += 1

        # Update ease factor
        ef = card["ease_factor"] + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        card["ease_factor"] = max(1.3, ef)

        # Update difficulty label
        if quality >= 4:
            card["difficulty"] = 1  # easy
        elif quality == 3:
            card["difficulty"] = 2  # medium

    card["next_review"] = now + card["interval_days"] * 86400
    return card


def _get_due_cards(cards: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    """Return cards due for review, sorted by urgency."""
    now = time.time()
    due = [c for c in cards if c.get("next_review", 0) <= now or c.get("next_review", 0) == 0]
    due.sort(key=lambda c: (c.get("next_review", 0), -c.get("lapses", 0)))
    return due[:limit]


# ---------------------------------------------------------------------------
# LLM-powered flashcard generation
# ---------------------------------------------------------------------------

_GENERATE_SYSTEM_PROMPT = """\
You are an expert educational content designer. Given source material, generate \
high-quality flashcards for spaced-repetition study.

Requirements:
- Each flashcard has a clear, concise FRONT (question/prompt) and BACK (answer).
- Questions should test understanding, not just recall where possible.
- Vary question types: definition, application, comparison, example, fill-in-blank.
- Keep answers focused and self-contained (no "see above").
- Tag each card with 1-3 topic keywords.
- Estimate difficulty: 1=easy, 2=medium, 3=hard.

Return valid JSON:
{
  "flashcards": [
    {
      "front": "What is the time complexity of binary search?",
      "back": "O(log n) — each step halves the search space.",
      "tags": ["algorithms", "search", "complexity"],
      "difficulty": 1
    }
  ]
}"""


async def _generate_cards_with_llm(
    source_text: str,
    num_cards: int = 10,
    focus_tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Use LLM to generate flashcards from source text."""
    from herpeakgem.services.config import get_agent_params
    from herpeakgem.services.llm import complete as llm_complete
    from herpeakgem.services.llm.config import get_llm_config
    from herpeakgem.utils.json_parser import parse_json_response

    llm_cfg = get_llm_config()
    agent_params = get_agent_params("question")

    user_prompt = f"Generate {num_cards} flashcards from this material:\n\n{source_text[:12000]}"
    if focus_tags:
        user_prompt += f"\n\nFocus on these topics: {', '.join(focus_tags)}"

    result_text = await llm_complete(
        prompt=user_prompt,
        system_prompt=_GENERATE_SYSTEM_PROMPT,
        model=llm_cfg.model,
        api_key=llm_cfg.api_key,
        base_url=llm_cfg.base_url,
        temperature=agent_params.get("temperature", 0.7),
        max_tokens=agent_params.get("max_tokens", 4096),
    )

    parsed = parse_json_response(result_text, fallback={})
    raw_cards = parsed.get("flashcards", [])

    now = time.time()
    cards = []
    for raw in raw_cards:
        card = _flashcard_schema()
        card["id"] = uuid.uuid4().hex[:12]
        card["front"] = str(raw.get("front", "")).strip()
        card["back"] = str(raw.get("back", "")).strip()
        card["tags"] = [str(t) for t in (raw.get("tags") or [])][:5]
        card["difficulty"] = int(raw.get("difficulty", 2))
        card["difficulty"] = max(1, min(3, card["difficulty"]))
        card["created_at"] = now
        card["next_review"] = now  # Due immediately for first review
        if card["front"] and card["back"]:
            cards.append(card)

    return cards


# ---------------------------------------------------------------------------
# Flashcard tool actions
# ---------------------------------------------------------------------------

async def _action_generate(kwargs: dict[str, Any]) -> ToolResult:
    """Generate flashcards from source text and save to a deck."""
    source = str(kwargs.get("source_text") or "").strip()
    if not source:
        return ToolResult(content="source_text is required for generation.", success=False)

    deck_name = str(kwargs.get("deck_name") or "Untitled Deck").strip()
    num_cards = max(1, min(30, int(kwargs.get("num_cards") or 10)))
    focus_tags = [str(t) for t in (kwargs.get("focus_tags") or []) if str(t).strip()]

    cards = await _generate_cards_with_llm(source, num_cards, focus_tags)
    if not cards:
        return ToolResult(content="No flashcards could be generated from the source text.", success=False)

    # Create or append to deck
    deck_id = str(kwargs.get("deck_id") or "").strip()
    if deck_id:
        deck = _load_deck(deck_id)
        if deck is None:
            return ToolResult(content=f"Deck '{deck_id}' not found.", success=False)
        deck["cards"].extend(cards)
    else:
        deck = _deck_schema()
        deck["id"] = uuid.uuid4().hex[:12]
        deck["name"] = deck_name
        deck["description"] = f"Auto-generated from source text ({len(cards)} cards)"
        deck["cards"] = cards
        deck["created_at"] = time.time()
        deck["tags"] = focus_tags

    deck["card_count"] = len(deck["cards"])
    _save_deck(deck)

    return ToolResult(
        content=json.dumps({
            "action": "generate",
            "deck_id": deck["id"],
            "deck_name": deck["name"],
            "cards_generated": len(cards),
            "total_cards": len(deck["cards"]),
            "sample": [{"front": c["front"], "back": c["back"][:80]} for c in cards[:3]],
        }, ensure_ascii=False, indent=2),
        metadata={"flashcard_deck": {"id": deck["id"], "card_count": len(deck["cards"])}},
    )


def _action_review(kwargs: dict[str, Any]) -> ToolResult:
    """Get due cards for review or submit a review grade."""
    deck_id = str(kwargs.get("deck_id") or "").strip()
    if not deck_id:
        return ToolResult(content="deck_id is required.", success=False)

    deck = _load_deck(deck_id)
    if deck is None:
        return ToolResult(content=f"Deck '{deck_id}' not found.", success=False)

    # If quality is provided, record the review
    quality = kwargs.get("quality")
    card_id = str(kwargs.get("card_id") or "").strip()

    if quality is not None and card_id:
        quality = int(quality)
        quality = max(0, min(5, quality))
        found = False
        for card in deck["cards"]:
            if card["id"] == card_id:
                card = _sm2_review(card, quality)
                found = True
                break
        if not found:
            return ToolResult(content=f"Card '{card_id}' not found in deck.", success=False)
        _save_deck(deck)
        return ToolResult(
            content=json.dumps({
                "action": "review_recorded",
                "card_id": card_id,
                "quality": quality,
                "next_review_days": deck["cards"][[c["id"] for c in deck["cards"]].index(card_id)]["interval_days"],
                "due_cards_remaining": len(_get_due_cards(deck["cards"])),
            }, ensure_ascii=False, indent=2),
            metadata={"flashcard_review": {"card_id": card_id, "quality": quality}},
        )

    # Otherwise, return due cards
    limit = max(1, min(20, int(kwargs.get("limit") or 10)))
    due = _get_due_cards(deck["cards"], limit)
    if not due:
        return ToolResult(
            content=json.dumps({
                "action": "no_due_cards",
                "message": "No cards are due for review right now. Great job!",
                "next_review_in_hours": _hours_until_next(deck["cards"]),
            }, ensure_ascii=False, indent=2),
        )

    return ToolResult(
        content=json.dumps({
            "action": "review_session",
            "deck_id": deck_id,
            "deck_name": deck["name"],
            "due_count": len(due),
            "cards": [
                {
                    "card_id": c["id"],
                    "front": c["front"],
                    "tags": c["tags"],
                    "difficulty": c["difficulty"],
                    "repetitions": c["repetitions"],
                }
                for c in due
            ],
            "instruction": "Present each card's FRONT to the learner. When they answer, submit their answer with quality 0-5 (0=blackout, 5=perfect).",
        }, ensure_ascii=False, indent=2),
        metadata={"flashcard_session": {"deck_id": deck_id, "due_count": len(due)}},
    )


def _hours_until_next(cards: list[dict[str, Any]]) -> float:
    """Hours until the next card becomes due."""
    now = time.time()
    future = [c["next_review"] for c in cards if c.get("next_review", 0) > now]
    if not future:
        return 0.0
    return round((min(future) - now) / 3600, 1)


def _action_stats(kwargs: dict[str, Any]) -> ToolResult:
    """Get deck statistics."""
    deck_id = str(kwargs.get("deck_id") or "").strip()
    if not deck_id:
        # List all decks
        decks = _list_decks()
        return ToolResult(
            content=json.dumps({"action": "list_decks", "decks": decks}, ensure_ascii=False, indent=2),
            metadata={"flashcard_decks": decks},
        )

    deck = _load_deck(deck_id)
    if deck is None:
        return ToolResult(content=f"Deck '{deck_id}' not found.", success=False)

    cards = deck.get("cards", [])
    now = time.time()
    new = sum(1 for c in cards if c.get("repetitions", 0) == 0)
    learning = sum(1 for c in cards if 0 < c.get("repetitions", 0) < 3)
    mature = sum(1 for c in cards if c.get("repetitions", 0) >= 3)
    due = sum(1 for c in cards if c.get("next_review", 0) <= now or c.get("next_review", 0) == 0)
    total_lapses = sum(c.get("lapses", 0) for c in cards)
    avg_ease = sum(c.get("ease_factor", 2.5) for c in cards) / len(cards) if cards else 2.5

    stats = {
        "action": "deck_stats",
        "deck_id": deck_id,
        "deck_name": deck["name"],
        "total_cards": len(cards),
        "new": new,
        "learning": learning,
        "mature": mature,
        "due_now": due,
        "total_lapses": total_lapses,
        "avg_ease_factor": round(avg_ease, 2),
        "difficulty_distribution": {
            "easy": sum(1 for c in cards if c.get("difficulty") == 1),
            "medium": sum(1 for c in cards if c.get("difficulty") == 2),
            "hard": sum(1 for c in cards if c.get("difficulty") == 3),
        },
    }
    return ToolResult(
        content=json.dumps(stats, ensure_ascii=False, indent=2),
        metadata={"flashcard_stats": stats},
    )


def _action_export(kwargs: dict[str, Any]) -> ToolResult:
    """Export a deck as JSON or Anki-compatible CSV."""
    deck_id = str(kwargs.get("deck_id") or "").strip()
    fmt = str(kwargs.get("format") or "json").strip().lower()
    if not deck_id:
        return ToolResult(content="deck_id is required.", success=False)

    deck = _load_deck(deck_id)
    if deck is None:
        return ToolResult(content=f"Deck '{deck_id}' not found.", success=False)

    cards = deck.get("cards", [])

    if fmt == "csv":
        # Anki-compatible CSV: front;back;tags
        lines = ["#separator:Semicolon", "#html:false", "#tags column:3"]
        for c in cards:
            tags = " ".join(c.get("tags", []))
            front = c["front"].replace(";", ",").replace("\n", " ")
            back = c["back"].replace(";", ",").replace("\n", " ")
            lines.append(f"{front};{back};{tags}")
        content = "\n".join(lines)
        return ToolResult(
            content=f"Exported {len(cards)} cards in Anki CSV format:\n\n```\n{content[:3000]}\n```",
            metadata={"flashcard_export": {"format": "csv", "card_count": len(cards), "content": content}},
        )
    else:
        # JSON export
        export = {
            "deck_name": deck["name"],
            "description": deck.get("description", ""),
            "export_time": time.time(),
            "card_count": len(cards),
            "cards": [{"front": c["front"], "back": c["back"], "tags": c["tags"]} for c in cards],
        }
        return ToolResult(
            content=json.dumps(export, ensure_ascii=False, indent=2),
            metadata={"flashcard_export": {"format": "json", "card_count": len(cards)}},
        )


# ---------------------------------------------------------------------------
# Tool class (registered in BUILTIN_TOOL_TYPES)
# ---------------------------------------------------------------------------

class FlashcardTool(BaseTool):
    """Generate, review, and manage adaptive flashcard decks with SM-2 spaced repetition."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="flashcard",
            description=(
                "Generate and manage flashcard decks with SM-2 spaced repetition. "
                "Actions: 'generate' (create cards from source text via LLM), "
                "'review' (get due cards or record a review grade), "
                "'stats' (deck statistics or list all decks), "
                "'export' (export deck as JSON or Anki CSV)."
            ),
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="Action to perform: generate, review, stats, or export.",
                    enum=["generate", "review", "stats", "export"],
                ),
                ToolParameter(
                    name="source_text",
                    type="string",
                    description="Source material for flashcard generation (action=generate).",
                    required=False,
                ),
                ToolParameter(
                    name="deck_name",
                    type="string",
                    description="Name for a new deck (action=generate, optional).",
                    required=False,
                ),
                ToolParameter(
                    name="deck_id",
                    type="string",
                    description="Deck ID for review/stats/export/append.",
                    required=False,
                ),
                ToolParameter(
                    name="num_cards",
                    type="integer",
                    description="Number of cards to generate (default 10, max 30).",
                    required=False,
                ),
                ToolParameter(
                    name="focus_tags",
                    type="array",
                    description="Topic tags to focus generation on.",
                    required=False,
                    items={"type": "string"},
                ),
                ToolParameter(
                    name="card_id",
                    type="string",
                    description="Card ID for recording a review (action=review).",
                    required=False,
                ),
                ToolParameter(
                    name="quality",
                    type="integer",
                    description="Review quality 0-5 (0=blackout, 5=perfect) for action=review.",
                    required=False,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Max cards to return in review session (default 10).",
                    required=False,
                ),
                ToolParameter(
                    name="format",
                    type="string",
                    description="Export format: 'json' or 'csv' (Anki-compatible). Default 'json'.",
                    required=False,
                    enum=["json", "csv"],
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = str(kwargs.get("action") or "").strip().lower()

        if action == "generate":
            return await _action_generate(kwargs)
        elif action == "review":
            return _action_review(kwargs)
        elif action == "stats":
            return _action_stats(kwargs)
        elif action == "export":
            return _action_export(kwargs)
        else:
            return ToolResult(
                content=f"Unknown action '{action}'. Valid actions: generate, review, stats, export.",
                success=False,
            )


__all__ = ["FlashcardTool"]
