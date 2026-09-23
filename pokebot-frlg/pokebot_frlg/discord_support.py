from __future__ import annotations

import asyncio
import queue
import threading
import time
from copy import deepcopy
from datetime import timezone
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .discord_payloads import build_embed_payload, safe_int
from .rich_presence_assets import RPC_LARGE_IMAGE, RPC_LARGE_TEXT


class DiscordBotWorker(QThread):
    state = Signal(dict)
    log = Signal(str)

    def __init__(self, settings: dict):
        super().__init__()
        self.settings=deepcopy(settings or {})
        self.outbox=queue.Queue()
        self.stop_event=threading.Event()
        self.loop=None; self.client=None; self.tree=None
        self._snapshot={}; self._snapshot_lock=threading.Lock(); self._synced=False

    def publish(self, kind: str, payload: dict | None=None):
        self.outbox.put((kind, deepcopy(payload or {})))

    def update_snapshot(self, payload: dict):
        with self._snapshot_lock: self._snapshot=deepcopy(payload or {})

    def snapshot(self):
        with self._snapshot_lock: return deepcopy(self._snapshot)

    def request_stop(self):
        self.stop_event.set(); self.outbox.put(("__stop__",{}))
        if self.loop and self.client:
            try: asyncio.run_coroutine_threadsafe(self.client.close(),self.loop)
            except Exception: pass

    def run(self):
        token=str(self.settings.get("discord_bot_token","") or "").strip()
        channel_id=safe_int(self.settings.get("discord_channel_id"),0)
        if not token or not channel_id:
            self.state.emit({"connected":False,"message":"Discord bot not configured"}); return
        try:
            import discord
            from discord import app_commands
        except Exception as exc:
            self.state.emit({"connected":False,"message":"discord.py is not installed"}); self.log.emit(str(exc)); return

        self.loop=asyncio.new_event_loop(); asyncio.set_event_loop(self.loop)
        intents=discord.Intents.none()
        client=discord.Client(intents=intents)
        tree=app_commands.CommandTree(client)
        self.client=client; self.tree=tree

        @tree.command(name="status", description="Show the current PokebotSwitch-FRLG status")
        async def status_cmd(interaction: discord.Interaction):
            snap=self.snapshot(); embed_dict,_=build_embed_payload("status",snap)
            await interaction.response.send_message(embed=discord.Embed.from_dict(embed_dict))

        @tree.command(name="party", description="Show the current live FRLG party")
        async def party_cmd(interaction: discord.Interaction):
            snap=self.snapshot(); party=snap.get("party",[]) or []
            lines=[]
            for i,p in enumerate(party[:6],1):
                if not p or not p.get("valid"): lines.append(f"{i}. —"); continue
                shiny="★ " if p.get("shiny") else ""
                lines.append(f"{i}. {shiny}{p.get('name','Pokémon')} — {p.get('nature','—')} — {p.get('ability_name','—')} — IVs {p.get('iv_spread','—')} — SV {p.get('shiny_xor','—')}")
            embed=discord.Embed(title="PokebotSwitch-FRLG live party",description="\n".join(lines) or "No party data yet.",color=0x4DA3FF)
            embed.set_footer(text="Read-only RAM party view")
            await interaction.response.send_message(embed=embed)

        @client.event
        async def on_ready():
            try:
                if not self._synced:
                    await tree.sync(); self._synced=True
                synced="commands synced"
            except Exception as exc:
                synced=f"command sync failed: {exc}"
            msg=f"Discord connected as {client.user} • {synced}"
            self.state.emit({"connected":True,"message":msg}); self.log.emit(msg)

        async def outbox_loop():
            await client.wait_until_ready()
            while not self.stop_event.is_set():
                try:
                    item=await asyncio.to_thread(self.outbox.get,True,0.25)
                except queue.Empty:
                    continue
                kind,payload=item
                if kind=="__stop__": break
                try:
                    channel=client.get_channel(channel_id)
                    if channel is None: channel=await client.fetch_channel(channel_id)
                    embed_dict,image_path=build_embed_payload(kind,payload)
                    embed=discord.Embed.from_dict(embed_dict)
                    file=None
                    if image_path and Path(str(image_path)).is_file():
                        file=discord.File(str(image_path),filename="pokemon.png")
                        embed.set_thumbnail(url="attachment://pokemon.png")
                    if file: await channel.send(embed=embed,file=file)
                    else: await channel.send(embed=embed)
                except Exception as exc:
                    msg=f"Discord send failed ({kind}): {exc}"; self.log.emit(msg)

        async def main():
            try:
                async with client:
                    await client.login(token)
                    sender=asyncio.create_task(outbox_loop())
                    try: await client.connect(reconnect=True)
                    finally:
                        sender.cancel()
                        try: await sender
                        except BaseException: pass
            except Exception as exc:
                msg=f"Discord connection failed: {exc}"; self.state.emit({"connected":False,"message":msg}); self.log.emit(msg)

        try: self.loop.run_until_complete(main())
        finally:
            self.state.emit({"connected":False,"message":"Discord disconnected"})
            try: self.loop.close()
            except Exception: pass


class RichPresenceWorker(QThread):
    state = Signal(dict)
    log = Signal(str)

    def __init__(self, client_id: str):
        super().__init__(); self.client_id=str(client_id or "").strip(); self.stop_event=threading.Event(); self.updates=queue.Queue()

    def publish(self, snapshot: dict):
        # Collapse stale updates: the newest state is all Rich Presence needs.
        try:
            while True: self.updates.get_nowait()
        except queue.Empty: pass
        self.updates.put(deepcopy(snapshot or {}))

    def request_stop(self): self.stop_event.set(); self.updates.put({"__stop__":True})

    def run(self):
        if not self.client_id:
            self.state.emit({"connected":False,"message":"Rich Presence client ID not configured"}); return
        try:
            from pypresence import Presence
        except Exception as exc:
            self.state.emit({"connected":False,"message":"pypresence is not installed"}); self.log.emit(str(exc)); return
        rpc=None
        try:
            rpc=Presence(self.client_id); rpc.connect(); self.state.emit({"connected":True,"message":"Discord Rich Presence connected"})
            while not self.stop_event.is_set():
                try: snap=self.updates.get(timeout=0.5)
                except queue.Empty: continue
                if snap.get("__stop__"): break
                hunting=bool(snap.get("hunting")); shiny=bool(snap.get("shiny_hold"))
                if shiny:
                    details=f"★ Shiny {snap.get('last_name','Pokémon')} found!"; state="HOME safety hold"
                elif hunting:
                    details=f"Hunting {snap.get('hunt','FRLG')}"; state=f"{snap.get('game','FRLG')} • {snap.get('session_encounters',0)} encounters"
                else:
                    details="Idle"; state=str(snap.get("game") or "PokebotSwitch-FRLG")
                kw={"details":details[:128],"state":state[:128],"large_image":RPC_LARGE_IMAGE,"large_text":RPC_LARGE_TEXT}
                start=snap.get("session_started_epoch")
                if hunting and start: kw["start"]=safe_int(start)
                rpc.update(**kw)
        except Exception as exc:
            self.state.emit({"connected":False,"message":f"Rich Presence unavailable: {exc}"}); self.log.emit(str(exc))
        finally:
            if rpc:
                try: rpc.clear(); rpc.close()
                except Exception: pass
            self.state.emit({"connected":False,"message":"Rich Presence disconnected"})
