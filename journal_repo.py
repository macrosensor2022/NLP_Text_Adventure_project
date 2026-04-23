from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from inference import classify_item_as_clue

JOURNAL_PATH = "memory/journal.json"


def _default_journal() -> dict[str, Any]:
    return {
        "updated_turn": 0,
        "discovered_clues": [],
        "conversation_summaries": [],
    }


def load_journal(path: str = JOURNAL_PATH) -> dict[str, Any]:
    journal_path = Path(path)
    if not journal_path.exists():
        return _default_journal()
    try:
        data = json.loads(journal_path.read_text())
        if not isinstance(data, dict):
            return _default_journal()
        return {
            "updated_turn": int(data.get("updated_turn", 0)),
            "discovered_clues": list(data.get("discovered_clues", [])),
            "conversation_summaries": list(data.get("conversation_summaries", [])),
        }
    except Exception:
        return _default_journal()


def save_journal(data: dict[str, Any], path: str = JOURNAL_PATH) -> None:
    journal_path = Path(path)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(json.dumps(data, indent=2))


def _summarize_memory_for_journal(memory, prompt_context: dict[str, Any]) -> str:
    summary = str(prompt_context.get("summary", "")).strip()
    if summary:
        return summary

    npc_turns: list[str] = []
    for turn in memory.turns:
        speaker = str(getattr(turn, "speaker", "")).strip()
        text = str(getattr(turn, "text", "")).strip()
        if not text or speaker.lower() == "player":
            continue
        npc_turns.append(text)

    if not npc_turns:
        return ""

    return " ".join(npc_turns[-3:])


def rebuild_journal(world_state, memory_repo, path: str = JOURNAL_PATH) -> dict[str, Any]:
    clue_entries: list[str] = []
    for item in world_state.get_player_inventory():
        decision = classify_item_as_clue(item.name, item.description)
        if not decision.get("include"):
            continue
        reason = str(decision.get("reason", "")).strip()
        clue_text = f"Found {item.name}: {reason}."
        if clue_text not in clue_entries:
            clue_entries.append(clue_text)

    summaries: list[str] = []
    for npc in world_state.world.npcs.values():
        memory = memory_repo.load_existing(npc.id)
        if memory is None:
            continue
        if memory.npc_name != npc.name:
            memory.npc_name = npc.name
            memory_repo.save(memory)
        prompt_context = memory_repo.build_prompt_context(memory)
        summary = _summarize_memory_for_journal(memory, prompt_context)
        if summary and not str(memory.summary).strip():
            memory.summary = summary
            if memory.turns:
                memory.summarized_until_turn = memory.turns[-1].turn_index
            memory_repo.save(memory)
        if summary:
            summary_line = f"{npc.name}: {summary}"
            if summary_line not in summaries:
                summaries.append(summary_line)
            clue_line = f"Conversation clue from {npc.name}: {summary}"
            if clue_line not in clue_entries:
                clue_entries.append(clue_line)

    journal = {
        "updated_turn": world_state.world.turn,
        "discovered_clues": clue_entries,
        "conversation_summaries": summaries,
    }
    save_journal(journal, path=path)
    return journal
