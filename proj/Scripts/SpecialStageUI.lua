-- SpecialStageUI.lua
-- PLACEHOLDER UI for the special stage, after the original's:
--
--     SONIC                 +-TOTAL-+
--     RINGS 0               |   0   |
--
--               [flag]  S T A R T  [flag]        <- drops in from the top of the window,
--                                                   holds, then scatters: the left half
--                                                   and its flag fly off to the left, the
--                                                   right half to the right, the A straight up
--
--                       (thumbs-up emblem)        <- on a passed ring check: pops in over
--                           COOL !                   the middle, holds, fades
--
-- Attach to a Canvas (or any node) in the scene. It builds its own widgets as children, so
-- there is nothing to lay out in the editor. The words are Text widgets in the engine's own
-- font; the flag and the emblem are T_UI_Flag and T_UI_Emblem, drawn by
-- native/gen_ui_assets.py -- replace those two textures with real art and nothing here changes.
--
-- There is no game to drive it yet, so `demo` (on by default) plays it on a loop: START,
-- rings counting up, COOL !, again. The game will turn `demo` off and call:
--
--     TheSpecialStageUI:ShowStart()        at the start of a stage
--     TheSpecialStageUI:SetRings(n)        as rings are collected or lost
--     TheSpecialStageUI:SetTotal(n)        the number in the TOTAL box (rings to go, or the total)
--     TheSpecialStageUI:ShowCool()         when a ring check is passed
--
-- Everything is laid out on the original's 320 x 224 screen and scaled to the window's
-- height, so it sits the same at any resolution and is re-laid if the window changes size.

SpecialStageUI = {}

local SCREEN_W, SCREEN_H = 320.0, 224.0

local WHITE   = Vec(1.00, 1.00, 1.00, 1.0)
local BLACK   = Vec(0.00, 0.00, 0.00, 1.0)
local NAME    = Vec(0.35, 0.55, 1.00, 1.0)      -- SONIC, in his blue
local YELLOW  = Vec(1.00, 0.84, 0.10, 1.0)      -- RINGS
local BOX     = Vec(1.00, 1.00, 1.00, 1.0)

-- START: how long each part of it takes, in seconds.
local DROP_TIME, HOLD_TIME, SCATTER_TIME = 0.45, 1.10, 0.60
local START_Y = 150.0                           -- where it comes to rest, on the 224-high screen
local LETTERS = { "S", "T", "A", "R", "T" }
local LETTER_SIZE, LETTER_STEP = 44.0, 30.0
local FLAG_W, FLAG_H = 56.0, 42.0

-- COOL !
local COOL_POP, COOL_HOLD, COOL_FADE = 0.30, 1.60, 0.40
local EMBLEM_SIZE = 110.0

function SpecialStageUI:Create()
    self.demo = true
    self.playerName = "SONIC"
    self.rings = 0
    self.total = 0
    self.built = false
    self.layoutHeight = -1
    self.startTime = -1.0           -- < 0: START is not showing
    self.coolTime = -1.0
    self.demoTime = 0.0
    TheSpecialStageUI = self
end

function SpecialStageUI:GatherProperties()
    return
    {
        { name = "demo", type = DatumType.Bool },
        { name = "playerName", type = DatumType.String },
    }
end

-- ------------------------------------------------------------------ the game's side
function SpecialStageUI:SetRings(n)
    self.rings = n
    if (self.built) then self.ringsNumber:SetText(tostring(n)) end
end

function SpecialStageUI:SetTotal(n)
    self.total = n
    if (self.built) then self.totalNumber:SetText(tostring(n)) end
end

function SpecialStageUI:ShowStart()
    self.startTime = 0.0
end

function SpecialStageUI:ShowCool()
    self.coolTime = 0.0
end

-- ------------------------------------------------------------------ building
local function MakeText(parent, text, colour)
    local t = parent:CreateChild("Text")
    t:SetAnchorMode(AnchorMode.TopLeft)
    t:SetText(text)
    t:SetColor(colour)
    t:SetOutlineColor(BLACK)
    return t
end

local function MakeQuad(parent, texture, colour)
    local q = parent:CreateChild("Quad")
    q:SetAnchorMode(AnchorMode.TopLeft)
    if (texture ~= nil) then q:SetTexture(texture) end
    q:SetColor(colour or WHITE)
    return q
end

