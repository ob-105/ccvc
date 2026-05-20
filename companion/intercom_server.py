"""
CC Intercom – Companion Server
Captures the system microphone and streams 48 kHz mono PCM audio to any
connected ComputerCraft computer over a WebSocket.

A Cloudflare Quick Tunnel is launched automatically so the CC computer can
reach this machine from anywhere without port-forwarding.
"""

import asyncio
import re
import sys
from typing import Optional, Set

import numpy as np
import sounddevice as sd
import websockets
from websockets.server import WebSocketServerProtocol

# ── Audio settings ────────────────────────────────────────────────────────────
SAMPLE_RATE   = 48_000   # Hz  – must match CC speaker.playAudio native rate
CHUNK_FRAMES  = 4_800    # 100 ms per chunk at 48 kHz
SERVER_HOST   = "127.0.0.1"
SERVER_PORT   = 8_765

# ── Shared state (set in _main before any callbacks fire) ─────────────────────
_event_loop: asyncio.AbstractEventLoop
_audio_queue: asyncio.Queue
_clients: Set[WebSocketServerProtocol] = set()


# ── Audio capture callback (runs in sounddevice thread) ───────────────────────
def _audio_callback(indata: np.ndarray, frames: int, time_info, status) -> None:
    if status:
        print(f"[audio] {status}", file=sys.stderr)

    # Convert float32 [-1, 1] -> signed 8-bit PCM bytes (-128..127).
    # CC speaker.playAudio expects 8-bit amplitudes at 48 kHz.
    pcm = np.clip(indata[:, 0] * 127.0, -128, 127).astype(np.int8)
    raw = pcm.tobytes()

    # Hand off to the asyncio event loop safely from this background thread
    _event_loop.call_soon_threadsafe(_audio_queue.put_nowait, raw)


# ── WebSocket connection handler ──────────────────────────────────────────────
async def _ws_handler(ws: WebSocketServerProtocol) -> None:
    addr = ws.remote_address
    _clients.add(ws)
    print(f"[+] CC computer connected     {addr}")
    try:
        await ws.wait_closed()
    finally:
        _clients.discard(ws)
        print(f"[-] CC computer disconnected  {addr}")


# ── Broadcast loop: dequeue PCM frames and push to all clients ────────────────
async def _broadcast_loop() -> None:
    while True:
        raw = await _audio_queue.get()
        if not _clients:
            continue  # nobody listening, discard

        dead: Set[WebSocketServerProtocol] = set()
        for ws in list(_clients):
            try:
                await ws.send(raw)          # binary frame
            except Exception:
                dead.add(ws)
        _clients.difference_update(dead)


# ── Cloudflare Quick Tunnel ───────────────────────────────────────────────────
async def _start_tunnel(port: int) -> Optional[str]:
    """Launch cloudflared and return the public HTTPS URL (or None on error)."""
    print("[*] Starting Cloudflare Quick Tunnel …")
    try:
        proc = await asyncio.create_subprocess_exec(
            "cloudflared", "tunnel", "--url", f"http://localhost:{port}",
            stderr=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError:
        print(
            "[!] cloudflared not found in PATH.\n"
            "    Download it from:\n"
            "    https://developers.cloudflare.com/cloudflare-one/"
            "connections/connect-networks/downloads/\n"
            "    Then add it to your PATH and restart the companion app."
        )
        return None

    pattern = re.compile(r"https://[\w-]+\.trycloudflare\.com")
    while True:
        line_bytes = await proc.stderr.readline()
        if not line_bytes:
            print("[!] cloudflared exited before a URL was emitted.")
            return None
        line = line_bytes.decode(errors="replace").rstrip()
        print(f"    [cloudflared] {line}")
        m = pattern.search(line)
        if m:
            return m.group(0)


# ── Startup helpers ───────────────────────────────────────────────────────────
def _print_input_devices() -> None:
    print("\nAvailable microphone / input devices:")
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            marker = " ← default" if i == sd.default.device[0] else ""
            print(f"  [{i:2d}]  {dev['name']}{marker}")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────
async def _main() -> None:
    global _event_loop, _audio_queue
    _event_loop  = asyncio.get_running_loop()
    _audio_queue = asyncio.Queue(maxsize=100)   # ~10 s buffer; drop if overrun

    _print_input_devices()
    raw_input = input("Device index (press Enter for default): ").strip()
    device: Optional[int] = int(raw_input) if raw_input.isdigit() else None

    # Start WebSocket server
    server = await websockets.serve(_ws_handler, SERVER_HOST, SERVER_PORT)
    print(f"[*] WebSocket server listening on ws://{SERVER_HOST}:{SERVER_PORT}")

    # Launch Cloudflare Quick Tunnel
    tunnel_https = await _start_tunnel(SERVER_PORT)
    if tunnel_https:
        wss_url = tunnel_https.replace("https://", "wss://")
        banner  = "─" * 60
        print(f"\n{banner}")
        print(f"  Enter this URL in the CC Intercom script:")
        print(f"  {wss_url}")
        print(f"{banner}\n")
    else:
        print("[!] Running without a public tunnel.")
        print(f"    CC must reach this PC directly at ws://{SERVER_HOST}:{SERVER_PORT}\n")

    # Background broadcast task
    asyncio.create_task(_broadcast_loop())

    # Open microphone stream (non-blocking; callback fires in sounddevice thread)
    print("[*] Microphone active – streaming to any connected CC computers.")
    print("    Press Ctrl+C to stop.\n")
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=CHUNK_FRAMES,
        device=device,
        callback=_audio_callback,
    ):
        try:
            await asyncio.Future()          # run until interrupted
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass

    print("\n[*] Shutting down …")
    server.close()
    await server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
