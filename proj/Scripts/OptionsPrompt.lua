-- OptionsPrompt.lua
-- A box of settings over the title menu, as SavePrompt.lua's: OPTIONS opens it at its first page,
-- and MARATHON at the marathon's setup, whose START begins the run.
--
--     +--------------------------------------------+
--     |                  MARATHON                  |
--     |                                            |
--     |         ROUNDS                    7        |
--     |         STARTING DIFFICULTY       2        |
--     |         DIFFICULTY CLIMB     NORMAL        |
--     |         RING LENIENCY        NORMAL        |
--     |         LIVES                     1        |
--     |         START                              |
--     |                                            |
--     |           A  CHANGE        B  BACK         |
--     +--------------------------------------------+
--
-- Up and down pick a line; A opens a page, changes a setting or starts; left and right change a
-- setting either way; B goes back a page, and from the first closes. The settings are
-- GameOptions.lua's: they take effect at once and are kept with the save.
--
--     TheOptions:Open(page)   "options" (the default) or "marathon"; the menu keeps still meanwhile
--     TheOptions.onClose      called when it closes (B, or START)
--     TheOptions.onStart      called by the marathon page's START, after it has closed

Script.Require("GameOptions")

OptionsPrompt = {}

-- Blue and yellow on white: never red against green (the owner reads neither apart).
local WHITE = Vec(1.0, 1.0, 1.0, 1.0)
local YELLOW = Vec(1.0, 0.84, 0.18, 1.0)
local SKY = Vec(0.45, 0.78, 1.0, 1.0)
local DIM = Vec(0.0, 0.0, 0.0, 0.55)
local BOX = Vec(0.02, 0.10, 0.42, 0.94)
local EDGE = Vec(0.45, 0.78, 1.0, 1.0)