function SpecialStageUI:Build()
    self.nameText    = MakeText(self, self.playerName, NAME)
    self.ringsLabel  = MakeText(self, "RINGS", YELLOW)
    self.ringsNumber = MakeText(self, tostring(self.rings), WHITE)

    -- the TOTAL box: four thin bars, open at the top where the word sits
    self.boxBars = {}
    for i = 1, 5 do self.boxBars[i] = MakeQuad(self, nil, BOX) end
    self.totalLabel  = MakeText(self, "TOTAL", WHITE)
    self.totalNumber = MakeText(self, tostring(self.total), WHITE)

    local flag = LoadAsset("T_UI_Flag")
    self.flagLeft  = MakeQuad(self, flag, WHITE)
    self.flagRight = MakeQuad(self, flag, WHITE)
    -- The texture's pole is on its left, so it is the right-hand flag as drawn: pole beside
    -- the word, cloth flying outward. The left-hand one is the same picture mirrored.
    self.flagLeft:SetUvScale(Vec(-1.0, 1.0))
    self.flagLeft:SetUvOffset(Vec(1.0, 0.0))
    self.letters = {}
    for i = 1, #LETTERS do self.letters[i] = MakeText(self, LETTERS[i], WHITE) end

    self.emblem   = MakeQuad(self, LoadAsset("T_UI_Emblem"), WHITE)
    self.coolText = MakeText(self, "COOL !", WHITE)

    self.built = true
    self:ShowStartParts(false)
    self:ShowCoolParts(false)
end

function SpecialStageUI:ShowStartParts(visible)
    self.flagLeft:SetVisible(visible)
    self.flagRight:SetVisible(visible)
    for i = 1, #self.letters do self.letters[i]:SetVisible(visible) end
end

function SpecialStageUI:ShowCoolParts(visible)
    self.emblem:SetVisible(visible)
    self.coolText:SetVisible(visible)
end

-- ------------------------------------------------------------------ layout
-- (x, y, w, h) are on the 320 x 224 screen; k scales them to the window, and the picture
-- is centred across a window that is wider than 4:3.
function SpecialStageUI:Place(widget, x, y, w, h)
    widget:SetPosition(self.left + x * self.k, y * self.k)
    if (w ~= nil) then widget:SetDimensions(w * self.k, h * self.k) end
end

-- The window's size. The script may sit on a Canvas or on a plain node, which has no size of
-- its own; either way the children are laid out against the whole window.
function SpecialStageUI:WindowSize()
    local res = Renderer.GetScreenResolution()
    return res.x, res.y
end

function SpecialStageUI:Layout()
    local width, height = self:WindowSize()
    self.layoutHeight = height
    self.k = height / SCREEN_H
    self.left = (width - SCREEN_W * self.k) * 0.5

    self.nameText:SetTextSize(13.0 * self.k)
    self.ringsLabel:SetTextSize(16.0 * self.k)
    self.ringsNumber:SetTextSize(16.0 * self.k)
    self:Place(self.nameText, 26.0, 8.0)
    self:Place(self.ringsLabel, 12.0, 21.0)
    self:Place(self.ringsNumber, 72.0, 21.0)

    -- the box, 60 x 34, centred; its top edge is two stubs either side of TOTAL
    local bx, by, bw, bh, t = 130.0, 16.0, 60.0, 34.0, 2.0
    self:Place(self.boxBars[1], bx, by, 10.0, t)
    self:Place(self.boxBars[2], bx + bw - 10.0, by, 10.0, t)
    self:Place(self.boxBars[3], bx, by, t, bh)
    self:Place(self.boxBars[4], bx + bw - t, by, t, bh)
    self:Place(self.boxBars[5], bx, by + bh - t, bw, t)
    self.totalLabel:SetTextSize(11.0 * self.k)
    self.totalNumber:SetTextSize(20.0 * self.k)
    self:Place(self.totalLabel, bx + 13.0, by - 7.0)
    self:Place(self.totalNumber, bx + 24.0, by + 9.0)

    for i = 1, #self.letters do self.letters[i]:SetTextSize(LETTER_SIZE * self.k) end
    self.coolText:SetTextSize(26.0 * self.k)
end

-- ------------------------------------------------------------------ animation
local function EaseOutBack(t)               -- overshoots a little and settles: a drop with a bounce
    local c = 1.70158
    local u = t - 1.0
    return 1.0 + (c + 1.0) * u * u * u + c * u * u
end

local function EaseInQuad(t)
    return t * t
end

