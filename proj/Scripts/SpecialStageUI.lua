-- SpecialStageUI.lua
-- The special stage's UI, after the original's:
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
-- there is nothing to lay out in the editor. The labels, START, the flag and the emblem are
-- pictures: the art in external/ui/, made into T_UI_* textures by native/gen_ui_assets.py.
-- Only the NUMBERS, COOL ! and the banner are Text widgets, in the engine's own font.
--
-- There is no game to drive it yet, so `demo` (on by default) plays it on a loop: START,
-- rings counting up, COOL !, again. The game will turn `demo` off and call:
--
--     TheSpecialStageUI:ShowStart()        at the start of a stage
--     TheSpecialStageUI:SetRings(n)        as rings are collected or lost
--     TheSpecialStageUI:SetTotal(n)        the number in the TOTAL box (rings to go, or the total)
--     TheSpecialStageUI:ShowCool()         when a ring check is passed
--     TheSpecialStageUI:ShowBanner(t, s)   a line of words for s seconds
--     TheSpecialStageUI:ShowPause(on, i)   the pause menu, CONTINUE (1) or EXIT (2) picked
--
-- Everything is laid out on the original's 320 x 224 screen and scaled to the window's
-- height, so it sits the same at any resolution and is re-laid if the window changes size.

SpecialStageUI = {}

local SCREEN_W, SCREEN_H = 320.0, 224.0
-- The share of the window kept clear all round. 0 on a monitor, which shows every pixel; a TV
-- hides its edges (overscan), so a console build sets this to a few percent.
local SAFE_MARGIN = 0.0

local WHITE   = Vec(1.00, 1.00, 1.00, 1.0)
local BLACK   = Vec(0.00, 0.00, 0.00, 1.0)
local NAME    = Vec(0.35, 0.55, 1.00, 1.0)      -- SONIC, in his blue
local YELLOW  = Vec(1.00, 0.84, 0.10, 1.0)      -- RINGS
local BOX     = Vec(1.00, 1.00, 1.00, 1.0)

-- START: how long each part of it takes, in seconds.
local DROP_TIME, HOLD_TIME, SCATTER_TIME = 0.55, 1.00, 0.75
local DROP_STAGGER = 0.045      -- each letter lands this long after the one before it: S, T, A, R, T
local START_Y = 118.0                           -- where it comes to rest, on the 224-high screen
-- START is five textures, a letter each, so that they can part company. The letters of the art
-- TOUCH, so gen_ui_assets.py separates them properly (split_letters), each with a whole outline
-- of its own, and prints where each sits in the word: { x, y } here, in the art's pixels. Put
-- back at those places they overlap only in outline, and the word is exactly as it was drawn.
local START_LETTERS = { { 5, 11 }, { 50, 11 }, { 96, 11 }, { 146, 11 }, { 200, 11 } }
-- How each part leaves: the way it flies (x, y: up is negative), how far it turns (degrees), and
-- how long after the scatter starts it goes. They go from the OUTSIDE IN -- the flags, then the
-- end letters, then the inner ones, the A last -- each pulling back a touch first, then flung,
-- turning and growing as it comes toward the screen.
local START_FLIGHT = {
    { -1.00, -0.55, -70.0, 0.06 },      -- S
    { -0.55, -1.00, -35.0, 0.12 },      -- T
    {  0.00, -1.20,  12.0, 0.18 },      -- A
    {  0.55, -1.00,  35.0, 0.12 },      -- R
    {  1.00, -0.55,  70.0, 0.06 },      -- T
}
local FLAG_FLIGHT = { { -1.10, 0.20, -110.0, 0.0 }, { 1.10, 0.20, 110.0, 0.0 } }
local FLIGHT_REACH = 300.0      -- how far a part travels, on the 320 screen: well off it
local FLIGHT_GROW = 0.45        -- and how much bigger it gets on the way
local START_ART_W = 256.0                       -- the word, in the art's pixels
local LETTER_W, LETTER_H = 64.0, 128.0          -- the texture of one letter, in the same
local START_SCALE = 0.6                         -- art pixels to pixels of the 320 screen
local FLAG_W, FLAG_H = 44.0, 44.0

