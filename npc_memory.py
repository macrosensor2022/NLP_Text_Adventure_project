from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from models import (
    ConversationTurn,
    MAX_RECENT_TURNS,
    MEMORY_BUDGET_RATIO,
    NPCConversationMemory,
)

DEFAULT_MEMORY_DIR = "memory/npcs"


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _compact_text(text: str) -> str:
    return " ".join(text.strip().split())


def _format_turn(turn: ConversationTurn) -> str:
    return f"{turn.speaker}: {turn.text}"


class NPCMemoryRepository:
    def __init__(self, base_dir: str = DEFAULT_MEMORY_DIR):
        self.base_path = Path(base_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _memory_path(self, npc_id: str) -> Path:
        safe_id = npc_id.strip().lower().replace(" ", "_")
        return self.base_path / f"{safe_id}.json"

    def load(self, npc_id: str, npc_name: str) -> NPCConversationMemory:
        path = self._memory_path(npc_id)
        if not path.exists():
            memory = NPCConversationMemory(npc_id=npc_id, npc_name=npc_name)
            self.save(memory)
            return memory

        raw = json.loads(path.read_text())
        memory = NPCConversationMemory.model_validate(raw)

        if memory.npc_name != npc_name:
            memory.npc_name = npc_name
            self.save(memory)

        return memory

    def save(self, memory: NPCConversationMemory) -> None:
        path = self._memory_path(memory.npc_id)
        path.write_text(memory.model_dump_json(indent=2))

    def append_turn(
        self,
        memory: NPCConversationMemory,
        speaker: str,
        text: str,
        *,
        game_turn: int | None = None,
    ) -> None:
        clean_text = _compact_text(text)
        if not clean_text:
            return

        next_index = memory.turns[-1].turn_index + 1 if memory.turns else 1
        memory.turns.append(
            ConversationTurn(
                speaker=speaker,
                text=clean_text,
                turn_index=next_index,
                game_turn=game_turn,
            )
        )
        self.save(memory)

    def append_exchange(
        self,
        memory: NPCConversationMemory,
        player_text: str,
        npc_name: str,
        npc_text: str,
        *,
        game_turn: int | None = None,
    ) -> None:
        self.append_turn(memory, "Player", player_text, game_turn=game_turn)
        self.append_turn(memory, npc_name, npc_text, game_turn=game_turn)

    def build_prompt_context(
        self,
        memory: NPCConversationMemory,
        *,
        model_context_tokens: int = 2048,
        budget_ratio: float = MEMORY_BUDGET_RATIO,
        recent_turn_limit: int = MAX_RECENT_TURNS,
    ) -> dict[str, Any]:
        budget_tokens = max(128, int(model_context_tokens * budget_ratio))
        summary_updated = self._summarize_if_needed(
            memory,
            budget_tokens=budget_tokens,
            recent_turn_limit=recent_turn_limit,
        )
        if summary_updated:
            self.save(memory)

        recent_turns = [t for t in memory.turns if t.turn_index > memory.summarized_until_turn]
        recent_turns = recent_turns[-recent_turn_limit:]

        summary = _compact_text(memory.summary)
        summary = self._fit_summary_to_budget(summary, budget_tokens)
        while recent_turns and self._section_tokens(summary, recent_turns) > budget_tokens:
            recent_turns.pop(0)

        return {
            "summary": summary,
            "recent_turns": [_format_turn(turn) for turn in recent_turns],
            "budget_tokens": budget_tokens,
            "used_tokens": self._section_tokens(summary, recent_turns),
        }

    def _fit_summary_to_budget(self, summary: str, budget_tokens: int) -> str:
        if not summary:
            return summary

        # Reserve some room for section labels and at least one short recent turn.
        summary_budget = max(48, budget_tokens - 32)
        if _estimate_tokens(summary) <= summary_budget:
            return summary

        max_chars = max(80, summary_budget * 4)
        clipped = summary[: max_chars - 3].rstrip() + "..."
        return clipped

    def _section_tokens(self, summary: str, turns: list[ConversationTurn]) -> int:
        turns_blob = "\n".join(_format_turn(t) for t in turns)
        text = f"Summary: {summary}\nRecent:\n{turns_blob}".strip()
        return _estimate_tokens(text)

    def _summarize_if_needed(
        self,
        memory: NPCConversationMemory,
        *,
        budget_tokens: int,
        recent_turn_limit: int,
    ) -> bool:
        if self._section_tokens(memory.summary, memory.turns[-recent_turn_limit:]) <= budget_tokens:
            return False

        older_turns = memory.turns[:-recent_turn_limit] if len(memory.turns) > recent_turn_limit else []
        pending = [t for t in older_turns if t.turn_index > memory.summarized_until_turn]
        if not pending:
            return False

        condensed = self._deterministic_summary(pending)
        if memory.summary:
            memory.summary = _compact_text(f"{memory.summary} {condensed}")
        else:
            memory.summary = condensed
        memory.summarized_until_turn = pending[-1].turn_index
        return True

    def _deterministic_summary(self, turns: list[ConversationTurn], max_chars: int = 700) -> str:
        fragments: list[str] = []
        for turn in turns:
            normalized = _compact_text(turn.text)
            if not normalized:
                continue
            fragments.append(f"{turn.speaker} said: {normalized}.")

        summary = " ".join(fragments)
        if len(summary) > max_chars:
            summary = summary[: max_chars - 3].rstrip() + "..."
        return summary
