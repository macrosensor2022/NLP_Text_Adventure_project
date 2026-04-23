from __future__ import annotations

from pathlib import Path
from typing import Any
import json

try:
    from llama_cpp import Llama
except Exception: 
    Llama = None

MODEL_PATH = "model/final/model-Q4_K_M.gguf"
DEFAULT_FALLBACK_REPLY = "The NPC watches you silently and says nothing."
DEFAULT_TEMPERATURE = 0.9
DEFAULT_MAX_TOKENS = 128
_REWRITE_DIRECTIONS = {"north", "south", "east", "west", "up", "down"}
_REWRITE_VERBS = {"go", "take", "drop", "use", "attack", "talk"}
_CLUE_ITEM_KEYWORDS = ("key", "rune", "seal", "map", "note", "tablet", "lens", "crank", "valve")

_MODEL: Any = None


def _get_model(
    model_path: str = MODEL_PATH,
    n_ctx: int = 2048,
    n_threads: int = 8,
    verbose: bool = False,
) -> Any:
    global _MODEL

    if _MODEL is not None:
        return _MODEL

    if Llama is None:
        raise RuntimeError("llama_cpp is not available in this environment.")

    if not Path(model_path).exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    _MODEL = Llama(
        model_path=model_path,
        n_ctx=n_ctx,
        n_threads=n_threads,
        verbose=verbose,
    )
    return _MODEL


def _stringify_context(compact_context: dict[str, Any] | None) -> str:
    if not compact_context:
        return "No additional context."
    return "\n".join(f"{key}: {value}" for key, value in compact_context.items())


def _build_messages(
    npc_info: dict[str, Any],
    player_utterance: str,
    compact_context: dict[str, Any] | None,
    npc_memory_context: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    npc_name = str(npc_info.get("name", "Unknown NPC"))
    npc_role = str(npc_info.get("role", "NPC"))
    npc_persona = str(npc_info.get("persona", "No persona details provided."))
    npc_attitude = npc_info.get("attitude", "unknown")
    npc_secret = str(npc_info.get("secret", "")).strip() or "No specific secret."

    memory_summary = ""
    memory_recent_turns = []
    if npc_memory_context:
        memory_summary = str(npc_memory_context.get("summary", "")).strip()
        memory_recent_turns = npc_memory_context.get("recent_turns", [])
        if not isinstance(memory_recent_turns, list):
            memory_recent_turns = []

    memory_section_lines = []
    if memory_summary:
        memory_section_lines.append(f"Prior Conversation Summary: {memory_summary}")
    if memory_recent_turns:
        recent_blob = "\n".join(f"- {line}" for line in memory_recent_turns)
        memory_section_lines.append(f"Recent Conversation Turns:\n{recent_blob}")
    if not memory_section_lines:
        memory_section_lines.append("No prior conversation memory available.")

    system_prompt = (
        "You are an NPC in a text adventure game. "
        "Stay in-character, be concise, and do not describe impossible state changes.\n"
        "Keep your response consistent with your prior accepted dialogue when memory is provided.\n"
        "You may hold secrets, clues, or items relevant to this area. Do not reveal them easily.\n"
        "Only share key secrets or important items after trust-building dialogue or a clear, polite request from the player.\n"
        "If not ready to share, give a subtle hint instead of the full secret.\n"
        f"NPC Name: {npc_name}\n"
        f"NPC Role: {npc_role}\n"
        f"NPC Persona: {npc_persona}\n"
        f"NPC Attitude: {npc_attitude}\n"
        f"NPC Secret: {npc_secret}\n"
        f"World Context:\n{_stringify_context(compact_context)}"
        f"\nMemory Context:\n{chr(10).join(memory_section_lines)}"
    )
    user_prompt = f"Player says: {player_utterance}"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def rewrite_to_command(raw_text: str) -> str | None:
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return None

    system_prompt = (
        "Rewrite the player input as exactly one command for a text adventure.\n"
        "Allowed verbs: go, take, drop, use, attack, talk.\n"
        "Output format: '<verb> <target_or_direction>' only.\n"
        "For go, direction must be one of north/south/east/west/up/down.\n"
        "Return only the command, no punctuation or commentary."
    )
    try:
        model = _get_model()
        response = model.create_chat_completion(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": raw_text}],
            max_tokens=24,
            temperature=0.1,
        )
        content = response["choices"][0]["message"]["content"]
    except Exception:
        return None

    rewritten = " ".join(str(content).strip().lower().split())
    if not rewritten:
        return None
    parts = rewritten.split(maxsplit=1)
    if parts[0] not in _REWRITE_VERBS or len(parts) < 2:
        return None
    if parts[0] == "go" and parts[1] not in _REWRITE_DIRECTIONS:
        return None
    return rewritten


def classify_item_as_clue(item_name: str, item_description: str) -> dict[str, str | bool]:
    name = (item_name or "").strip()
    description = (item_description or "").strip()
    fallback_reason = "looks relevant to progression"
    fallback_include = any(
        keyword in f"{name} {description}".lower()
        for keyword in _CLUE_ITEM_KEYWORDS
    )

    if not name:
        return {"include": False, "reason": "missing item name"}

    system_prompt = (
        "You classify whether an inventory item should be a discovered clue in a text adventure journal.\n"
        "Return strict JSON only with keys include (boolean) and reason (short string).\n"
        "Mark include=true only if item likely helps progression, puzzles, lore, or unlocking.\n"
    )
    user_prompt = f"Item name: {name}\nItem description: {description}"

    try:
        model = _get_model()
        response = model.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=64,
            temperature=0.1,
        )
        content = str(response["choices"][0]["message"]["content"]).strip()
        payload = json.loads(content)
        include = payload.get("include")
        reason = payload.get("reason")
        if isinstance(include, bool) and isinstance(reason, str) and reason.strip():
            return {"include": include, "reason": reason.strip()}
    except Exception:
        pass

    return {
        "include": fallback_include,
        "reason": fallback_reason if fallback_include else "not clearly a clue item",
    }


