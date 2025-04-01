local InputBox = require("inputbox")  -- Import the inputbox.lua file
local Label = require("label")
local configer = require("configer")
local Panel = require("panel")
local Widgets = require("widgets")
    
local widgets
local config

local inputBox
local panel1, panel2
local title

function love.load()
    config = configer.getConfig()
    printTable(config)

    window_width = config.window.width
    window_height = config.window.height
    tiling = config.tiling.left
    margin = config.box.margin

    love.window.setMode(window_width, window_height,{resizable = true})  
    love.window.setTitle("FuckAnotherWritingSoftware")

    inputBox = InputBox.new(margin, margin, window_width*tiling-2*margin, window_height-2*margin)
    panel1 = Panel.new(0, 0, window_width * tiling, window_height, {1, 0, 0}, inputBox)  
    panel2 = Panel.new(window_width * tiling, 0, window_width * (1-tiling), window_height, {0, 0, 1})  

    local font_size = 20
    local font = love.graphics.newFont(font_size)
    label = Label.new("FileName.txt", margin, window_height-font_size-margin, font, {1, 1, 1})

    widgets = Widgets.new()
    widgets:add("writing_box",inputBox)
    widgets:add("left_panel",panel1)
    widgets:add("right_panel",panel2)
    widgets:add("file_label",label,2)
end

function love.resize(w, h)
    print("Window resized to: " .. w .. "x" .. h)
    config.window.width = w 
    config.window.height= h 
    configer.updateConfig("window.width", w)
    configer.updateConfig("window.height", h)
    tiling = config.tiling.left
    margin = config.box.margin

    panel1:update_box(0,0,w*tiling,h)   
    panel2:update_box(w*tiling,0,w*(1-tiling),h)   
    inputBox:update_size(w*tiling-2*margin, h-2*margin)
end

function love.mousepressed(x, y, button, istouch, presses)
    if button == 1 then  
        widgets:get("writing_box"):mousepressed(x,y,button)
        print("Mouse pressed at: " .. x .. ", " .. y)
    end
end

function love.keypressed(key, scancode, isrepeat)
    -- Forward the keypress event to the input box
    --inputBox:keypressed(key)
    local shiftPressed = love.keyboard.isDown("lshift") or love.keyboard.isDown("rshift")
    widgets:get("writing_box"):keypressed(key, shiftPressed)
end

function love.update(dt)
end

function love.draw()
    widgets:draw()
end


