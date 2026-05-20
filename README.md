# CC Voice Chat

Stream your microphone audio into ComputerCraft speakers in real-time using a Cloudflare Quick Tunnel.

```
[Your PC mic] → Python server → Cloudflare Tunnel → CC WebSocket → Speaker
```

---

## Requirements

| Component | Requirement |
|-----------|-------------|
| Python | 3.8 or newer |
| Minecraft | CC:Tweaked 1.100+ (Minecraft 1.19+) |
| In-game | A **Speaker** block attached to your ComputerCraft computer |
| Tool | [`cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) on your system PATH |

---

## Setup

### 1 — Install cloudflared

Download the Windows binary from the Cloudflare page above and place `cloudflared.exe` somewhere on your PATH (e.g. `C:\Windows\System32` or any folder in your PATH).  
No account or login is needed for Quick Tunnels.

### 2 — Start the companion server

Double-click `companion\start.bat`.  
It will:
- Install Python dependencies automatically
- Start the WebSocket server on `ws://localhost:8765`
- Launch `cloudflared` in a second window and print a URL like:

```
https://abc-randomly-generated.trycloudflare.com
```

Keep **both** windows open while playing.

### 3 — Copy the CC script to your computer

Copy `computercraft\voice_client.lua` into your Minecraft save's `computer/<id>/` folder, or use an in-game method like `wget` / `pastebin`.

In-game wget example (if you host the file somewhere):
```
wget https://your-host/voice_client.lua voice_client.lua
```

### 4 — Run the CC script

On your ComputerCraft computer (with a Speaker attached):
```
voice_client
```

When prompted, paste the `wss://` URL from the cloudflared window (replace `https://` with `wss://`):

```
URL> wss://abc-randomly-generated.trycloudflare.com
```

The URL is saved to `voice_url.txt` and reused on next run.

---

## Server config (multiplayer)

If you are on a server, the server admin must allow WebSocket connections in `computercraft-tweaked.toml`:

```toml
[http]
    enabled = true
    websocket_enabled = true
    # Allow all outbound connections (default); or add the Cloudflare domain explicitly:
    # rules = [{ host = "*.trycloudflare.com", action = "allow" }]
```

---

## Audio details

| Property | Value |
|----------|-------|
| Sample rate | 48 000 Hz |
| Channels | Mono |
| Bit depth | 8-bit signed PCM |
| Chunk size | 4 800 samples (100 ms) |

---

## Troubleshooting

**"No Speaker peripheral found"**  
→ Make sure a Speaker block is placed directly adjacent to (or wired to) your CC computer.

**"WebSocket connection failed"**  
→ Check the cloudflared window is still running and the URL matches exactly.  
→ Ensure `http.websocket_enabled = true` in the server config.

**Choppy / delayed audio**  
→ Try reducing chunk size in `server.py` (`CHUNK_SAMPLES = 2400` for 50 ms).  
→ Ensure a stable internet connection — Quick Tunnels route through Cloudflare's global network.

**Wrong microphone**  
→ Change the default recording device in Windows Sound Settings → Recording.

---

## File structure

```
ccvc/
├── companion/
│   ├── server.py          # Python WebSocket + mic capture server
│   ├── requirements.txt   # Python dependencies
│   └── start.bat          # One-click launcher (Windows)
├── computercraft/
│   └── voice_client.lua   # CC:Tweaked script
└── README.md
```
