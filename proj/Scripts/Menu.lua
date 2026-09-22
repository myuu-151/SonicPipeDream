-- Menu.lua
-- The title menu, after external/ui/menu/imaged.png:
--
--     [SONIC PIPE DREAM]
--                                       +-----------+
--      > Main Game                      |  preview  |
--        Marathon   (locked)            +-----------+
--        Records    (not written)        SPECIAL STAGE
--        Options    (not written)
--                                        (A) Select  (B) Back
--     SONIC PIPE DREAM  (watermark)
--
-- Attach to a Canvas. It builds its own widgets as children, like SpecialStageUI, so there
-- is nothing to lay out in the editor. Every piece is a texture cut from the mockup by
-- external/ui/menu/split_menu.py and cooked by native/gen_menu_assets.py, which also writes
-- MenuLayout.lua: where each piece goes on the mockup's own 522 x 386 screen. This scales
-- that to the window, so the menu is the picture that was drawn at any size.
--
-- What it does NOT draw is a background above panel_top: the mockup left that transparent,
-- and the sky dome shows through it.
--
--     TheMenu:Open()          show it (and take the input)
--     TheMenu:Close()         hide it
--     TheMenu.onChoose        called with "main_game" / "marathon" / ... when A is pressed
--     TheMenu:SetUnlocked(k, true)    light a locked item up
--
-- Marathon is locked until the seventh emerald; Records and Options are locked because they
-- do not exist. A locked item can be walked onto -- it is part of the picture -- but A does
-- nothing on it.

Menu = {}

Script.Require("MenuLayout")            -- where every piece goes; written by gen_menu_assets.py

local WHITE = Vec(1.0, 1.0, 1.0, 1.0)

-- Which items can be chosen. Marathon is switched on by the game when the gauntlet is done.
local UNLOCKED = { main_game = true, marathon = false, records = false, options = false }

local REPEAT_FIRST, REPEAT_AFTER = 0.40, 0.12       -- held up/down: the first wait, then the rest

local BLINK = 0.45                      -- seconds the cursor is on, and off again

-- The watermark scrolls, and wraps: copies of the same art in a row, moving left, each one
-- coming back round when it has gone. The art fills its picture edge to edge with no margin,
-- so a gap is put between copies or DREAM would run straight into the next SONIC.
local MARK_SPEED = 22.0                 -- mockup pixels a second
local MARK_GAP = 60.0                   -- between one SONIC PIPE DREAM and the next
local MARK_COPIES = 6                   -- enough to cross any window; the spare ones hide


local function MakeQuad(parent, texture)
    local q = parent:CreateChild("Quad")
    q:SetAnchorMode(AnchorMode.TopLeft)
    if (texture ~= nil) then q:SetTexture(texture) end
    q:SetColor(WHITE)
    return q
end

function Menu:Create()
    self.built = false
    self.index = 1
    self.open = true
    self.held = 0.0
    self.unlocked = {}
    for k, v in pairs(UNLOCKED) do self.unlocked[k] = v end
    TheMenu = self
end

function Menu:Build()
    local L = MenuLayout
    self.quads = {}
    -- Back to front: the panel, then what sits on it.
    -- No picture on this screen: the frame, the stage shot, the emerald and its label belong
    -- to the stage select, where there is a stage for them to be about.
    for _, name in ipairs({ "T_Menu_Panel", "T_Menu_Circles" }) do
        self.quads[name] = MakeQuad(self, LoadAsset(name))
    end
    self:BuildWatermark()               -- over the panel, under everything else
    for _, name in ipairs({ "T_Menu_TitleBanner", "T_Menu_TitleText", "T_Menu_SelectBar",
                            "T_Menu_ButtonA", "T_Menu_LabelSelect",
                            "T_Menu_ButtonB", "T_Menu_LabelBack", "T_Menu_Cursor" }) do
        self.quads[name] = MakeQuad(self, LoadAsset(name))
    end

    -- the four items, each with a lit and a greyed texture
    self.items, self.itemQuads = {}, {}
    for i, key in ipairs(L.items) do
        local name = "T_Menu_Item" .. i
        self.items[i] = { key = key, name = name,
                          on = LoadAsset(name), off = LoadAsset(name .. "_Off") }
        self.itemQuads[i] = MakeQuad(self, self.items[i].on)
    end

    self.built = true
    self:Refresh()
    self:Layout()
end

