local json = require("dkjson")
local filepath = "config.json"

local function getConfig()
    local file = love.filesystem.read(filepath)
    if not file then
        error("Could not read the file: " .. filepath)
    end
    local data, _, err = json.decode(file, 1, nil)
    if err then
        error("JSON Decode Error: " .. err)
    end
    return data
end

local function updateConfig(keyPath, value)
    local data = getConfig()
    
    local keys = {}
    for key in keyPath:gmatch("[^%.]+") do
        table.insert(keys, key)
    end

    local current = data
    for i = 1, #keys - 1 do
        local k = keys[i]
        if not current[k] then
            error("Invalid key path: " .. keyPath)
        end
        current = current[k]
    end
    
    current[keys[#keys]] = value

    local jsonData = json.encode(data, { indent = true })
    local success = love.filesystem.write(filepath, jsonData)
    if not success then
        error("Failed to write updated JSON to file: " .. filepath)
    end
end

function printTable(tbl, indent)
    indent = indent or 0
    local prefix = string.rep("  ", indent)

    for k, v in pairs(tbl) do
        if type(v) == "table" then
            print(prefix .. tostring(k) .. " = {")
            printTable(v, indent + 1)
            print(prefix .. "}")
        else
            print(prefix .. tostring(k) .. " = " .. tostring(v))
        end
    end
end


return {
    getConfig = getConfig,
    updateConfig = updateConfig,
    printTable = printTable
}


