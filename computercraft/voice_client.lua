-- ============================================================
--  CC Voice Chat Client  —  voice_client.lua
--  Receives raw PCM audio from the companion server and plays
--  it through an attached Speaker peripheral in real-time.
--
--  Requires:
--    • CC:Tweaked 1.100+ (speaker.playAudio support)
--    • A Speaker block wired to this computer
--    • HTTP + WebSocket enabled on the server (default)
-- ============================================================

local CONFIG_FILE = "voice_url.txt"

-- ── Helpers ─────────────────────────────────────────────────

local function trim(s)
    return s:match("^%s*(.-)%s*$")
end

local function readConfig()
    if not fs.exists(CONFIG_FILE) then return nil end
    local f = fs.open(CONFIG_FILE, "r")
    local line = f.readLine()
    f.close()
    return line and trim(line) ~= "" and trim(line) or nil
end

local function saveConfig(url)
    local f = fs.open(CONFIG_FILE, "w")
    f.writeLine(url)
    f.close()
end

local function ensureScheme(url)
    if not url:match("^wss?://") then
        return "wss://" .. url
    end
    return url
end

-- ── Startup ──────────────────────────────────────────────────

term.clear()
term.setCursorPos(1, 1)
print("=== CC Voice Chat Client ===")
print()

-- Find speaker
local speaker = peripheral.find("speaker")
if not speaker then
    error("No Speaker peripheral found!\n"
        .. "Attach a Speaker block to this computer, then rerun.", 0)
end

if not speaker.playAudio then
    error("speaker.playAudio not available.\n"
        .. "Requires CC:Tweaked 1.100+ (Minecraft 1.19+).", 0)
end

-- Get / prompt for server URL
local url = readConfig()

if url then
    print("Saved URL: " .. url)
    io.write("Use this URL? [Y/n]: ")
    local ans = trim(io.read())
    if ans:lower() == "n" then
        url = nil
        fs.delete(CONFIG_FILE)
    end
end

if not url then
    print()
    print("Paste your Cloudflare Quick Tunnel URL.")
    print("Example:  wss://abc-def-123.trycloudflare.com")
    print("(HTTP or HTTPS host also accepted — wss:// added automatically)")
    print()
    io.write("URL> ")
    url = trim(io.read())
    if url == "" then
        error("No URL provided.", 0)
    end
    url = ensureScheme(url)
    saveConfig(url)
    print("URL saved to " .. CONFIG_FILE)
end

url = ensureScheme(url)

-- ── Connect ──────────────────────────────────────────────────

print()
print("Connecting to:")
print("  " .. url)
print()

local ws, err = http.websocket(url)
if not ws then
    error("WebSocket connection failed:\n  " .. tostring(err)
        .. "\n\nCheck:\n"
        .. "  1. companion server is running\n"
        .. "  2. cloudflared tunnel is active\n"
        .. "  3. URL is correct\n"
        .. "  4. This domain is allowed in server HTTP config", 0)
end

print("Connected!  Audio is streaming.")
print("Volume can be adjusted with the in-game speaker block.")
print("Press Ctrl+T to disconnect.")
print()

-- ── Receive loop ─────────────────────────────────────────────
-- Each message is a binary string of signed 8-bit PCM samples
-- recorded at 48 000 Hz mono by the companion server.

local function receiveLoop()
    while true do
        local msg, isBinary = ws.receive()

        -- nil means the server closed the connection
        if not msg then
            print("Server closed the connection.")
            break
        end

        -- Decode the binary blob into a Lua number table.
        -- msg:byte(1, -1) returns all bytes in one call — much faster
        -- than iterating byte-by-byte.
        local raw = { msg:byte(1, -1) }
        local len = #raw
        local samples = {}

        for i = 1, len do
            local b = raw[i]
            -- Reinterpret unsigned byte [0-255] as signed int8 [-128, 127]
            samples[i] = b >= 128 and (b - 256) or b
        end

        -- Feed samples to the speaker.
        -- playAudio returns false when its internal buffer is full;
        -- we wait for the "speaker_audio_empty" event before retrying.
        while not speaker.playAudio(samples, 3.0) do
            os.pullEvent("speaker_audio_empty")
        end
    end
end

local ok, result = pcall(receiveLoop)
ws.close()

print()
if not ok then
    -- "Terminated" is the normal Ctrl+T shutdown — don't treat as an error
    if tostring(result):find("Terminated") then
        print("Disconnected by user.")
    else
        printError("Error: " .. tostring(result))
    end
else
    print("Disconnected.")
end