-- COOL !
local COOL_POP, COOL_HOLD, COOL_FADE = 0.30, 1.60, 0.40
local EMBLEM_W, EMBLEM_H = 150.0, 75.0          -- the winged disc: twice as wide as tall
local THUMB_SIZE = 66.0                         -- the glove, on the disc and a little over its edge
local COOL_BOB, COOL_BOB_TIME = 5.0, 1.8        -- it drifts up and down this far, this many seconds a cycle

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
    if (self.built) then
        self.totalNumber:SetText(tostring(n))
        self:PlaceTotal()
    end
end

-- The number sits in the MIDDLE of the box however many digits it has: a digit of this font
-- is about 6.6 wide on the 320 screen at the size it is shown.
function SpecialStageUI:PlaceTotal()
    if (self.totalAt == nil) then return end
    local digits = #tostring(self.total)
    self:Place(self.totalNumber, self.totalAt.x - digits * 6.6, self.totalAt.y)
end

function SpecialStageUI:ShowStart()
    self.startTime = 0.0
end

function SpecialStageUI:ShowCool()
    self.coolTime = 0.0
    self.tooBad = false
    self:DressEmblem()
end

-- A FAILED check: the same emblem and glove, gone red and thumb down, over TOO BAD !
function SpecialStageUI:ShowTooBad()
    self.coolTime = 0.0
    self.tooBad = true
    self:DressEmblem()
end

function SpecialStageUI:DressEmblem()
    if (not self.built) then return end
    self.emblem:SetTexture(self.tooBad and self.texEmblemRed or self.texEmblem)
    self.thumb:SetTexture(self.tooBad and self.texThumbDown or self.texThumb)
    self.coolText:SetText(self.tooBad and "TOO BAD !" or "COOL !")
end

-- The pause menu: CONTINUE over EXIT, the picked one in yellow.
function SpecialStageUI:ShowPause(visible, index)
    self.pauseOn, self.pauseIndex = visible and true or false, index or 1
    if (not self.built) then return end
    for i, t in ipairs(self.pauseItems) do
        t:SetVisible(self.pauseOn)
        t:SetColor((i == self.pauseIndex) and YELLOW or WHITE)
    end
end

-- A line of words across the middle for a few seconds: NOT ENOUGH RINGS, EMERALD GET !
function SpecialStageUI:ShowBanner(text, seconds)
    self.bannerText = text
    self.bannerLeft = seconds or 3.0
    if (self.built) then self.banner:SetText(text) end
end

-- ------------------------------------------------------------------ building
local function MakeText(parent, text, colour)
    local t = parent:CreateChild("Text")
    -- F_SonicUI: the Sonic font with its outline and drop shadow baked into the glyphs
    -- (native/gen_ui_font.py), so white text is the finished look and a colour only tints the face.
    local font = LoadAsset("F_SonicUI")
    if (font ~= nil) then t:SetFont(font) end
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
    self.ringsLabel  = MakeQuad(self, LoadAsset("T_UI_SonicRings"), WHITE)      -- SONIC over RINGS
    self.ringsNumber = MakeText(self, tostring(self.rings), WHITE)
    self.totalBox    = MakeQuad(self, LoadAsset("T_UI_Total"), WHITE)           -- the frame, word and all
    self.totalNumber = MakeText(self, tostring(self.total), WHITE)

    self.flagLeft  = MakeQuad(self, LoadAsset("T_UI_FlagLeft"), WHITE)
    self.flagRight = MakeQuad(self, LoadAsset("T_UI_Flag"), WHITE)
    -- The pole is beside the word and the cloth flies outward, so the left one is a mirrored picture.
    self.letters = {}
    for i = 1, #START_LETTERS do self.letters[i] = MakeQuad(self, LoadAsset("T_UI_Start_" .. i), WHITE) end

    self.banner   = MakeText(self, self.bannerText or "", YELLOW)
    self.banner:SetVisible(false)
    self.texEmblem, self.texThumb = LoadAsset("T_UI_Emblem"), LoadAsset("T_UI_Thumb")
    self.texEmblemRed = LoadAsset("T_UI_EmblemRed") or self.texEmblem
    self.texThumbDown = LoadAsset("T_UI_ThumbDown") or self.texThumb
    self.emblem   = MakeQuad(self, self.texEmblem, WHITE)
    self.thumb    = MakeQuad(self, self.texThumb, WHITE)
    self.coolText = MakeText(self, "COOL !", WHITE)
    self.pauseItems = { MakeText(self, "CONTINUE", WHITE), MakeText(self, "EXIT", WHITE) }

    self.built = true
    self:ShowPause(self.pauseOn, self.pauseIndex)
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
    self.thumb:SetVisible(visible)
    self.coolText:SetVisible(visible)
