# CC Intercom

One-way voice intercom: your PC microphone → ComputerCraft speaker.  
A Cloudflare Quick Tunnel is created automatically so the CC computer can connect from any world, server, or machine without port-forwarding.

```
[ PC microphone ]
       │  sounddevice (48 kHz PCM)
       ▼
[ Python companion app ]
       │  WebSocket (binary PCM frames)
       ▼
[ Cloudflare Quick Tunnel ]  ──  wss://xxxx.trycloudflare.com
       │
       ▼
[ CC computer ] → speaker.playAudio()
```

---

## Requirements

### PC side

| Requirement | Notes |
|---|---|
| Python 3.10+ | |
| `cloudflared` binary | [Download here](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) – add it to your `PATH` |

### Minecraft / CC side

| Requirement | Notes |
|---|---|
| CC: Tweaked **≥ 1.100.0** | Needed for `speaker.playAudio` |
| **Speaker** peripheral | Attach one to (or place adjacent to) the computer |
| HTTP enabled | Default in most modpacks; check `computercraft.toml` if unsure |

---

## Setup

### 1 – Install Python dependencies

```powershell
cd companion
pip install -r requirements.txt
```

### 2 – Install cloudflared

Download the Windows executable from the link above and either:
- place it in a folder that is already on your `PATH`, or
- add its folder to `PATH` via *System → Advanced → Environment Variables*.

Verify with:

```powershell
cloudflared --version
```

### 3 – Copy the Lua script to your CC computer

Options:
- **Pastebin** – upload `computercraft/intercom.lua` and run `pastebin get <id> intercom` in-game.
- **Singleplayer / LAN** – use a mod like [CC: Remote Files](https://modrinth.com/mod/cc-remote) or copy the file directly into the computer's save folder:
  `saves/<world>/computercraft/computer/<id>/intercom.lua`

---

## Running

### Step 1 – Start the companion app (PC)

```powershell
cd companion
python intercom_server.py
```

It will:
1. List available microphone devices and ask you to choose one.
2. Start a local WebSocket server on port `8765`.
3. Launch a Cloudflare Quick Tunnel and print a URL like:

```
────────────────────────────────────────────────────────────
  Enter this URL in the CC Intercom script:
  wss://random-words-here.trycloudflare.com
────────────────────────────────────────────────────────────
```

> The tunnel URL changes every time you restart the app.

### Step 2 – Run the Lua script in-game

```
intercom
```

Paste the `wss://` URL when prompted and press Enter.  
Audio from your microphone will play through the in-game speaker in real time.

Press **Ctrl+T** in-game to disconnect.  
Press **Ctrl+C** in the companion app terminal to stop streaming.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No speaker peripheral found` | Attach a Speaker block to the computer (any side) |
| `Connection failed: …` | Make sure the companion app is running and the URL was copied correctly |
| Audio plays too fast / wrong pitch | You are using a CC: Tweaked version older than 1.100 that does not support `speaker.playAudio` with PCM data |
| Choppy audio | Your network latency to the Cloudflare PoP is high; try reducing `CHUNK_FRAMES` in `intercom_server.py` to `2400` (50 ms chunks) |
| `cloudflared` not found | Ensure the binary is in `PATH` and the terminal session was restarted after updating `PATH` |
| Audio input device not listed | Check Windows sound settings; make sure the mic is not disabled |

---

## File layout

```
ccvc/
├── companion/
│   ├── intercom_server.py   # Python companion app
│   └── requirements.txt
└── computercraft/
    └── intercom.lua         # CC: Tweaked client script
```
