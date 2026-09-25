from dataclasses import dataclass


@dataclass(frozen=True)
class FRLGOffsets:
    language: str
    game: str
    title_id: str
    current_seed: int
    wild_pokemon: int
    party_start: int
    overworld: int


# Switch FRLG 1.0.0 offsets. These are heap-relative.
# Source/credit: LegoFigure11/GRASS, GRASS.Core/Structures/Offsets.cs
FRLG_GAME_VERSION = "1.0.0"
INITIAL_SEED = 0x01208000
IN_BATTLE = 0x006D9C91
BATTLE_MENU = 0x011F6FF7
LARGE_SHIFT = 0x08
SMALL_SHIFT = 0x0C
BOX_START_SHIFT = 0x10
BOX_FORMAT_SLOT_SIZE = 0x50
PARTY_SLOT_STRIDE = 0x64

# FRLG 1.0.0 GBA field structures, mapped into the Switch heap.
# gObjectEvents = 0x02036E38 (16 x 0x24-byte ObjectEvent entries).
# gPlayerAvatar = 0x02037078; byte +5 is the active ObjectEvent ID.
# ObjectEvent +0x20 is the facing direction: 0x11 Down, 0x22 Up,
# 0x33 Left, 0x44 Right.
PLAYER_AVATAR = INITIAL_SEED + (0x02037078 - 0x02000000)
OBJECT_EVENTS = INITIAL_SEED + (0x02036E38 - 0x02000000)

_ENTRIES = [
    FRLGOffsets("Japanese", "FireRed",   "01006FA0233F8000", 0xBD68D230, 0x120BF88, 0x120C1E0, 0x1222B54),
    FRLGOffsets("Japanese", "LeafGreen", "0100F1E0233FA000", 0xBD68D230, 0x120BF88, 0x120C1E0, 0x1222B54),
    FRLGOffsets("English",  "FireRed",   "0100554023408000", 0xBD68D2D0, 0x120C028, 0x120C280, 0x1222BDC),
    FRLGOffsets("English",  "LeafGreen", "010034D02340E000", 0xBD68D2D0, 0x120C028, 0x120C280, 0x1222BDC),
    FRLGOffsets("French",   "FireRed",   "01004B3023412000", 0xBD68D220, 0x120C028, 0x120C280, 0x1222BDC),
    FRLGOffsets("French",   "LeafGreen", "010087C02342E000", 0xBD68D220, 0x120C028, 0x120C280, 0x1222BDC),
    FRLGOffsets("Italian",  "FireRed",   "010092302342A000", 0xBD68D220, 0x120C028, 0x120C280, 0x1222BDC),
    FRLGOffsets("Italian",  "LeafGreen", "01005C7023432000", 0xBD68D220, 0x120C028, 0x120C280, 0x1222BDC),
    FRLGOffsets("German",   "FireRed",   "01007F8023416000", 0xBD68D220, 0x120C028, 0x120C280, 0x1222BDC),
    FRLGOffsets("German",   "LeafGreen", "0100FD6023430000", 0xBD68D220, 0x120C028, 0x120C280, 0x1222BDC),
    FRLGOffsets("Spanish",  "FireRed",   "0100EB702342C000", 0xBD68D220, 0x120C028, 0x120C280, 0x1222BDC),
    FRLGOffsets("Spanish",  "LeafGreen", "01002B5023434000", 0xBD68D220, 0x120C028, 0x120C280, 0x1222BDC),
]

BY_TITLE_ID = {x.title_id: x for x in _ENTRIES}


def lookup(title_id: str):
    return BY_TITLE_ID.get(title_id.upper())
