from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum

MAX_RECENT_TURNS = 8
MEMORY_BUDGET_RATIO = 0.6

#Intent categories 
class  Intent(str,Enum):
    MOVEMENT = "MOVEMENT"
    INVENTORY = "INVENTORY"
    DIALOGUE = "DIALOGUE"
    COMBAT = "COMBAT"
    INTERACTION = "INTERACTION"
    SOCIAL_INTERACTION = "SOCIAL_INTERACTION"
    SYSTEM = "SYSTEM"


#Core game engine classes

class Item(BaseModel):
    id:str
    name: str
    description: str
    is_weapon:bool = False
    is_key:bool = False
    damage:int = 0
    unlocks:Optional[str] = None

class NPC(BaseModel):
    id:str
    name:str
    description:str
    current_room:str
    attitude:int = Field(default=0, ge=-100, le=100)
    dialogue_state:str="default"
    hp:int = 50

class Room(BaseModel):
    id:str
    name:str
    description:str
    exits:dict[str,str]
    items:list[str] = []
    npcs:list[str] = []
    locked:bool = False
    requires:Optional[str] = None

class Player(BaseModel):
    name:str = "Adventurer"
    current_room:str
    inventory:list[str] = []
    hp:int = 100
    max_hp:int = 100
    skills:dict[str,int] = {}

#Event log
class StateChange(BaseModel):
    entity_type:str
    entity_id:str
    field:str
    old_value:Optional[Any] = None
    new_value:Optional[Any] = None

class Event(BaseModel):
    turn:int
    description:str
    state_changes:list[StateChange] = []

#Interface contracts for member 2
class ParsedAction(BaseModel):
    intent:Intent
    verb:str
    target:Optional[str] = None
    direction:Optional[str] = None
    requires:list[str] = []
    participants:list[str] = []

class ActionResolutionResult(BaseModel):
    is_possible:bool
    difficulty:int = Field(default=5, ge=1, le=10)
    success:bool
    state_changes:list[StateChange] = []
    narrative:str

#Top level game state
class GameWorld(BaseModel):
    rooms:dict[str,Room] 
    items:dict[str,Item]
    npcs:dict[str,NPC]
    player:Player
    turn:int = 0
    events:list[Event] = [] 


class ConversationTurn(BaseModel):
    speaker: str
    text: str
    turn_index: int = Field(ge=1)
    game_turn: Optional[int] = None


class NPCConversationMemory(BaseModel):
    npc_id: str
    npc_name: str
    summary: str = ""
    summarized_until_turn: int = 0
    turns: list[ConversationTurn] = []