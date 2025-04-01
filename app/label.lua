-- labels bc why not
Label = {}
Label.__index = Label

function Label.new(text, x, y, font, color)
    local self = setmetatable({}, Label)
    self.text = text or "Label"
    self.x = x or 0
    self.y = y or 0
    self.font = font or love.graphics.newFont(14)
    self.color = color or {1, 1, 1, 1}  -- White with full opacity (RGBA)
    return self
end

function Label:draw()
    love.graphics.setFont(self.font)
    love.graphics.setColor(self.color)
    love.graphics.print(self.text, self.x, self.y)
end

function Label:setText(newText)
    self.text = newText
end

function Label:setPosition(x, y)
    self.x = x
    self.y = y
end

function Label:setColor(r, g, b, a)
    self.color = {r or 1, g or 1, b or 1, a or 1}
end

function Label:setFont(newFont)
    self.font = newFont
end

return Label