-- Each part of START: where it rests (x on the 320 screen), and which way it scatters.
local function StartParts(self)
    local parts = {}
    local mid = SCREEN_W * 0.5
    local first = mid - LETTER_STEP * (#LETTERS - 1) * 0.5 - 12.0
    for i = 1, #self.letters do
        local x = first + LETTER_STEP * (i - 1)
        local dir = 0.0
        if (i < 3) then dir = -1.0 elseif (i > 3) then dir = 1.0 end
        parts[#parts + 1] = { widget = self.letters[i], x = x, y = START_Y, dx = dir, dy = (dir == 0.0) and -1.0 or -0.25 }
    end
    parts[#parts + 1] = { widget = self.flagLeft,  x = first - FLAG_W - 6.0, y = START_Y + 4.0, dx = -1.0, dy = 0.15,
                          w = FLAG_W, h = FLAG_H, spin = -40.0 }
    parts[#parts + 1] = { widget = self.flagRight, x = first + LETTER_STEP * #LETTERS + 4.0, y = START_Y + 4.0, dx = 1.0, dy = 0.15,
                          w = FLAG_W, h = FLAG_H, spin = 40.0 }
    return parts
end

function SpecialStageUI:TickStart(deltaTime)
    if (self.startTime < 0.0) then return end
    self.startTime = self.startTime + deltaTime
    local t = self.startTime
    local total = DROP_TIME + HOLD_TIME + SCATTER_TIME
    if (t >= total) then
        self.startTime = -1.0
        self:ShowStartParts(false)
        return
    end
    self:ShowStartParts(true)

    local drop = 1.0                        -- 0: above the window, 1: at rest
    local away = 0.0                        -- 0: at rest, 1: gone
    if (t < DROP_TIME) then
        drop = EaseOutBack(t / DROP_TIME)
    elseif (t > DROP_TIME + HOLD_TIME) then
        away = EaseInQuad((t - DROP_TIME - HOLD_TIME) / SCATTER_TIME)
    end

    for _, p in ipairs(StartParts(self)) do
        local y = -70.0 + (p.y + 70.0) * drop       -- from above the top of the window
        local x = p.x + p.dx * away * 260.0         -- and away, off the side it belongs to
        y = y + p.dy * away * 260.0
        self:Place(p.widget, x, y, p.w, p.h)
        if (p.spin ~= nil) then p.widget:SetRotation(p.spin * away) end
    end
end

function SpecialStageUI:TickCool(deltaTime)
    if (self.coolTime < 0.0) then return end
    self.coolTime = self.coolTime + deltaTime
    local t = self.coolTime
    if (t >= COOL_POP + COOL_HOLD + COOL_FADE) then
        self.coolTime = -1.0
        self:ShowCoolParts(false)
        return
    end
    self:ShowCoolParts(true)

    local size = 1.0
    local opacity = 1.0
    if (t < COOL_POP) then
        size = EaseOutBack(t / COOL_POP)
    elseif (t > COOL_POP + COOL_HOLD) then
        opacity = 1.0 - (t - COOL_POP - COOL_HOLD) / COOL_FADE
    end

    local e = EMBLEM_SIZE * size
    self:Place(self.emblem, SCREEN_W * 0.5 - e * 0.5, 84.0 - e * 0.5, e, e)
    self:Place(self.coolText, SCREEN_W * 0.5 - 44.0, 140.0)
    self.emblem:SetOpacityFloat(opacity)
    self.coolText:SetOpacityFloat(opacity)
end

-- With no game yet: START, rings counting up, COOL !, and round again.
function SpecialStageUI:TickDemo(deltaTime)
    local before = self.demoTime
    self.demoTime = self.demoTime + deltaTime
    local t = self.demoTime
    if (before < 0.5 and t >= 0.5) then
        self:SetRings(0)
        self:SetTotal(30)
        self:ShowStart()
    end
    if (t > 3.0 and t < 7.5 and math.floor(t / 0.15) ~= math.floor(before / 0.15)) then
        self:SetRings(self.rings + 1)
        self:SetTotal(math.max(0, 30 - self.rings))
    end
    if (before < 8.0 and t >= 8.0) then self:ShowCool() end
    if (t >= 11.5) then self.demoTime = 0.0 end
end

function SpecialStageUI:Tick(deltaTime)
    if (not self.built) then self:Build() end

    local _, height = self:WindowSize()
    if (height ~= self.layoutHeight) then self:Layout() end

    if (self.demo) then self:TickDemo(deltaTime) end
    self:TickStart(deltaTime)
    self:TickCool(deltaTime)
end