-- Sized for a 480-line screen (the GameCube's), and scaled up with the window on the PC.
local REF_H = 480.0
local BOX_W = 560.0
local FIRST_LINE, LINE_GAP = 66.0, 30.0
local MAX_LINES = 7

-- The pages. A line opens another page, is an on/off setting (GameOptions[option]), a setting with
-- a list of values (GameOptions.marathon[setting], GameOptions.CHOICES), or START.
local PAGES = {
    options = { title = "OPTIONS", lines = { { label = "AUDIO", open = "audio" } } },
    audio = { title = "AUDIO", back = "options",
              lines = { { label = "MUTE IN-STAGE MUSIC", option = "muteStageMusic" } } },
    marathon = { title = "MARATHON",
                 lines = { { label = "ROUNDS", setting = "rounds" },
                           { label = "STARTING DIFFICULTY", setting = "start" },
                           { label = "DIFFICULTY CLIMB", setting = "climb" },
                           { label = "RING LENIENCY", setting = "leniency" },
                           { label = "LIVES", setting = "lives" },
                           { label = "START", start = true } } },
}

local function MakeText(parent, font, colour)
    local t = parent:CreateChild("Text")
    if (font ~= nil) then t:SetFont(font) end
    t:SetAnchorMode(AnchorMode.TopLeft)
    t:SetColor(colour or WHITE)
    t:SetText("")
    return t
end

local function MakeQuad(parent, colour)
    local q = parent:CreateChild("Quad")
    q:SetAnchorMode(AnchorMode.TopLeft)
    q:SetColor(colour)
    return q
end

function OptionsPrompt:Create()
    self.built = false
    self.shown = false
    self.page, self.index = "options", 1
    TheOptions = self
end

function OptionsPrompt:Build()
    self.dim = MakeQuad(self, DIM)
    self.edge = MakeQuad(self, EDGE)
    self.box = MakeQuad(self, BOX)
    local font = LoadAsset("F_SonicUI")
    self.title = MakeText(self, font, YELLOW)
    self.labels, self.values = {}, {}
    for i = 1, MAX_LINES do
        self.labels[i] = MakeText(self, font, WHITE)
        self.values[i] = MakeText(self, font, SKY)
    end
    self.buttons = MakeText(self, font, SKY)
    self.built = true
    self:Show(false)
end

local function BoxHeight(page)
    return FIRST_LINE + #page.lines * LINE_GAP + 56.0
end

-- Laid out every tick while it shows: text is placed by its measured width, known once drawn,
-- and on the PC the window can change size. A page with values has its labels down the left of
-- the box and the values down the right; one without is centred.
function OptionsPrompt:Place()
    local page = PAGES[self.page]
    local res = Renderer.GetScreenResolution()
    local w, h = res.x, res.y
    local k = h / REF_H
    self:SetAnchorMode(AnchorMode.TopLeft)
    self:SetPosition(0.0, 0.0)
    self:SetDimensions(w, h)
    self.dim:SetPosition(0.0, 0.0)
    self.dim:SetDimensions(w, h)
    local bw, bh = BOX_W * k, BoxHeight(page) * k
    local x, top = (w - bw) * 0.5, (h - bh) * 0.5
    self.edge:SetPosition(x - 3.0 * k, top - 3.0 * k)
    self.edge:SetDimensions(bw + 6.0 * k, bh + 6.0 * k)
    self.box:SetPosition(x, top)
    self.box:SetDimensions(bw, bh)
    self.title:SetTextSize(22.0 * k)
    self.buttons:SetTextSize(16.0 * k)
    local function Wide(t) return (t.GetTextWidth ~= nil) and t:GetTextWidth() or 0.0 end
    self.title:SetPosition((w - Wide(self.title)) * 0.5, top + 20.0 * k)
    local columns = false
    for _, line in ipairs(page.lines) do
        if (line.setting ~= nil or line.option ~= nil) then columns = true end
    end
    for i = 1, MAX_LINES do
        local label, value = self.labels[i], self.values[i]
        label:SetTextSize(17.0 * k)
        value:SetTextSize(17.0 * k)
        local y = top + (FIRST_LINE + (i - 1) * LINE_GAP) * k
        if (columns) then
            label:SetPosition(x + 48.0 * k, y)
            value:SetPosition(x + bw - 48.0 * k - Wide(value), y)
        else
            label:SetPosition((w - Wide(label)) * 0.5, y)
        end
    end
    self.buttons:SetPosition((w - Wide(self.buttons)) * 0.5, top + bh - 40.0 * k)
end

-- What the page says now: its lines, the chosen one in yellow, each setting with its value.
function OptionsPrompt:Refresh()
    local page = PAGES[self.page]
    self.title:SetText(page.title)
    for i = 1, MAX_LINES do
        local line = page.lines[i]
        local value = ""
        if (line ~= nil and line.option ~= nil) then
            value = GameOptions[line.option] and "ON" or "OFF"
        elseif (line ~= nil and line.setting ~= nil) then
            value = GameOptions.CHOICES[line.setting].show(GameOptions.marathon[line.setting])
        end
        self.labels[i]:SetText(line and line.label or "")
        self.labels[i]:SetColor((i == self.index) and YELLOW or WHITE)
        self.values[i]:SetText(value)
    end
    local chosen = page.lines[self.index]
    local act = "A  SELECT"
    if (chosen ~= nil and (chosen.option ~= nil or chosen.setting ~= nil)) then act = "A  CHANGE" end
    if (chosen ~= nil and chosen.start) then act = "A  START" end
    self.buttons:SetText(act .. "        B  BACK")
end

function OptionsPrompt:Show(visible)
    self.shown = visible and true or false
    if (self.built) then self:SetVisible(self.shown) end
end

function OptionsPrompt:Open(page)
    if (not self.built) then self:Build() end
    self.page, self.index, self.armed = page or "options", 1, false
    self:Show(true)
    self:Refresh()
    self:Place()
end

function OptionsPrompt:Close()
    self:Show(false)
    if (self.onClose ~= nil) then self.onClose() end
end

-- As the menus: not armed until the key that opened it is let go.
function OptionsPrompt:Armed()
    if (self.armed) then return true end
    if (not Input.IsKeyDown(Key.Enter) and not Input.IsKeyDown(Key.Space)
        and not Input.IsKeyDown(Key.Backspace)) then
        self.armed = true
    end
    return false
end

local function Sound(name)
    if (MenuSound ~= nil) then MenuSound(name) end
end

-- A setting one step along its list of values, round from the end to the start.
local function Step(setting, by)
    local values = GameOptions.CHOICES[setting].values
    local at = 1
    for i, v in ipairs(values) do
        if (v == GameOptions.marathon[setting]) then at = i end
    end
    GameOptions.marathon[setting] = values[(at - 1 + by) % #values + 1]
end

function OptionsPrompt:Tick(deltaTime)
    if (not self.built) then self:Build() end
    if (not self.shown) then return end
    -- over the menus, which were spawned before it: attached again, it draws last
    self:Attach(self:GetWorld():GetRootNode(), false)
    self:Place()
    if (not self:Armed()) then return end

    local page = PAGES[self.page]
    local up = Input.IsKeyJustDown(Key.Up) or Input.IsKeyJustDown(Key.W)
    local down = Input.IsKeyJustDown(Key.Down) or Input.IsKeyJustDown(Key.S)
    local left = Input.IsKeyJustDown(Key.Left) or Input.IsKeyJustDown(Key.A)
    local right = Input.IsKeyJustDown(Key.Right) or Input.IsKeyJustDown(Key.D)
    local yes = Input.IsKeyJustDown(Key.Enter) or Input.IsKeyJustDown(Key.Space)
    local no = Input.IsKeyJustDown(Key.Backspace) or Input.IsKeyJustDown(Key.Escape)
    local line = page.lines[self.index]

    if (no) then
        Sound("MenuBack")
        if (page.back ~= nil) then
            -- back to the page this one was opened from, on the line that opened it
            local from = self.page
            self.page, self.index = page.back, 1
            for i, l in ipairs(PAGES[self.page].lines) do
                if (l.open == from) then self.index = i end
            end
            self:Refresh()
        else
            self:Close()
        end
    elseif (up or down) then
        local n = #page.lines
        if (n > 1) then
            self.index = (self.index - 1 + (down and 1 or -1)) % n + 1
            Sound("MenuMove")
            self:Refresh()
        end
    elseif (line == nil) then
        return
    elseif (line.open ~= nil and yes) then
        Sound("MenuSelect")
        self.page, self.index = line.open, 1
        self:Refresh()
    elseif (line.start and yes) then
        Sound("MenuSelect")
        self:Show(false)
        if (self.onClose ~= nil) then self.onClose() end
        if (self.onStart ~= nil) then self.onStart() end
    elseif (line.option ~= nil and (yes or left or right)) then
        GameOptions[line.option] = not GameOptions[line.option]
        GameOptions.touched = true              -- kept with the save the next time it is written
        Sound("MenuMove")
        self:Refresh()
    elseif (line.setting ~= nil and (yes or left or right)) then
        Step(line.setting, left and -1 or 1)
        GameOptions.touched = true
        Sound("MenuMove")
        self:Refresh()
    end
end
