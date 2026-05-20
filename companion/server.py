"""
CC Voice Chat — Companion Server (GUI)
Streams microphone audio to ComputerCraft via WebSocket + Cloudflare Quick Tunnel.

Run:  python server.py   (or double-click start.bat)
"""

import asyncio
import re
import subprocess
import sys
import threading
import tkinter as tk

import numpy as np
import sounddevice as sd
import websockets

# ── Config ───────────────────────────────────────────────────────────────────
PORT          = 8765
SAMPLE_RATE   = 48_000
CHANNELS      = 1
CHUNK_SAMPLES = 4_800   # 100 ms per chunk

# ── Shared state ──────────────────────────────────────────────────────────────
_connected: set = set()
_loop:  asyncio.AbstractEventLoop | None = None
_queue: asyncio.Queue               | None = None
_level: float = 0.0   # written by audio C thread, read by Tk main thread (GIL safe)
_app          = None  # set after App() is created


# ── Audio callback (runs in sounddevice C thread) ────────────────────────────
def _audio_callback(indata, frames, time_info, status):
    global _level
    if not _loop or not _queue:
        return
    mono = indata[:, 0]
    _level = float(np.abs(mono).mean())
    samples = np.clip(mono * 127.0, -128, 127).astype(np.int8).tobytes()
    if not _queue.full():
        _loop.call_soon_threadsafe(_queue.put_nowait, samples)


# ── Asyncio WebSocket server (runs in background thread) ─────────────────────
async def _broadcast_loop():
    while True:
        data = await _queue.get()
        if not _connected:
            continue
        dead: set = set()
        for ws in list(_connected):
            try:
                await ws.send(data)
            except Exception:
                dead.add(ws)
        _connected -= dead


async def _handler(websocket):
    addr = str(websocket.remote_address)
    _connected.add(websocket)
    if _app:
        _app.root.after(0, _app.on_client_event, f"[+] Connected:    {addr}", True)
    try:
        async for _ in websocket:
            pass
    except Exception:
        pass
    finally:
        _connected.discard(websocket)
        if _app:
            _app.root.after(0, _app.on_client_event, f"[-] Disconnected: {addr}", False)


async def _run_server():
    global _loop, _queue
    _loop  = asyncio.get_running_loop()
    _queue = asyncio.Queue(maxsize=100)
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                        dtype="float32", blocksize=CHUNK_SAMPLES,
                        callback=_audio_callback):
        asyncio.create_task(_broadcast_loop())
        async with websockets.serve(_handler, "0.0.0.0", PORT):
            await asyncio.Future()  # run forever


def _server_thread():
    asyncio.run(_run_server())


# ── Cloudflare URL helpers ────────────────────────────────────────────────────
_CF_RE = re.compile(r'https://[a-z0-9\-]+\.trycloudflare\.com')


def _find_cf_url(text: str):
    m = _CF_RE.search(text)
    return m.group(0) if m else None


def _to_wss(url: str) -> str:
    return re.sub(r'^https?://', 'wss://', url)


