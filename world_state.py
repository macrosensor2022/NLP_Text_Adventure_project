"""
world_state.py — Knowledge graph manager and deterministic game engine.
The LLM is the narrator; this module owns the actual state.
 
Covers:
- Load / save game state (single JSON file)
- Query entities (rooms, items, NPCs)
- Deterministic precondition checking (Stage 3)
- Apply validated state changes (Stage 7)
- Event logging (append-only)
- Build context package for LLM prompts (Stage 4)
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional, Any

from models import (
    GameWorld,
    Room,
    Item,
    NPC,
    Player,
    StateChange,
    Event,
    ParsedAction,
    ActionResolutionResult,
    Intent,
)


class WorldState:
    def __init__(self, game_world: GameWorld):
        self.world = game_world

    @classmethod
    def load(cls, file_path: str = "game_state.json") -> "WorldState":
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Game state file not found: {file_path}")
        raw = json.loads(path.read_text())
        world = GameWorld.model_validate(raw)
        return cls(world)

    def save(self, file_path: str = "game_state.json") -> None:
        Path(file_path).write_text(self.world.model_dump_json(indent=2))
        print(f"Game state saved to {file_path}")

    # Room queries
    def get_room(self, room_id: str) -> Optional[Room]:
        return self.world.rooms.get(room_id)

    def get_current_room(self) -> Room:
        return self.world.rooms[self.world.player.current_room]

    def get_room_items(self, room_id: str) -> list[Item]:
        room = self.get_room(room_id)
        if not room:
            return []
        return [self.world.items[iid] for iid in room.items if iid in self.world.items]

    def get_room_npcs(self, room_id: str) -> list[NPC]:
        room = self.get_room(room_id)
        if not room:
            return []
        return [self.world.npcs[nid] for nid in room.npcs if nid in self.world.npcs]

    def get_exits(self, room_id: str) -> dict[str, str]:
        room = self.get_room(room_id)
        return room.exits if room else {}

    # Player queries
    def get_player(self) -> Player:
        return self.world.player

    def get_player_inventory(self) -> list[Item]:
        return [
            self.world.items[iid] for iid in self.world.player.inventory if iid in self.world.items
        ]

    def player_has_item(self, item_id: str) -> bool:
        return item_id in self.world.player.inventory

    # Item queries
    def get_item(self, item_id: str) -> Optional[Item]:
        return self.world.items.get(item_id)

    def find_item_by_name(self, name: str) -> Optional[Item]:
        name_lower = name.lower()
        for item in self.world.items.values():
            if name_lower in item.name.lower():
                return item
        return None

    def is_item_in_room(self, item_id: str, room_id: str) -> bool:
        room = self.get_room(room_id)
        return room is not None and item_id in room.items

    # NPC queries
    def get_npc(self, npc_id: str) -> Optional[NPC]:
        return self.world.npcs.get(npc_id)

    def is_npc_in_room(self, npc_id: str, room_id: str) -> bool:
        room = self.get_room(room_id)
        return room is not None and npc_id in room.npcs

    # Mutations
    def move_player(self, direction: str) -> tuple[bool, str]:
        current_room = self.get_current_room()
        if direction not in current_room.exits:
            return False, f"There is no exit to the {direction}."

        target_id = current_room.exits[direction]
        target = self.get_room(target_id)
        if not target:
            return False, "That exit leads nowhere."

        if target.locked:
            if target.requires and self.player_has_item(target.requires):
                target.locked = False
                key_item = self.get_item(target.requires)
                key_name = key_item.name if key_item else target.requires
                self._log_event(f"Unlocked {target.name} using {key_name}.", [
                    StateChange(entity_type="room", entity_id=target_id,
                                field="locked", old_value="True", new_value="False")
                ])
            else:
                req_item = self.get_item(target.requires) if target.requires else None
                req_name = req_item.name if req_item else "something"
                return False, f"The {target.name} is locked. You need {req_name}."

        old_room = self.world.player.current_room
        self.world.player.current_room = target_id
        self._log_event(f"Moved from {current_room.name} to {target.name}.", [
            StateChange(entity_type="player", entity_id="player",
                        field="current_room", old_value=old_room, new_value=target_id)
        ])
        return True, f"You move {direction} to {target.name}.\n{target.description}"

    def take_item(self, item_id: str) -> tuple[bool, str]:
        current = self.get_current_room()
        if item_id not in current.items:
            return False, "That item isn't here."
        item = self.get_item(item_id)
        if not item:
            return False, "That item doesn't exist."

        current.items.remove(item_id)
        self.world.player.inventory.append(item_id)
        self._log_event(f"Picked up {item.name}.", [
            StateChange(entity_type="item", entity_id=item_id,
                        field="location", old_value=f"room:{current.id}",
                        new_value="player:inventory")
        ])
        return True, f"You pick up the {item.name}."

    def drop_item(self, item_id: str) -> tuple[bool, str]:
        if item_id not in self.world.player.inventory:
            return False, "You don't have that item."
        item = self.get_item(item_id)
        if not item:
            return False, "That item doesn't exist."

        current = self.get_current_room()
        self.world.player.inventory.remove(item_id)
        current.items.append(item_id)
        self._log_event(f"Dropped {item.name}.", [
            StateChange(entity_type="item", entity_id=item_id,
                        field="location", old_value="player:inventory",
                        new_value=f"room:{current.id}")
        ])
        return True, f"You drop the {item.name}."

    def use_item(self, item_id: str, target_id: Optional[str] = None) -> tuple[bool, str]:
        if not self.player_has_item(item_id):
            return False, "You don't have that item."
        item = self.get_item(item_id)
        if not item:
            return False, "That item doesn't exist."
        if item.is_key and item.unlocks:
            target_room = self.get_room(item.unlocks)
            if target_room and target_room.locked:
                target_room.locked = False
                self._log_event(f"Used {item.name} to unlock {target_room.name}.", [
                    StateChange(entity_type="room", entity_id=item.unlocks,
                                field="locked", old_value="True", new_value="False")
                ])
                return True, f"You use the {item.name}. The {target_room.name} is now unlocked."
        return False, f"You can't figure out how to use the {item.name} here."

    def update_npc_attitude(self, npc_id: str, change: int) -> tuple[bool, str]:
        npc = self.get_npc(npc_id)
        if not npc:
            return False, "That character doesn't exist."
        old_val = npc.attitude
        npc.attitude = max(-100, min(100, npc.attitude + change))
        self._log_event(f"{npc.name}'s attitude changed by {change}.", [
            StateChange(entity_type="npc", entity_id=npc_id,
                        field="attitude", old_value=str(old_val),
                        new_value=str(npc.attitude))
        ])
        return True, f"{npc.name} seems {'more friendly' if change > 0 else 'more hostile'}."

    def damage_player(self, amount: int) -> tuple[bool, str]:
        old_hp = self.world.player.hp
        self.world.player.hp = max(0, self.world.player.hp - amount)
        self._log_event(f"Player took {amount} damage.", [
            StateChange(entity_type="player", entity_id="player",
                        field="hp", old_value=str(old_hp),
                        new_value=str(self.world.player.hp))
        ])
        if self.world.player.hp <= 0:
            return True, f"You take {amount} damage and collapse. Game over."
        return True, f"You take {amount} damage. You have {self.world.player.hp} HP remaining."

    def attack_npc(self, npc_id: str) -> tuple[bool, str]:
        npc = self.get_npc(npc_id)
        if not npc:
            return False, "That character doesn't exist."

        current_room = self.get_current_room()
        if not self.is_npc_in_room(npc_id, current_room.id):
            return False, "That character isn't here."
        if npc.hp <= 0:
            return False, f"{npc.name} has already been defeated."

        weapons = [i for i in self.get_player_inventory() if i.is_weapon]
        weapon = max(weapons, key=lambda i: i.damage, default=None)
        player_damage = 5 + (weapon.damage if weapon else 0)
        weapon_name = weapon.name if weapon else "fists"
        npc_old_hp = npc.hp
        npc.hp = max(0, npc.hp - player_damage)
        self._log_event(
            f"Player attacked {npc.name} with {weapon_name} for {player_damage} damage.",
            [
                StateChange(
                    entity_type="npc",
                    entity_id=npc.id,
                    field="hp",
                    old_value=str(npc_old_hp),
                    new_value=str(npc.hp),
                )
            ],
        )

        if npc.hp <= 0:
            if npc.id in current_room.npcs:
                current_room.npcs.remove(npc.id)
            self._log_event(
                f"{npc.name} was defeated.",
                [
                    StateChange(
                        entity_type="room",
                        entity_id=current_room.id,
                        field="remove_npc",
                        old_value=npc.id,
                        new_value=None,
                    )
                ],
            )
            return True, f"You strike with {weapon_name} for {player_damage} damage and defeat {npc.name}."

        counter_damage = max(1, 4 + max(0, npc.attitude // 25))
        player_old_hp = self.world.player.hp
        self.world.player.hp = max(0, self.world.player.hp - counter_damage)
        self._log_event(
            f"{npc.name} counterattacked for {counter_damage} damage.",
            [
                StateChange(
                    entity_type="player",
                    entity_id="player",
                    field="hp",
                    old_value=str(player_old_hp),
                    new_value=str(self.world.player.hp),
                )
            ],
        )

        outcome = (
            f"{npc.name} hits back for {counter_damage}. You collapse. Game over."
            if self.world.player.hp <= 0
            else f"{npc.name} hits back for {counter_damage}. You have {self.world.player.hp} HP remaining."
        )
        return True, (
            f"You strike with {weapon_name} for {player_damage} damage. "
            f"{npc.name} has {npc.hp} HP left. {outcome}"
        )

    # Deterministic precondition checks
    def check_preconditions(self, action: ParsedAction) -> tuple[bool, str]:
        """
        Returns (can_proceed, message).
        Rejects impossible actions BEFORE they reach the LLM.
        """
        current_room = self.get_current_room()

        if action.intent == Intent.MOVEMENT:
            if not action.direction:
                return False, "Which Direction?"
            if action.direction not in current_room.exits:
                return False, f"There is no exit to the {action.direction}."
            target_id = current_room.exits[action.direction]
            target = self.get_room(target_id)
            if target and target.locked:
                if not target.requires or not self.player_has_item(target.requires):
                    req = self.get_item(target.requires) if target.requires else None
                    return False, f"The {target.name} is locked. You need {req.name if req else 'something'}."
            return True, "OK"

        if action.intent == Intent.INVENTORY:
            if action.verb in ["take", "pick up"]:
                if not action.target:
                    return False, "Take what?"
                if action.target not in current_room.items:
                    return False, "That item isn't here."
                return True, "OK"
            if action.verb == "drop":
                if not action.target:
                    return False, "Drop what?"
                if action.target not in self.world.player.inventory:
                    return False, "You don't have that item."
                return True, "OK"
            if action.verb in ("use", "equip"):
                if not action.target:
                    return False, "Use what?"
                if not self.player_has_item(action.target):
                    return False, "You don't have that item."
                for req in action.requires:
                    if not self.player_has_item(req):
                        req_item = self.get_item(req)
                        return False, f"You need {req_item.name if req_item else req}."
                return True, "OK"

        if action.intent == Intent.COMBAT:
            if not action.target:
                return False, "Attack Who?"
            if not self.is_npc_in_room(action.target, current_room.id):
                return False, "That character isn't here."
            npc = self.get_npc(action.target)
            if not npc:
                return False, "That character doesn't exist."
            if npc.hp <= 0:
                return False, f"{npc.name} has already been defeated."
            return True, "OK"

        if action.intent == Intent.INTERACTION:
            for req in action.requires:
                if not self.player_has_item(req):
                    req_item = self.get_item(req)
                    return False, f"You need {req_item.name if req_item else req}."
            return True, "OK"

        if action.intent == Intent.DIALOGUE:
            if not action.target:
                return False, "Who to Talk To?"
            if not self.is_npc_in_room(action.target, current_room.id):
                return False, "That character isn't here."
            return True, "OK"

        return True, "OK"

    # APPLY VALIDATED LLM OUTPUT (Stage 7)
    def apply_resolution(self, result_changes: list[StateChange], narrative: str) -> None:
        snapshot = self.world.model_dump()
        try:
            for change in result_changes:
                self._apply_single_change(change)
            self._log_event(narrative, result_changes)
        except Exception as e:
            self.world = GameWorld.model_validate(snapshot)
            raise RuntimeError(f"Rollback due to error: {e}")

    def _apply_single_change(self, change: StateChange) -> None:
        if change.entity_type == "player":
            p = self.world.player
            if change.field == "current_room" and change.new_value:
                p.current_room = change.new_value
            elif change.field == "hp" and change.new_value:
                p.hp = int(change.new_value)
            elif change.field == "add_item" and change.new_value:
                if change.new_value not in p.inventory:
                    p.inventory.append(change.new_value)
            elif change.field == "remove_item" and change.new_value:
                if change.new_value in p.inventory:
                    p.inventory.remove(change.new_value)

        elif change.entity_type == "room":
            room = self.get_room(change.entity_id)
            if room:
                if change.field == "locked" and change.new_value:
                    room.locked = change.new_value.lower() == "true"
                elif change.field == "add_item" and change.new_value:
                    if change.new_value not in room.items:
                        room.items.append(change.new_value)
                elif change.field == "remove_item" and change.new_value:
                    if change.new_value in room.items:
                        room.items.remove(change.new_value)

        elif change.entity_type == "npc":
            npc = self.world.npcs.get(change.entity_id)
            if npc:
                if change.field == "attitude" and change.new_value:
                    npc.attitude = max(-100, min(100, int(change.new_value)))
                elif change.field == "hp" and change.new_value:
                    npc.hp = int(change.new_value)
                elif change.field == "current_room" and change.new_value:
                    old_room = self.world.rooms.get(npc.current_room)
                    new_room = self.world.rooms.get(change.new_value)
                    if old_room and npc.id in old_room.npcs:
                        old_room.npcs.remove(npc.id)
                    if new_room and npc.id not in new_room.npcs:
                        new_room.npcs.append(npc.id)
                    npc.current_room = change.new_value

    # Look / Status
    def look(self) -> str:
        room = self.get_current_room()
        parts = [f"== {room.name} ==", room.description]
        items = self.get_room_items(room.id)
        if items:
            parts.append(f"You see {', '.join(item.name for item in items)}.")
        npcs = self.get_room_npcs(room.id)
        if npcs:
            parts.append(f"You see {', '.join(npc.name for npc in npcs)}.")
        parts.append(f"Exits: {', '.join(room.exits.keys())}")
        return "\n".join(parts)

    def get_status(self) -> str:
        p = self.world.player
        inv = ", ".join(i.name for i in self.get_player_inventory()) or "empty"
        return f"HP: {p.hp}/{p.max_hp} | Inventory: {inv}"

    # Context package for LLM prompts
    def build_context_package(self) -> dict:
        """What gets injected into every LLM prompt."""
        current = self.get_current_room()
        player = self.world.player

        adjacent = {}
        for direction, rid in current.exits.items():
            room = self.get_room(rid)
            if room:
                adjacent[direction] = {"id": room.id, "name": room.name, "locked": room.locked}

        npcs_here = []
        for npc in self.get_room_npcs(current.id):
            npcs_here.append({
                "id": npc.id, "name": npc.name,
                "attitude": npc.attitude, "dialogue_state": npc.dialogue_state,
            })

        recent_events = [e.description for e in self.world.events[-5:]]

        return {
            "current_room": {
                "id": current.id, "name": current.name,
                "description": current.description,
                "items": [i.name for i in self.get_room_items(current.id)],
            },
            "player": {
                "name": player.name, "hp": player.hp, "max_hp": player.max_hp,
                "inventory": [i.name for i in self.get_player_inventory()],
                "skills": player.skills,
            },
            "npcs_present": npcs_here,
            "adjacent_rooms": adjacent,
            "recent_events": recent_events,
            "turn": self.world.turn,
        }

    # === INTERNAL ===
    def _log_event(self, description: str, changes: list[StateChange] = None) -> None:
        self.world.turn += 1
        event = Event(turn=self.world.turn, description=description,
                      state_changes=changes or [])
        self.world.events.append(event)
