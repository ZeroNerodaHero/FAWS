local Widgets = {}
Widgets.__index = Widgets
function Widgets.new()
    local self = setmetatable({}, Widgets)
    self.WidgetList = {}
    self.WidgetMap = {}
    return self
end
function Widgets:add(name, widget, zLevel)
    zLevel = zLevel or 1
    if self.WidgetList[zLevel] == nil then
        self.WidgetList[zLevel] = {}
    end
    self.WidgetList[zLevel][name] = widget
    self.WidgetMap[name] = zLevel 
end
function Widgets:get(name)
    if self.WidgetMap[name] == nil then
        return nil
    end
    local zLevel = self.WidgetMap[name]
    return self.WidgetList[zLevel][name]
end
function Widgets:draw()
    for level,tb in pairs(self.WidgetList) do
        for name, value in pairs(tb) do
            value:draw()
        end
    end

end
return Widgets
