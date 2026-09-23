from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame,QVBoxLayout,QHBoxLayout,QLabel

class SpriteLabel(QLabel):
    def __init__(self,size=64):
        super().__init__(); self.size_px=size; self.setFixedSize(size,size); self.setAlignment(Qt.AlignCenter); self.setObjectName("Sprite")
    def set_sprite(self,path:str|None,shiny=False):
        if path:
            pm=QPixmap(path)
            if not pm.isNull():
                self.setPixmap(pm.scaled(self.size_px,self.size_px,Qt.KeepAspectRatio,Qt.FastTransformation)); self.setText(""); return
        self.setPixmap(QPixmap()); self.setText("★" if shiny else "—")

class StatBox(QFrame):
    def __init__(self,title,value="0"):
        super().__init__(); self.setObjectName("Card"); lay=QVBoxLayout(self); lay.setContentsMargins(10,8,10,8); self.t=QLabel(title); self.t.setObjectName("Muted"); self.v=QLabel(value); self.v.setStyleSheet("font-size:15pt;font-weight:700;"); lay.addWidget(self.t); lay.addWidget(self.v)
    def set(self,v): self.v.setText(str(v))

class PartyCard(QFrame):
    def __init__(self,slot):
        super().__init__(); self.setObjectName("PartyCard"); self.setMinimumHeight(112)
        root=QHBoxLayout(self); root.setContentsMargins(8,7,8,7); root.setSpacing(8)
        self.sprite=SpriteLabel(68); root.addWidget(self.sprite,0,Qt.AlignVCenter)
        lay=QVBoxLayout(); lay.setContentsMargins(0,0,0,0); lay.setSpacing(2); root.addLayout(lay,1)
        self.slot=QLabel(f"SLOT {slot}"); self.slot.setObjectName("Muted"); self.name=QLabel("Empty"); self.name.setStyleSheet("font-size:12pt;font-weight:700;"); self.line1=QLabel("—"); self.line2=QLabel("—"); self.line1.setWordWrap(True); self.line2.setWordWrap(True)
        lay.addWidget(self.slot); lay.addWidget(self.name); lay.addWidget(self.line1); lay.addWidget(self.line2); lay.addStretch()
    def update_pk(self,p):
        if not p or not p.get("valid"):
            self.sprite.set_sprite(None); self.name.setText("Empty"); self.name.setStyleSheet("font-size:12pt;font-weight:700;"); self.line1.setText("—"); self.line2.setText("—"); self.setToolTip("Empty party slot"); return
        shiny=bool(p.get("shiny")); self.sprite.set_sprite(p.get("sprite_path"),shiny)
        prefix="★ " if shiny else ""; self.name.setText(prefix+p.get("name",f"#{p.get('species')}")); self.name.setStyleSheet("font-size:12pt;font-weight:700;color:#ffe36e;" if shiny else "font-size:12pt;font-weight:700;")
        ability=p.get("ability_name") or f"Ability slot {p.get('ability_slot')}"
        self.line1.setText(f"{p.get('nature')} • {ability} • SV {p.get('shiny_xor')}")
        self.line2.setText(f"IV {p.get('iv_spread')}  Σ {p.get('iv_sum')}")
        pokerus=p.get('pokerus',0); moves=[p.get(f'move{i}',0) for i in range(1,5)]
        self.setToolTip(f"{p.get('name')}\nPID: {p.get('pid',0):08X}\nTID/SID: {p.get('tid')}/{p.get('sid')}\nNature: {p.get('nature')}\nIVs: {p.get('iv_spread')} (Σ {p.get('iv_sum')})\nEVs: {p.get('ev_spread')}\nSV: {p.get('shiny_xor')}\nAbility: {ability}\nAbility slot: {p.get('ability_slot')}\nHeld item ID: {p.get('held_item')}\nPokérus: 0x{pokerus:02X}\nMove IDs: {' / '.join(map(str,moves))}\nShiny: {'YES' if shiny else 'No'}")
