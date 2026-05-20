-- Simple HTTP/WebSocket connectivity test for ComputerCraft
-- Tests basic HTTP, HTTPS, and WebSocket connectivity

local function test(name, fn)
    io.write(name .. "... ")
    local ok, err = pcall(fn)
    if ok then
        print("OK")
        return true
    else
        print("FAIL: " .. tostring(err))
        return false
    end
end

print("=== CC Network Test ===\n")

local http_ok = test("HTTP enabled", function()
    local res = http.get("http://httpbin.org/get")
    if not res then error("HTTP get returned nil") end
    res.close()
end)

local https_ok = test("HTTPS enabled", function()
    local res = http.get("https://httpbin.org/get")
    if not res then error("HTTPS get returned nil") end
    res.close()
end)

local ws_ok = test("WebSocket support", function()
    if not http.websocket then error("http.websocket not available") end
end)

print()

if http_ok and https_ok and ws_ok then
    print("✓ All tests passed!")
    print()
    print("Now test the actual tunnel URL:")
    io.write("Paste wss:// URL and press Enter: ")
    local url = io.read()
    
    if url ~= "" then
        io.write("Connecting to " .. url .. "... ")
        local ok, ws = pcall(http.websocket, url)
        if ok and ws then
            print("OK")
            print("✓ WebSocket connection successful!")
            ws.close()
        else
            print("FAIL")
            print("Error: " .. tostring(ws))
        end
    end
else
    print("✗ Some tests failed. Check your server config.")
end