end

-- ------------------------------------------------------------------ layout
-- (x, y, w, h) are on the 320 x 224 screen; k scales them to the window, and the picture
-- is centred across a window that is wider than 4:3.
function SpecialStageUI:Place(widget, x, y, w, h)
    widget:SetPosition(self.left + x * self.k, (self.top or 0.0) + y * self.k)
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

    -- A Canvas is 100 x 100 in the corner unless told otherwise, and it CLIPS its children to
    -- that: the first version laid everything out correctly and showed none of it, because
    -- all of it was outside that little square. Fill the window.
    if (self.SetDimensions ~= nil) then
        self:SetAnchorMode(AnchorMode.TopLeft)
        self:SetPosition(0.0, 0.0)
        self:SetDimensions(width, height)
    end
    self.layoutHeight = height
    -- Scaled to FIT: by the height on a wide window, by the WIDTH on a narrow one. The design is
    -- 320 x 224, which is wider in proportion than a 4:3 screen: scaled by height alone it was
    -- wider than a 640 x 480 window, and SONIC / RINGS hung off its left edge.
    local usableW, usableH = width * (1.0 - 2.0 * SAFE_MARGIN), height * (1.0 - 2.0 * SAFE_MARGIN)
    self.k = math.min(usableH / SCREEN_H, usableW / SCREEN_W)
    self.left = (width - SCREEN_W * self.k) * 0.5
    self.top = height * SAFE_MARGIN

    -- SONIC / RINGS: the picture is 2:1, RINGS its lower half; the count goes beside RINGS
    self:Place(self.ringsLabel, 8.0, 6.0, 68.0, 34.0)
    self.ringsNumber:SetTextSize(17.0 * self.k)
    self:Place(self.ringsNumber, 80.0, 17.0)

    -- TOTAL: the frame, centred, and the number in the middle of it. The texture is square
    -- and the art is its top 160 rows of 256, so the box on screen is bw wide and bw * 160/256 tall.
    local bx, by, bw = 122.0, 5.0, 76.0
    self:Place(self.totalBox, bx, by, bw, bw)
    self.totalNumber:SetTextSize(19.0 * self.k)
    self.totalAt = { x = bx + bw * 0.5, y = by + 15.0 }
    self:PlaceTotal()
    self.coolText:SetTextSize(26.0 * self.k)
    self.banner:SetTextSize(22.0 * self.k)
    -- the pause menu, centred, one line over the other
    for i, t in ipairs(self.pauseItems) do
        local word = (i == 1) and "CONTINUE" or "EXIT"
        t:SetTextSize(22.0 * self.k)
        self:Place(t, SCREEN_W * 0.5 - 5.6 * #word, 84.0 + (i - 1) * 28.0)
    end
end

-- ------------------------------------------------------------------ animation
local function EaseOutBack(t)               -- overshoots a little and settles: a drop with a bounce
    local c = 1.70158
    local u = t - 1.0
    return 1.0 + (c + 1.0) * u * u * u + c * u * u
end

-- Pulls back a little before it goes: anticipation, then the fling.
local function EaseInBack(t)
    local c = 1.9
    return t * t * ((c + 1.0) * t - c)
end

local function Clamp01(t)
    return math.max(0.0, math.min(1.0, t))
end

-- Each part of START: where it rests (on the 320 screen), its size, and how it flies off.
local function StartParts(self)
    local parts = {}
    local mid = SCREEN_W * 0.5
    local wordW = START_ART_W * START_SCALE
    local first = mid - wordW * 0.5
    for i = 1, #self.letters do
        local at = START_LETTERS[i]
        parts[#parts + 1] = { widget = self.letters[i], order = i - 1,
                              x = first + at[1] * START_SCALE, y = START_Y + at[2] * START_SCALE,
                              w = LETTER_W * START_SCALE, h = LETTER_H * START_SCALE, flight = START_FLIGHT[i] }
    end
    local flagY = START_Y + 17.0
    parts[#parts + 1] = { widget = self.flagLeft, order = 0, x = first - FLAG_W - 4.0, y = flagY,
                          w = FLAG_W, h = FLAG_H, flight = FLAG_FLIGHT[1] }
    parts[#parts + 1] = { widget = self.flagRight, order = 4, x = first + wordW + 4.0, y = flagY,
                          w = FLAG_W, h = FLAG_H, flight = FLAG_FLIGHT[2] }
    return parts
end

function SpecialStageUI:TickStart(deltaTime)
    if (self.startTime < 0.0) then return end
    self.startTime = self.startTime + deltaTime
    local t = self.startTime
    local dropEnd = DROP_TIME + DROP_STAGGER * 4.0
    local total = dropEnd + HOLD_TIME + SCATTER_TIME
    if (t >= total) then
        self.startTime = -1.0
        self:ShowStartParts(false)
        return
    end
    self:ShowStartParts(true)

    for _, p in ipairs(StartParts(self)) do
        -- the drop: one after another from above the window, each landing with a little bounce
        local drop = EaseOutBack(Clamp01((t - p.order * DROP_STAGGER) / DROP_TIME))
        local x, y, w, h = p.x, -110.0 + (p.y + 110.0) * drop, p.w, p.h
        local turn = 0.0

        -- the scatter
        local f = p.flight
        local since = t - dropEnd - HOLD_TIME - f[4]
        if (since > 0.0) then
            local away = EaseInBack(Clamp01(since / (SCATTER_TIME - 0.18)))
            x = x + f[1] * FLIGHT_REACH * away
            y = y + f[2] * FLIGHT_REACH * away
            turn = f[3] * math.max(0.0, away)
            local grow = 1.0 + FLIGHT_GROW * math.max(0.0, away)
            x, y = x - w * (grow - 1.0) * 0.5, y - h * (grow - 1.0) * 0.5      -- grow about its middle
            w, h = w * grow, h * grow
        end
        self:Place(p.widget, x, y, w, h)
        p.widget:SetRotation(turn)
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

    -- The glove floats slowly up and down, and the emblem behind it floats the OTHER way:
    -- as the hand rises the wings sink, so the two drift apart and back together.
    local ew, eh, th = EMBLEM_W * size, EMBLEM_H * size, THUMB_SIZE * size
    local bob = math.sin(t * 2.0 * math.pi / COOL_BOB_TIME) * COOL_BOB
    self:Place(self.emblem, SCREEN_W * 0.5 - ew * 0.5, 84.0 + bob - eh * 0.5, ew, eh)
    self:Place(self.thumb, SCREEN_W * 0.5 - th * 0.5, 84.0 - bob - th * 0.5, th, th)
    self:Place(self.coolText, SCREEN_W * 0.5 - (self.tooBad and 62.0 or 44.0), 128.0)
    self.emblem:SetOpacityFloat(opacity)
    self.thumb:SetOpacityFloat(opacity)
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

    if ((self.bannerLeft or 0.0) > 0.0) then
        self.bannerLeft = self.bannerLeft - deltaTime
        self.banner:SetVisible(true)
        self:Place(self.banner, SCREEN_W * 0.5 - 5.6 * #self.bannerText, 176.0)
    elseif (self.banner:IsVisible()) then
        self.banner:SetVisible(false)
    end
    self:TickStart(deltaTime)
    self:TickCool(deltaTime)
end
