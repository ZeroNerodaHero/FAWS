local InputBox = {}
InputBox.__index = InputBox

local shiftSymbols = {
    ["1"] = "!", ["2"] = "@", ["3"] = "#", ["4"] = "$", ["5"] = "%",
    ["6"] = "^", ["7"] = "&", ["8"] = "*", ["9"] = "(", ["0"] = ")",
    ["-"] = "_", ["="] = "+", ["["] = "{", ["]"] = "}", [";"] = ":",
    ["'"] = "\"", ["\\"] = "|", [","] = "<", ["."] = ">", ["/"] = "?",
    ["`"] = "~"
}

function InputBox.new(x, y, width, height)
    local self = setmetatable({}, InputBox)
    self.x = x
    self.y = y
    self.width = width
    self.height = height
    self.text = ""
    self.active = false
    self.cursorPos = 1
    return self
end

function InputBox:update_size(width,height)
    self.width = width
    self.height = height
end 

function InputBox:keypressed(key,shiftPressed)
    if self.active then
        print("Key pressed: " .. key)

        -- Handle backspace (delete text)
        if key == "backspace" then
            if self.cursorPos > 1 then
                self.text = self.text:sub(1, self.cursorPos - 2) .. self.text:sub(self.cursorPos)
                self.cursorPos = self.cursorPos - 1
            end
        elseif #key == 1 or key == "space" then
            local char = (key == "space") and " " or key
        
            -- Convert to uppercase if Shift is pressed
            if shiftPressed and key:match("[a-z]") then
                char = key:upper()
            end
            if shiftPressed and shiftSymbols[key] then
                char = shiftSymbols[key]
            end

            self.text = self.text:sub(1, self.cursorPos - 1) .. char .. self.text:sub(self.cursorPos)
            self.cursorPos = self.cursorPos + 1
        end
        --cursor movement
        if key == "left" then
            if self.cursorPos > 1 then
                self.cursorPos = self.cursorPos - 1
            end
        elseif key == "right" then
            if self.cursorPos <= #self.text then
                self.cursorPos = self.cursorPos + 1
            end
        end
    end

end

function InputBox:draw()
    -- Draw the input box
    love.graphics.setColor(1, 1, 1) -- White color
    love.graphics.rectangle("line", self.x, self.y, self.width, self.height)

    -- Draw the text inside the input box
    love.graphics.print(self.text, self.x + 5, self.y + 5)

    -- Draw the cursor at the current text position
    if self.active then
        local cursorX = self.x + 5 + love.graphics.getFont():getWidth(self.text:sub(1, self.cursorPos - 1))
        --controls font
        love.graphics.line(cursorX, self.y + 5, cursorX, self.y + 30)
    end
end

function InputBox:mousepressed(x, y, button)
    if button == 1 then
        if x >= self.x and x <= self.x + self.width and y >= self.y and y <= self.y + self.height then
            self.active = true
        else
            self.active = false
        end
    end
end

return InputBox

