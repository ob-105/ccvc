"""
CC Voice Chat - Companion Server
Captures microphone audio and streams it to ComputerCraft via WebSocket.

Requirements: Python 3.8+, see requirements.txt
Usage:
    1. pip install -r requirements.txt
    2. python server.py
    3. In a separate terminal: cloudflared tunnel --url http://localhost:8765
    4. Copy the wss:// URL into the CC script
"""

import asyncio
import sys
import numpy as np
import sounddevice as sd
import websockets

SAMPLE_RATE  = 48000   # Hz — CC speaker.playAudio expects 48 kHz
CHANNELS     = 1       # Mono
CHUNK_SAMPLES = 4800   # 100 ms per chunk (latency vs. overhead balance)
PORT         = 8765

# --- Shared state (set once the event loop is running) ---
_connected: set = set()
_loop: asyncio.AbstractEventLoop | None = None
_queue: asyncio.Queue | None = None


# ---------------------------------------------------------------------------
# sounddevice callback — runs in a C audio thread
# ---------------------------------------------------------------------------
def _audio_callback(indata, frames, time_info, status):
    if status:
        print(f"[mic] {status}", flush=True)
    if not _loop or not _queue:
        return
    # Convert float32 [-1, 1] → int8 [-128, 127]
    samples: bytes = np.clip(indata[:, 0] * 127.0, -128, 127).astype(np.int8).tobytes()
    # Thread-safe hand-off to the asyncio event loop
    _loop.call_soon_threadsafe(_enqueue, samples)


def _enqueue(data: bytes):
    if _queue and not _queue.full():
        _queue.put_nowait(data)
    # If full (lagging client), silently drop — avoids unbounded buffering


# ---------------------------------------------------------------------------
# Async broadcast loop — sends queued chunks to every connected CC client
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# WebSocket connection handler
# ---------------------------------------------------------------------------
async def _handler(websocket):
    addr = websocket.remote_address
    print(f"[+] ComputerCraft connected  — {addr}")
    _connected.add(websocket)
    try:
        # Keep the handler alive; we don't expect inbound messages from CC
        async for _ in websocket:
            pass
    except Exception:
        pass
    finally:
        _connected.discard(websocket)
        print(f"[-] ComputerCraft disconnected — {addr}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def main():
    global _loop, _queue
    _loop  = asyncio.get_running_loop()
    _queue = asyncio.Queue(maxsize=100)  # ~10 s of audio max before dropping

    print("CC Voice Chat — Companion Server")
    print("=================================")
    print(f"WebSocket listening on  ws://localhost:{PORT}")
    print()
    print("Expose to ComputerCraft via Cloudflare Quick Tunnel:")
    print(f"   cloudflared tunnel --url http://localhost:{PORT}")
    print()
    print("Copy the  wss://xxxx.trycloudflare.com  URL into the CC script.")
    print()

    # List available input devices to help the user pick
    try:
        devices = sd.query_devices()
        default_in = sd.default.device[0]
        print(f"Using microphone: {devices[default_in]['name']}")
        print("(Change default mic in Windows Sound Settings if needed)")
    except Exception:
        pass

    print()

    # Start audio capture
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        blocksize=CHUNK_SAMPLES,
        callback=_audio_callback,
    ):
        print(f"Microphone open at {SAMPLE_RATE} Hz. Waiting for ComputerCraft...")
        print("Press Ctrl+C to stop.\n")

        broadcast_task = asyncio.create_task(_broadcast_loop())

        async with websockets.serve(_handler, "0.0.0.0", PORT):
            try:
                await asyncio.Future()  # run forever
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass

        broadcast_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)