# ── GUI ───────────────────────────────────────────────────────────────────────
class App:
    # Catppuccin Mocha palette
    BG     = "#1e1e2e"
    CARD   = "#2a2a3e"
    ENTRY  = "#313244"
    FG     = "#cdd6f4"
    ACCENT = "#89b4fa"
    GREEN  = "#a6e3a1"
    RED    = "#f38ba8"
    YELLOW = "#f9e2af"
    MUTED  = "#6c7086"

    def __init__(self, root: tk.Tk):
        self.root = root
        self._cf_proc: subprocess.Popen | None = None
        self._client_count = 0
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._shutdown)
        # Start background services
        self._log("WebSocket server starting on port 8765…", "muted")
        threading.Thread(target=_server_thread, daemon=True).start()
        threading.Thread(target=self._run_cloudflared, daemon=True).start()
        self._poll_level()  # start 20 fps level-meter refresh

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        r = self.root
        r.title("CC Voice Chat")
        r.configure(bg=self.BG)
        r.resizable(False, False)

        def lbl(parent, text, size=10, bold=False, fg=None, **kw):
            return tk.Label(
                parent, text=text,
                bg=parent.cget("bg"), fg=fg or self.FG,
                font=("Segoe UI", size, "bold" if bold else "normal"),
                **kw,
            )

        p = {"padx": 16}

        # Header row
        hdr = tk.Frame(r, bg=self.BG)
        hdr.pack(fill="x", **p, pady=(16, 4))
        lbl(hdr, "CC Voice Chat", 18, bold=True, fg=self.ACCENT).pack(side="left")
        self._client_lbl = lbl(hdr, "0 clients", 10, bold=True, fg=self.MUTED)
        self._client_lbl.pack(side="right", pady=4)

        # Status row
        sf = tk.Frame(r, bg=self.CARD, padx=12, pady=8)
        sf.pack(fill="x", **p, pady=4)
        self._dot = lbl(sf, "●", 13, fg=self.YELLOW)
        self._dot.pack(side="left")
        self._status_lbl = lbl(sf, "  Waiting for tunnel…", 9)
        self._status_lbl.pack(side="left")

        # URL box
        uf = tk.Frame(r, bg=self.CARD, padx=12, pady=10)
        uf.pack(fill="x", **p, pady=4)
        lbl(uf, "Paste this URL when the CC script asks:", 9, fg=self.MUTED).pack(anchor="w")
        row = tk.Frame(uf, bg=self.CARD)
        row.pack(fill="x", pady=(4, 0))
        self._url_var = tk.StringVar(value="Waiting for cloudflared…")
        tk.Entry(
            row, textvariable=self._url_var,
            font=("Consolas", 10), bg=self.ENTRY, fg=self.ACCENT,
            relief="flat", bd=4, state="readonly",
            readonlybackground=self.ENTRY,
        ).pack(side="left", fill="x", expand=True, ipady=5)
        self._copy_btn = tk.Button(
            row, text="Copy", font=("Segoe UI", 9),
            bg="#585b70", fg=self.FG, relief="flat",
            padx=12, pady=5, cursor="hand2",
            command=self._copy_url,
        )
        self._copy_btn.pack(side="left", padx=(6, 0))

        # Mic level meter
        mf = tk.Frame(r, bg=self.CARD, padx=12, pady=10)
        mf.pack(fill="x", **p, pady=4)
        lbl(mf, "Microphone level", 9, fg=self.MUTED).pack(anchor="w")
        self._cv = tk.Canvas(mf, height=12, bg=self.ENTRY, highlightthickness=0)
        self._cv.pack(fill="x", pady=(4, 0))
        self._bar = self._cv.create_rectangle(0, 0, 0, 12, fill=self.GREEN, outline="")

        # Activity log
        lf = tk.Frame(r, bg=self.CARD, padx=12, pady=10)
        lf.pack(fill="both", expand=True, **p, pady=4)
        lbl(lf, "Activity log", 9, fg=self.MUTED).pack(anchor="w")
        self._log_box = tk.Text(
            lf, height=7, font=("Consolas", 9),
            bg="#181825", fg=self.FG, relief="flat",
            state="disabled", wrap="word", cursor="arrow",
        )
        self._log_box.pack(fill="both", expand=True, pady=(4, 0))
        self._log_box.tag_config("green",  foreground=self.GREEN)
        self._log_box.tag_config("red",    foreground=self.RED)
        self._log_box.tag_config("muted",  foreground=self.MUTED)
        self._log_box.tag_config("accent", foreground=self.ACCENT)

        # Stop button
        tk.Button(
            r, text="Stop Server", font=("Segoe UI", 10),
            bg=self.RED, fg="#1e1e2e", relief="flat",
            padx=20, pady=7, cursor="hand2",
            command=self._shutdown,
        ).pack(pady=(4, 16))

        r.update_idletasks()
        r.minsize(500, 480)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _log(self, msg: str, tag: str = "muted"):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", msg + "\n", tag)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _copy_url(self):
        url = self._url_var.get()
        if "Waiting" in url or "not found" in url:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        self._copy_btn.config(text="✓ Copied")
        self.root.after(2000, lambda: self._copy_btn.config(text="Copy"))

    def _poll_level(self):
        w = self._cv.winfo_width() or 1
        self._cv.coords(self._bar, 0, 0, int(min(_level * 6, 1.0) * w), 12)
        self.root.after(50, self._poll_level)

    # ── Callbacks from background threads (scheduled via root.after) ──────────
    def on_client_event(self, msg: str, connected: bool):
        self._client_count += 1 if connected else -1
        self._client_count = max(0, self._client_count)
        n = self._client_count
        self._client_lbl.config(
            text=f"{n} client{'s' if n != 1 else ''}",
            fg=self.GREEN if n > 0 else self.MUTED,
        )
        self._log(msg, "green" if connected else "red")

    def _set_tunnel_url(self, https_url: str):
        wss = _to_wss(https_url)
        self._url_var.set(wss)
        self._status_lbl.config(text="  Tunnel active")
        self._dot.config(fg=self.GREEN)
        self._log(f"Tunnel ready: {wss}", "accent")

    # ── Background: cloudflared subprocess ───────────────────────────────────
    def _run_cloudflared(self):
        try:
            proc = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://localhost:{PORT}"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            self._cf_proc = proc
            url_found = False
            for line in proc.stdout:     # drain pipe — prevents cloudflared blocking
                if not url_found:
                    url = _find_cf_url(line)
                    if url:
                        url_found = True
                        self.root.after(0, self._set_tunnel_url, url)
            proc.wait()
        except FileNotFoundError:
            self.root.after(0, self._on_cf_missing)

    def _on_cf_missing(self):
        self._url_var.set("cloudflared not found — see README")
        self._status_lbl.config(text="  cloudflared not installed")
        self._dot.config(fg=self.RED)
        self._log("cloudflared not found on PATH.", "red")
        self._log(
            "Download: https://developers.cloudflare.com/cloudflare-one/"
            "connections/connect-networks/downloads/", "muted"
        )
        self._log("Then manually run: cloudflared tunnel --url http://localhost:8765", "muted")

    def _shutdown(self):
        if self._cf_proc:
            self._cf_proc.terminate()
        self.root.destroy()
        sys.exit(0)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    _app = App(root)
    root.mainloop()
