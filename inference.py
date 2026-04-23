from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from llama_cpp import Llama
except Exception: 
    Llama = None

MODEL_PATH = "model/final/model-Q4_K_M.gguf"
DEFAULT_FALLBACK_REPLY = "The NPC watches you silently and says nothing."
DEFAULT_TEMPERATURE = 0.9
DEFAULT_MAX_TOKENS = 128

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
        f"NPC Name: {npc_name}\n"
        f"NPC Role: {npc_role}\n"
        f"NPC Persona: {npc_persona}\n"
        f"NPC Attitude: {npc_attitude}\n"
        f"World Context:\n{_stringify_context(compact_context)}"
        f"\nMemory Context:\n{chr(10).join(memory_section_lines)}"
    )
    user_prompt = f"Player says: {player_utterance}"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


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