def generate_npc_reply(
    npc_info: dict[str, Any],
    player_utterance: str,
    compact_context: dict[str, Any] | None = None,
    npc_memory_context: dict[str, Any] | None = None,
    fallback_reply: str = DEFAULT_FALLBACK_REPLY,
    *,
    model_path: str = MODEL_PATH,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    if not player_utterance or not player_utterance.strip():
        return fallback_reply

    try:
        model = _get_model(model_path=model_path)
        messages = _build_messages(
            npc_info,
            player_utterance.strip(),
            compact_context,
            npc_memory_context,
        )
        response = model.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = response["choices"][0]["message"]["content"]
        if isinstance(content, str) and content.strip():
            return content.strip()
    except Exception:
        return fallback_reply

    return fallback_reply


def format_journal_fallback(
    discovered_clues: list[str] | None = None,
    conversation_summaries: list[str] | None = None,
) -> str:
    discovered_clues = discovered_clues or []
    conversation_summaries = conversation_summaries or []

    def _section(title: str, lines: list[str], empty_text: str) -> str:
        if not lines:
            return f"{title}\n- {empty_text}"
        bullets = "\n".join(f"- {line}" for line in lines[:6])
        return f"{title}\n{bullets}"

    return "\n\n".join(
        [
            _section("Discovered clues", discovered_clues, "No solid clues recorded yet."),
            _section("Conversation summaries", conversation_summaries, "No conversation summaries logged yet."),
        ]
    )


def generate_journal_summary(
    discovered_clues: list[str] | None = None,
    conversation_summaries: list[str] | None = None,
    *,
    model_path: str = MODEL_PATH,
    max_tokens: int = 200,
    temperature: float = 0.3,
) -> str:
    discovered_clues = discovered_clues or []
    conversation_summaries = conversation_summaries or []

    fallback_text = format_journal_fallback(discovered_clues, conversation_summaries)
    system_prompt = (
        "You write a player's journal in a text adventure game.\n"
        "Use only the facts provided. Do not invent rooms, NPCs, clues, or tasks.\n"
        "Keep it concise and practical.\n"
        "Return exactly these section headers with bullet points:\n"
        "Discovered clues\n"
        "Conversation summaries\n"
        "In Conversation summaries, every bullet must keep speaker attribution as 'NPC Name: summary'.\n"
    )
    user_prompt = (
        f"Discovered clues: {discovered_clues}\n"
        f"Conversation summaries: {conversation_summaries}\n"
    )

    try:
        model = _get_model(model_path=model_path)
        response = model.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = response["choices"][0]["message"]["content"]
        if isinstance(content, str) and content.strip():
            generated = content.strip()
            if "Discovered clues" not in generated or "Conversation summaries" not in generated:
                return fallback_text
            conversation_block = generated.split("Conversation summaries", maxsplit=1)[-1]
            summary_lines = [line.strip() for line in conversation_block.splitlines() if line.strip().startswith("-")]
            if any(": " not in line for line in summary_lines):
                return fallback_text
            return generated
    except Exception:
        return fallback_text

    return fallback_text


if __name__ == "__main__":
    sample_reply = generate_npc_reply(
        npc_info={
            "name": "Elaria",
            "role": "Ranger",
            "persona": "Protects the forest and trusts few outsiders.",
            "attitude": 10,
        },
        player_utterance="Hail ranger, can you guide me safely through the woods?",
        compact_context={
            "room": "Dark Forest Clearing",
            "inventory": ["map", "torch"],
            "recent_events": ["player arrived from north path"],
        },
    )
    print(sample_reply)
