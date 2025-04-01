-- Panel class to handle creation, dragging, and rendering of panels
Panel = {}
Panel.__index = Panel

function Panel.new(x, y, width, height, color, inside)
    local self = setmetatable({}, Panel)
    self.x = x
    self.y = y
    self.width = width
    self.height = height
    self.color = color
    self.is_dragging = false
    self.drag_offset_x = 0
    self.drag_offset_y = 0
    self.inside = inside or nil
    return self
end

function Panel:update_box(x,y,width,height)
    self.x = x
    self.y = y
    self.width = width
    self.height = height
end

function Panel:draw()
    love.graphics.setColor(self.color)
    love.graphics.rectangle("fill", self.x, self.y, self.width, self.height)
    if self.inside ~= nil then  -- Access self.inside instead of just inside
        self.inside:draw()  -- Call draw method on inputBox (self.inside)
    end
end

return Panel
