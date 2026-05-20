-- test_speaker.lua
-- Quick hardware and audio sanity test for CC:Tweaked speakers.

term.clear()
term.setCursorPos(1, 1)
print("CC Speaker Test")
print("---------------")

local function list_peripherals()
    print("Peripherals by side:")
    for _, side in ipairs(rs.getSides()) do
        local ptype = peripheral.getType(side)
        if ptype then
            print(string.format("  %-6s : %s", side, ptype))
        else
            print(string.format("  %-6s : (none)", side))
        end
    end
    print("")
end

list_peripherals()

local speaker = peripheral.find("speaker")
if not speaker then
    printError("No speaker peripheral found.")
    printError("Attach a Speaker block directly to the computer.")
    return
end

print("Speaker found. Running tests...")
print("")

-- Test 1: noteblock note
local ok_note = speaker.playNote("harp", 3.0, 12)
print("Test 1 (playNote):", ok_note and "OK" or "FAILED")
os.sleep(0.3)

-- Test 2: Minecraft sound event
local ok_sound = speaker.playSound("minecraft:block.note_block.harp", 3.0, 1.0)
print("Test 2 (playSound):", ok_sound and "OK" or "FAILED")
os.sleep(0.5)

-- Test 3: 8-bit PCM tone via playAudio (48 kHz)
local function make_tone(freq_hz, duration_s, volume)
    local samples = {}
    local sample_rate = 48000
    local count = math.floor(sample_rate * duration_s)
    for i = 1, count do
        local t = (i - 1) / sample_rate
        local v = math.sin(2 * math.pi * freq_hz * t)
        local amp = math.floor(v * (127 * volume))
        if amp > 127 then amp = 127 end
        if amp < -128 then amp = -128 end
        samples[i] = amp
    end
    return samples
end

local tone = make_tone(440, 0.25, 0.8)
while not speaker.playAudio(tone, 1.0) do
    os.pullEvent("speaker_audio_empty")
end
print("Test 3 (playAudio): OK if you heard a short tone")

print("")
print("Done.")
print("If all tests say OK but you hear nothing:")
print("1) Increase Minecraft Master and Blocks/Note Blocks volume")
print("2) Move your player closer to the speaker block")