-- ------------------------------------------------------------------ layout
function Menu:Place(quad, p)
    -- The whole texture goes in a rectangle scaled by canvas/art, so the art lands on
    -- (x, y, w, h) and the power-of-two padding falls outside it. See MenuLayout.lua.
    local k = self.k
    quad:SetPosition(self.left + p.x * k, self.top + p.y * k)
    quad:SetDimensions(p.w * k * p.cw / p.aw, p.h * k * p.ch / p.ah)
end

function Menu:Layout()
    if (not self.built) then return end
    local L = MenuLayout
    local res = Renderer.GetScreenResolution()
    local width, height = res.x, res.y

    if (self.SetDimensions ~= nil) then
        self:SetAnchorMode(AnchorMode.TopLeft)
        self:SetPosition(0.0, 0.0)
        self:SetDimensions(width, height)
    end
    self.layoutSize = { w = width, h = height }

    -- Fit the drawn screen inside the window, as SpecialStageUI does: by the height on a wide
    -- window, by the width on a narrow one.
    self.k = math.min(height / L.screen.h, width / L.screen.w)
    self.left = (width - L.screen.w * self.k) * 0.5
    self.top = (height - L.screen.h * self.k) * 0.5

    for name, quad in pairs(self.quads) do self:Place(quad, L.parts[name]) end
    -- The panel is one column of colours stretched sideways: make it reach both edges of the
    -- window, however wide that is, so no bar of sky shows down the side.
    local panel = L.parts.T_Menu_Panel
    self.quads.T_Menu_Panel:SetPosition(0.0, self.top + panel.y * self.k)
    self.quads.T_Menu_Panel:SetDimensions(width, panel.h * self.k * panel.ch / panel.ah)

    for i, quad in ipairs(self.itemQuads) do self:Place(quad, L.parts[self.items[i].name]) end
    self:PlaceWatermark()
    self:PlaceSelection()
end

-- The bar and the arrow follow the chosen item: the mockup drew them on the first row, so
-- they move by the difference between that row's y and this one's.
function Menu:PlaceSelection()
    local L = MenuLayout
    local first = L.parts[self.items[1].name]
    local here = L.parts[self.items[self.index].name]
    local dy = (here.y + here.h * 0.5) - (first.y + first.h * 0.5)

    local bar = L.parts.T_Menu_SelectBar
    self.quads.T_Menu_SelectBar:SetPosition(self.left + bar.x * self.k, self.top + (bar.y + dy) * self.k)
    local cur = L.parts.T_Menu_Cursor
    self.quads.T_Menu_Cursor:SetPosition(self.left + cur.x * self.k, self.top + (cur.y + dy) * self.k)
end


-- ------------------------------------------------------------------ the scrolling watermark
function Menu:BuildWatermark()
    self.mark, self.markAt = {}, 0.0
    for i = 1, MARK_COPIES do
        self.mark[i] = MakeQuad(self, LoadAsset("T_Menu_Watermark"))
    end
end

function Menu:PlaceWatermark()
    if (self.mark == nil or self.k == nil) then return end
    local p = MenuLayout.parts.T_Menu_Watermark
    local period = (p.w + MARK_GAP) * self.k
    local width = (self.layoutSize ~= nil) and self.layoutSize.w or 0.0
    local wanted = math.min(MARK_COPIES, math.ceil(width / period) + 1)
    -- The run starts one whole copy to the left of the window, so a copy is always coming in
    -- as another goes out. p.x is where the mockup put it, a little off the left edge.
    local start = p.x * self.k - period + (self.markAt % period)
    for i, quad in ipairs(self.mark) do
        local on = (self.open ~= false) and i <= wanted
        quad:SetVisible(on)
        if (on) then
            quad:SetPosition(start + (i - 1) * period, self.top + p.y * self.k)
            quad:SetDimensions(p.w * self.k * p.cw / p.aw, p.h * self.k * p.ch / p.ah)
        end
    end
end

-- The cursor blinks, so the eye goes to the row it is on.
function Menu:BlinkCursor(deltaTime)
    local arrow = self.quads.T_Menu_Cursor
    if (arrow == nil) then return end
    self.blinkAt = (self.blinkAt or 0.0) + deltaTime
    arrow:SetVisible(self.open and (self.blinkAt % (BLINK * 2.0)) < BLINK)
end

