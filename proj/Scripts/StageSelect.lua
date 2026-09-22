-- StageSelect.lua
-- Where Main Game leads: the seven emerald stages, one to a row.
--
--     [SONIC PIPE DREAM]
--                                        (that stage's emerald)
--      > STAGE 1                        +-----------+
--        STAGE 2                        |  the      |
--        ...                            |  stage    |
--        STAGE 7                        +-----------+
--                                             BLUE
--                                        (A) Select  (B) Back
--
-- It borrows the menu's furniture -- the panel, the title, the frame round the picture, the
-- button legends -- so the two screens are one screen with a different middle. What changes
-- with the cursor is the picture and the emerald:
--
--   * the picture is a photograph of that stage, taken by native/make_stage_previews.py by
--     running the game at it. Each one is its own pipe colours under its own sky.
--   * the emerald is that stage's chaos emerald. Until it is won it is barely there -- its
--     own colour, nearly transparent -- so you can see which one is missing and what it will
--     look like when it is not. Taking it in the stage brings you straight back here with it
--     in full colour. What has been won is remembered between sessions (see Save).
--   * under the picture is that emerald's COLOUR, where the mockup said SPECIAL STAGE.
--
-- The rows are text, not art: the mockup drew four words and none of them is a number, and
-- the menu's lettering has no digits to cut one out of. F_SonicUI is the game's own Sonic
-- font, the one the ring counter uses.
--
--     TheStageSelect.onChoose    called with the stage number (1-7)
--     TheStageSelect.onBack      called when B is pressed

StageSelect = {}

Script.Require("MenuLayout")

local STAGES = 7
local SAVE = "emeralds"                 -- one character a stage: "1" won, "0" not

local WHITE = Vec(1.0, 1.0, 1.0, 1.0)
local DIM = Vec(0.62, 0.66, 0.78, 1.0)  -- a row the cursor is not on
local GHOST = Vec(1.0, 1.0, 1.0, 0.30)  -- an emerald still out there: its colour, barely there
local LABEL = Vec(0.01, 0.15, 0.68, 1.0)    -- the mockup's lettering blue

-- Which emerald belongs to which stage, as native/export_emeralds.py assigns them. The name
-- goes under the picture, where the mockup said SPECIAL STAGE.
local EMERALD_NAME = { "BLUE", "YELLOW", "PURPLE", "GREEN", "RED", "SKY", "WHITE" }

local ROW_TOP = 104.0                   -- on the mockup's 522 x 386 screen
local ROW_PITCH = 27.0
local ROW_X = 41.0
local ROW_SIZE = 19.0

local REPEAT_FIRST, REPEAT_AFTER = 0.40, 0.12

local function MakeQuad(parent, texture)
    local q = parent:CreateChild("Quad")
    q:SetAnchorMode(AnchorMode.TopLeft)
    if (texture ~= nil) then q:SetTexture(texture) end
    q:SetColor(WHITE)
    return q
end

local function MakeText(parent, text)
    local t = parent:CreateChild("Text")
    local font = LoadAsset("F_SonicUI")
    if (font ~= nil) then t:SetFont(font) end
    t:SetAnchorMode(AnchorMode.TopLeft)
    t:SetText(text)
    t:SetColor(WHITE)
    return t
end

-- ------------------------------------------------------------------ what has been won
-- A tiny save: seven characters. It is read when the screen is built and written the moment
-- an emerald is taken, so closing the game does not lose it.
function StageSelect:LoadWon()
    self.won = {}
    for i = 1, STAGES do self.won[i] = false end
    if (System == nil or System.DoesSaveExist == nil or not System.DoesSaveExist(SAVE)) then return end
    local stream = Stream.Create()
    System.ReadSave(SAVE, stream)
    stream:SetPos(0)                    -- the save is read INTO the stream; rewind to read it
    local text = stream:ReadString()
    for i = 1, math.min(STAGES, #text) do
        self.won[i] = (text:sub(i, i) == "1")
    end
end

function StageSelect:SaveWon()
    if (System == nil or System.WriteSave == nil) then return end
    local text = ""
    for i = 1, STAGES do text = text .. (self.won[i] and "1" or "0") end
    local stream = Stream.Create()
    stream:WriteString(text)
    System.WriteSave(SAVE, stream)
end

-- All seven: what unlocks MARATHON in the menu.
function StageSelect:AllWon()
    for i = 1, STAGES do
        if (not self.won[i]) then return false end
    end
    return true
end

function StageSelect:SetWon(stage, won)
    if (stage < 1 or stage > STAGES) then return end
    self.won[stage] = won and true or false
    self:SaveWon()
    if (self.built) then self:Refresh() end
end

-- ------------------------------------------------------------------ build
function StageSelect:Create()
    self.built = false
    self.index = 1
    self.open = false
    self.held = 0.0
    self:LoadWon()
    TheStageSelect = self
end

function StageSelect:Build()
    local L = MenuLayout
    self.quads = {}
    for _, name in ipairs({ "T_Menu_Panel", "T_Menu_Circles", "T_Menu_Watermark",
                            "T_Menu_TitleBanner", "T_Menu_TitleText", "T_Menu_SelectBar",
                            "T_Menu_PreviewFrame",
                            "T_Menu_ButtonA", "T_Menu_LabelSelect",
                            "T_Menu_ButtonB", "T_Menu_LabelBack", "T_Menu_Cursor" }) do
        self.quads[name] = MakeQuad(self, LoadAsset(name))
    end
    -- the picture and the emerald change with the cursor, so they are one quad each
    self.preview = MakeQuad(self, LoadAsset("T_Menu_Preview1"))
    self.emerald = MakeQuad(self, LoadAsset("T_Menu_Emerald1"))
    self.previewTex, self.emeraldTex = {}, {}
    for i = 1, STAGES do
        self.previewTex[i] = LoadAsset("T_Menu_Preview" .. i)
        self.emeraldTex[i] = LoadAsset("T_Menu_Emerald" .. i)
    end
    -- and the name of that emerald, where the mockup's SPECIAL STAGE label was
    self.label = MakeText(self, EMERALD_NAME[1])
    self.label:SetColor(LABEL)

    self.rows = {}
    for i = 1, STAGES do self.rows[i] = MakeText(self, "STAGE " .. i) end

    self.built = true
    -- A save from a previous session may already have every emerald in it.
    if (self:AllWon() and TheMenu ~= nil) then TheMenu:SetUnlocked("marathon", true) end
    self:Refresh()
    self:Layout()
    self:Show(self.open)
end

-- ------------------------------------------------------------------ layout
function StageSelect:Place(quad, p)
    local k = self.k
    quad:SetPosition(self.left + p.x * k, self.top + p.y * k)
    quad:SetDimensions(p.w * k * p.cw / p.aw, p.h * k * p.ch / p.ah)
end

function StageSelect:Layout()
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
    self.k = math.min(height / L.screen.h, width / L.screen.w)
    self.left = (width - L.screen.w * self.k) * 0.5
    self.top = (height - L.screen.h * self.k) * 0.5

    for name, quad in pairs(self.quads) do self:Place(quad, L.parts[name]) end
    local panel = L.parts.T_Menu_Panel
    self.quads.T_Menu_Panel:SetPosition(0.0, self.top + panel.y * self.k)
    self.quads.T_Menu_Panel:SetDimensions(width, panel.h * self.k * panel.ch / panel.ah)

    self:Place(self.preview, L.parts.T_Menu_Preview1)
    self:Place(self.emerald, L.parts.T_Menu_Emerald1)
    -- the colour's name, centred on the rectangle the SPECIAL STAGE label used
    local where = L.parts.T_Menu_LabelStage
    self.label:SetTextSize(13.0 * self.k)
    self.labelAt = { x = where.x + where.w * 0.5, y = where.y - 3.0 }
    self:PlaceLabel()

    for i, row in ipairs(self.rows) do
        row:SetTextSize(ROW_SIZE * self.k)
        row:SetPosition(self.left + ROW_X * self.k, self.top + (ROW_TOP + (i - 1) * ROW_PITCH) * self.k)
    end
    self:PlaceSelection()
end

-- The bar and the arrow follow the cursor. The bar was drawn to sit behind a row of the
-- menu's own art, which is taller than a line of text, so it is lifted by the difference.
function StageSelect:PlaceSelection()
    local L = MenuLayout
    local bar = L.parts.T_Menu_SelectBar
    local y = ROW_TOP + (self.index - 1) * ROW_PITCH - (bar.h - ROW_SIZE) * 0.5
    self.quads.T_Menu_SelectBar:SetPosition(self.left + bar.x * self.k, self.top + y * self.k)
    local cur = L.parts.T_Menu_Cursor
    self.quads.T_Menu_Cursor:SetPosition(self.left + cur.x * self.k,
                                         self.top + (y + (bar.h - cur.h) * 0.5) * self.k)
end

-- ------------------------------------------------------------------ state
-- The label is centred on the picture, so where it starts depends on how wide the word is.
function StageSelect:PlaceLabel()
    if (self.labelAt == nil or self.label == nil) then return end
    local wide = (self.label.GetTextWidth ~= nil) and self.label:GetTextWidth() or 0.0
    self.label:SetPosition(self.left + self.labelAt.x * self.k - wide * 0.5,
                           self.top + self.labelAt.y * self.k)
end

function StageSelect:Refresh()
    for i, row in ipairs(self.rows) do
        row:SetColor((i == self.index) and WHITE or DIM)
    end
    local n = self.index
    if (self.previewTex[n] ~= nil) then self.preview:SetTexture(self.previewTex[n]) end
    -- Always that stage's own emerald, in its own colour. Until it is won it is barely
    -- there: you can see which one is missing, and what it will look like when it is not.
    if (self.emeraldTex[n] ~= nil) then self.emerald:SetTexture(self.emeraldTex[n]) end
    self.emerald:SetColor(self.won[n] and WHITE or GHOST)
    self.label:SetText(EMERALD_NAME[n] or "")
    self:PlaceLabel()
end

function StageSelect:Show(visible)
    if (visible and not self.open) then self.armed = false end
    self.open = visible and true or false
    if (not self.built) then return end
    for _, quad in pairs(self.quads) do quad:SetVisible(self.open) end
    self.preview:SetVisible(self.open)
    self.emerald:SetVisible(self.open)
    self.label:SetVisible(self.open)
    for _, row in ipairs(self.rows) do row:SetVisible(self.open) end
end

function StageSelect:Open() self:Show(true) end
function StageSelect:Close() self:Show(false) end

function StageSelect:Move(by)
    self.index = self.index + by
    if (self.index < 1) then self.index = STAGES end
    if (self.index > STAGES) then self.index = 1 end
    self:PlaceSelection()
    self:Refresh()
end

-- ------------------------------------------------------------------ every frame
function StageSelect:Tick(deltaTime)
    if (not self.built) then self:Build() end
    -- For testing without a keyboard, as the menu has: S2_SELECT_PICK=3 chooses stage 3.
    if (self.open and self.autoPick == nil) then
        self.autoPick = (os ~= nil and os.getenv ~= nil and tonumber(os.getenv("S2_SELECT_PICK") or "")) or false
        if (self.autoPick) then
            self.index = math.max(1, math.min(STAGES, math.floor(self.autoPick)))
            self:PlaceSelection()
            self:Refresh()
            if (self.onChoose ~= nil) then self.onChoose(self.index) end
        end
    end
    local res = Renderer.GetScreenResolution()
    if (self.layoutSize == nil or res.x ~= self.layoutSize.w or res.y ~= self.layoutSize.h) then
        self:Layout()
    end
    if (not self.open) then return end

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
    if (Input.IsKeyJustDown(Key.Enter) or Input.IsKeyJustDown(Key.Space)) then
        if (self.onChoose ~= nil) then self.onChoose(self.index) end
    elseif (Input.IsKeyJustDown(Key.Escape) or Input.IsKeyJustDown(Key.Backspace)) then
        if (self.onBack ~= nil) then self.onBack() end
    end
end


-- A screen that has just opened must not act on the very key that opened it. Both screens
-- tick in the same frame, so the Enter that chose Main Game was still "just down" when the
-- stage select ticked a moment later, and it chose stage 1 with it. A screen is not armed
-- until it sees the confirm keys released.
function StageSelect:Armed()
    if (self.armed) then return true end
    if (not Input.IsKeyDown(Key.Enter) and not Input.IsKeyDown(Key.Space)) then
        self.armed = true
    end
    return false
end
