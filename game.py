"""
game.py - playable terminal prototype
"""

from world_state import WorldState
from input_parser import parse_input
from models import Intent
from inference import generate_npc_reply
from npc_memory import NPCMemoryRepository

DEFAULT_DIALOGUE_FALLBACK = "They do not respond."
NO_NPC_DIALOGUE_FALLBACK = "Are you talking to yourself right now? There is no one here."
INVALID_NPC_DIALOGUE_FALLBACK = (
    "Are you talking to yourself right now? You don't see that person here."
)


def resolve_dialogue_target(action, ws):
    """Resolve dialogue target deterministically for one-NPC-per-room scope."""
    if action.intent != Intent.DIALOGUE:
        return action.target, None

    current_room = ws.get_current_room()
    npcs_here = ws.get_room_npcs(current_room.id)

    if action.target:
        if ws.is_npc_in_room(action.target, current_room.id):
            return action.target, None
        return None, INVALID_NPC_DIALOGUE_FALLBACK

    if len(npcs_here) == 1:
        return npcs_here[0].id, None

    if not npcs_here:
        return None, NO_NPC_DIALOGUE_FALLBACK

    # Multi-NPC clarification is deferred while rooms are single-NPC scoped.
    return None, "Who are you talking to?"


def main():
    ws = WorldState.load("game_state.json")
    memory_repo = NPCMemoryRepository()
    print("=" * 50)
    print("  TEXT ADVENTURE — Engine Prototype")
    print("  Commands: go, take, drop, use, look,")
    print("  inventory, status, context, save, quit")
    print("=" * 50)
    print()
    print(ws.look())
    print()

    while True:
        raw = input("> ").strip()
        if not raw:
            continue

        action = parse_input(raw, ws)
        if action.intent == Intent.SYSTEM:
            if action.verb == "look":
                print(ws.look())
            elif action.verb in ("inventory", "inv", "i"):
                items = ws.get_player_inventory()
                if items:
                    print("You are carrying:")
                    for item in items:
                        print(f" - {item.name}:{item.description}")
                else:
                    print("You are carrying nothing.")
            elif action.verb == "status":
                print(ws.get_status())
            elif action.verb == "context":
                import json

                print(json.dumps(ws.world.model_dump(), indent=2))
            elif action.verb == "save":
                ws.save("game_state.json")
            elif action.verb in ("quit", "exit", "q"):
                print("Farewell, adventurer!")
                break
            elif action.verb == "help":
                print("Try natural language ! Examples:")
                print("  'go north' or 'walk to the north'")
                print("  'grab the rusty key' or 'pick up the torch'")
                print("  'attack the rat' or 'hit the giant rat'")
                print("  'talk to greta'")
                print("  look | inventory | status | context | save | quit")
            else:
                print(f"Unknown command. Type 'help'.")
        else:
            if action.intent == Intent.DIALOGUE:
                resolved_target, target_error = resolve_dialogue_target(action, ws)
                if target_error:
                    print(target_error)
                    print()
                    continue
                action.target = resolved_target

            ok, msg = ws.check_preconditions(action)
            if not ok:
                print(msg)
            else:
                if action.intent == Intent.MOVEMENT:
                    success, msg = ws.move_player(action.direction)
                    print(msg)
                    if success:
                        print()
                        print(ws.look())
                elif action.intent == Intent.INVENTORY:
                    if action.verb == "take":
                        _, msg = ws.take_item(action.target)
                        print(msg)
                    elif action.verb == "drop":
                        _, msg = ws.drop_item(action.target)
                        print(msg)
                    elif action.verb in ("use", "equip"):
                        _, msg = ws.use_item(action.target)
                        print(msg)
                elif action.intent == Intent.COMBAT:
                    print(
                        f"You attack the {action.target}! (combat system coming soon)"
                    )
                elif action.intent == Intent.DIALOGUE:
                    npc = ws.get_npc(action.target) if action.target else None
                    if not npc:
                        print("That character isn't here.")
                        print()
                        continue

                    context = ws.build_context_package()
                    compact_context = {
                        "room_name": context["current_room"]["name"],
                        "room_description": context["current_room"]["description"],
                        "nearby_npcs": [entry["name"] for entry in context["npcs_present"]],
                        "player_inventory": context["player"]["inventory"],
                        "recent_events": context["recent_events"][-3:],
                        "target_attitude": npc.attitude,
                    }
                    npc_info = {
                        "name": npc.name,
                        "role": npc.dialogue_state,
                        "persona": npc.description,
                        "attitude": npc.attitude,
                    }
                    memory = memory_repo.load(npc.id, npc.name)
                    npc_memory_context = memory_repo.build_prompt_context(memory)

                    reply = generate_npc_reply(
                        npc_info=npc_info,
                        player_utterance=raw,
                        compact_context=compact_context,
                        npc_memory_context=npc_memory_context,
                        fallback_reply=DEFAULT_DIALOGUE_FALLBACK,
                    )
                    memory_repo.append_exchange(
                        memory,
                        player_text=raw,
                        npc_name=npc.name,
                        npc_text=reply,
                        game_turn=ws.world.turn,
                    )
                    print(f"{npc.name}: {reply}")
                elif action.intent == Intent.INTERACTION:
                    print(f"You try to {action.verb}. (interaction system coming soon)")
        print()


if __name__ == "__main__":
    main()

