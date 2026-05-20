-- intercom.lua
-- CC:Tweaked Intercom client
--
-- Requirements
--   • Speaker peripheral attached to (or wrapped by) this computer
--   • CC:Tweaked >= 1.100.0  (for speaker.playAudio)
--   • http feature enabled in computercraft.toml / server config
--
-- Usage
--   1. Run the companion app on your PC and note the wss:// URL it prints.
--   2. Run this script on the CC computer.
--   3. Paste the URL when prompted.
--   4. Press Ctrl+T to disconnect.

-- ── Peripheral check ──────────────────────────────────────────────────────────
local speaker = peripheral.find("speaker")
if not speaker then
    printError("No speaker peripheral found.")
    printError("Attach a speaker to this computer and rerun the script.")
    return
end

-- ── UI ────────────────────────────────────────────────────────────────────────
term.clear()
term.setCursorPos(1, 1)
print("+----------------------+")
print("|     CC  Intercom     |")
print("+----------------------+")
print("")
print("Enter the wss:// URL shown")
print("by the companion app:")
write("> ")
local url = read()

if not url or url == "" then
    printError("No URL entered.")
    return
end

-- Normalise: accept https:// URLs too (swap scheme to wss://)
url = url:gsub("^https://", "wss://")

print("")
print("Connecting to:")
print("  " .. url)
print("")

-- ── WebSocket connection ──────────────────────────────────────────────────────
local ws, err = http.websocket(url)
if not ws then
    printError("Connection failed: " .. tostring(err))
    return
end

print("Connected!  Audio streaming.")
print("Press Ctrl+T to disconnect.")
print("")

-- ── PCM decoder ──────────────────────────────────────────────────────────────
-- The companion sends little-endian signed 16-bit PCM at 48 000 Hz.
-- CC's speaker.playAudio expects a table of floats in the range [-1, 1].
local function decode_pcm16(data)
    local n       = math.floor(#data / 2)
    local samples = {}
    for i = 1, n do
        local lo  = data:byte(i * 2 - 1)
        local hi  = data:byte(i * 2)
        local raw = lo + hi * 256            -- unsigned 16-bit
        if raw >= 32768 then
            raw = raw - 65536               -- sign-extend to signed 16-bit
        end
        samples[i] = raw / 32767            -- normalise to [-1, 1]
    end
    return samples
end

-- ── Shared audio buffer (receive thread → playback thread) ───────────────────
local audio_buffer  = {}
local MAX_BUFFERED  = 10   -- drop oldest chunks if we lag this far behind

-- ── Main loop (two parallel coroutines) ──────────────────────────────────────
parallel.waitForAny(

    -- ── Receive coroutine ─────────────────────────────────────────────────────
    function()
        while true do
            local msg, is_binary = ws.receive()

            if msg == nil then
                print("")
                print("Server closed the connection.")
                return
            end

            if is_binary then
                -- Binary frame: raw PCM bytes from the companion app
                local samples = decode_pcm16(msg)
                audio_buffer[#audio_buffer + 1] = samples

                -- Trim oldest chunks if playback falls behind
                while #audio_buffer > MAX_BUFFERED do
                    table.remove(audio_buffer, 1)
                end
            end
            -- Text frames are silently ignored (reserved for future use)
        end
    end,

    -- ── Playback coroutine ────────────────────────────────────────────────────
    function()
        while true do
            if #audio_buffer > 0 then
                local samples = table.remove(audio_buffer, 1)

                -- speaker.playAudio returns false when its internal buffer is
                -- full; wait for it to drain before retrying.
                if not speaker.playAudio(samples) then
                    os.pullEvent("speaker_audio_empty")
                    speaker.playAudio(samples)
                end
            else
                -- Nothing buffered yet; yield briefly so the receive
                -- coroutine gets CPU time.
                os.sleep(0.02)
            end
        end
    end

)

ws.close()
print("Disconnected.")