function Menu:ScrollWatermark(deltaTime)
    if (self.mark == nil or self.k == nil) then return end
    local p = MenuLayout.parts.T_Menu_Watermark
    local period = (p.w + MARK_GAP) * self.k
    self.markAt = (self.markAt - MARK_SPEED * self.k * deltaTime) % period
    self:PlaceWatermark()
end

-- ------------------------------------------------------------------ state
function Menu:Refresh()
    for i, item in ipairs(self.items) do
        local lit = self.unlocked[item.key]
        self.itemQuads[i]:SetTexture(lit and item.on or (item.off or item.on))
    end
end

function Menu:SetUnlocked(key, on)
    self.unlocked[key] = on and true or false
    if (self.built) then self:Refresh() end
end

function Menu:Show(visible)
    if (visible and not self.open) then self.armed = false end
    self.open = visible and true or false
    if (not self.built) then return end
    for _, quad in pairs(self.quads) do quad:SetVisible(self.open) end
    for _, quad in ipairs(self.itemQuads) do quad:SetVisible(self.open) end
    self:PlaceWatermark()
end

function Menu:Open() self:Show(true) end
function Menu:Close() self:Show(false) end

-- The menus' own sounds: the highlight moving (MenuMove), a menu going on to the next
-- (MenuSelect), and a stage chosen (MenuWarp). (For a while the menu borrowed the stage's
-- ring and checkpoint, and they were the wrong sounds for it.)
function MenuSound(name, volume)
    MenuSounds = MenuSounds or {}
    if (MenuSounds[name] == nil) then MenuSounds[name] = LoadAsset("SW_" .. name) or false end
    if (MenuSounds[name]) then Audio.PlaySound2D(MenuSounds[name], volume or 0.6) end
end

function Menu:Move(by)
    self.index = self.index + by
    if (self.index < 1) then self.index = #self.items end
    if (self.index > #self.items) then self.index = 1 end
    self:PlaceSelection()
    MenuSound("MenuMove")
end

function Menu:Choose()
    local item = self.items[self.index]
    if (not self.unlocked[item.key]) then return end        -- a locked row does nothing
    MenuSound("MenuSelect", 0.7)
    if (self.onChoose ~= nil) then self.onChoose(item.key) end
end


-- A screen that has just opened must not act on the very key that opened it. Both screens
-- tick in the same frame, so the Enter that chose Main Game was still "just down" when the
-- stage select ticked a moment later, and it chose stage 1 with it. A screen is not armed
-- until it sees the confirm keys released.
function Menu:Armed()
    if (self.armed) then return true end
    if (not Input.IsKeyDown(Key.Enter) and not Input.IsKeyDown(Key.Space)) then
        self.armed = true
    end
    return false
end

-- ------------------------------------------------------------------ every frame
function Menu:Tick(deltaTime)
    if (not self.built) then self:Build() end
    -- For testing without a keyboard: S2_MENU_CHOOSE=main_game picks that row straight away.
    if (self.autoChoose == nil) then
        self.autoChoose = (os ~= nil and os.getenv ~= nil and os.getenv("S2_MENU_CHOOSE")) or false
        if (self.autoChoose) then
            for i, item in ipairs(self.items) do
                if (item.key == self.autoChoose) then self.index = i end
            end
            self:PlaceSelection()
            self:Choose()
        end
    end
    local res = Renderer.GetScreenResolution()
    if (self.layoutSize == nil or res.x ~= self.layoutSize.w or res.y ~= self.layoutSize.h) then
        self:Layout()
    end
    if (not self.open) then return end
    self:ScrollWatermark(deltaTime)
    self:BlinkCursor(deltaTime)

    local up = Input.IsKeyDown(Key.Up) or Input.IsKeyDown(Key.W)
    local down = Input.IsKeyDown(Key.Down) or Input.IsKeyDown(Key.S)
    local by = (down and 1 or 0) - (up and 1 or 0)
    if (by == 0) then
        self.held, self.repeating = 0.0, false
    else
        self.held = self.held - deltaTime
        if (self.held <= 0.0) then
            self:Move(by)
            self.held = self.repeating and REPEAT_AFTER or REPEAT_FIRST
            self.repeating = true
        end
    end

    -- See Armed: a screen ignores the key that opened it.
    if (not self:Armed()) then return end
    if (Input.IsKeyJustDown(Key.Enter) or Input.IsKeyJustDown(Key.Space)) then self:Choose() end
end
