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
--   * the emerald is that stage's chaos emerald in its own colour once it is won, and until
--     then its shadow: a black silhouette, half transparent, so you can see which one is
--     missing. Taking it in the stage brings you straight back here with it in full colour.
--     What has been won is remembered between sessions (see Save).
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
local GHOST = Vec(1.0, 1.0, 1.0, 0.55)  -- an emerald still out there: a black silhouette, half there
local LABEL = Vec(0.01, 0.15, 0.68, 1.0)    -- the mockup's lettering blue

-- Which emerald belongs to which stage, as native/export_emeralds.py assigns them. The name
-- goes under the picture, where the mockup said SPECIAL STAGE, in that emerald's colour --
-- and the frame round the picture takes the same colour. The font carries its own dark
-- outline and shadow, so even yellow and white read on the yellow panel.
local EMERALD_NAME = { "BLUE", "YELLOW", "PURPLE", "GREEN", "RED", "SKY", "WHITE" }
local EMERALD_COLOUR = {
    Vec(0.12, 0.38, 1.00, 1.0),     -- blue
    Vec(1.00, 0.82, 0.12, 1.0),     -- yellow
    Vec(0.62, 0.22, 0.92, 1.0),     -- purple
    Vec(0.12, 0.78, 0.32, 1.0),     -- green
    Vec(0.92, 0.16, 0.16, 1.0),     -- red
    Vec(0.32, 0.78, 1.00, 1.0),     -- sky
    Vec(1.00, 1.00, 1.00, 1.0),     -- white
}

local ROW_TOP = 104.0                   -- on the mockup's 522 x 386 screen
local ROW_PITCH = 27.0
local ROW_X = 41.0
local ROW_SIZE = 19.0
local BAR_DROP = 5.0                    -- the bar sits this much below the row's text box, so
                                        -- its underline runs under the letters, not through them

local REPEAT_FIRST, REPEAT_AFTER = 0.40, 0.12

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
    for _, name in ipairs({ "T_Menu_Panel", "T_Menu_Circles" }) do
        self.quads[name] = MakeQuad(self, LoadAsset(name))
    end
    self:BuildWatermark()               -- over the panel, under everything else
    for _, name in ipairs({ "T_Menu_TitleBanner", "T_Menu_TitleText", "T_Menu_SelectBarThin",
                            "T_Menu_PreviewFrame",
                            "T_Menu_ButtonA", "T_Menu_LabelSelect",
                            "T_Menu_ButtonB", "T_Menu_LabelBack", "T_Menu_Cursor" }) do
        self.quads[name] = MakeQuad(self, LoadAsset(name))
    end
    -- the picture and the emerald change with the cursor, so they are one quad each
    self.preview = MakeQuad(self, LoadAsset("T_Menu_Preview1"))
    self.emerald = MakeQuad(self, LoadAsset("T_Menu_Emerald1"))
    self.previewTex, self.emeraldTex = {}, {}
    self.emeraldOff = LoadAsset("T_Menu_EmeraldOff")     -- the black silhouette
    for i = 1, STAGES do
        self.previewTex[i] = LoadAsset("T_Menu_Preview" .. i)
        self.emeraldTex[i] = LoadAsset("T_Menu_Emerald" .. i)
    end
    -- the preview is a short clip of the stage playing (native/make_stage_previews.py):
    -- frame 0 is T_Menu_Preview<n>, the rest T_Menu_Preview<n>_01 ..
    self.previewClip = {}
    local frames = (MenuLayout ~= nil and MenuLayout.preview_frames) or 1
    for i = 1, STAGES do
        self.previewClip[i] = { self.previewTex[i] }
        for k = 1, frames - 1 do
            local tex = LoadAsset(string.format("T_Menu_Preview%d_%02d", i, k))
            if (tex == nil) then break end
            self.previewClip[i][k + 1] = tex
        end
    end
    self.previewClock, self.previewFrame = 0.0, 0
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


-- ------------------------------------------------------------------ the scrolling watermark
function StageSelect:BuildWatermark()
    self.mark, self.markAt = {}, 0.0
    for i = 1, MARK_COPIES do
        self.mark[i] = MakeQuad(self, LoadAsset("T_Menu_Watermark"))
    end
end

function StageSelect:PlaceWatermark()
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
function StageSelect:BlinkCursor(deltaTime)
    local arrow = self.quads.T_Menu_Cursor
    if (arrow == nil) then return end
    self.blinkAt = (self.blinkAt or 0.0) + deltaTime
    arrow:SetVisible(self.open and (self.blinkAt % (BLINK * 2.0)) < BLINK)
end

function StageSelect:ScrollWatermark(deltaTime)
    if (self.mark == nil or self.k == nil) then return end
    local p = MenuLayout.parts.T_Menu_Watermark
    local period = (p.w + MARK_GAP) * self.k
    self.markAt = (self.markAt - MARK_SPEED * self.k * deltaTime) % period
    self:PlaceWatermark()
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
    self:PlaceWatermark()
    self:PlaceSelection()
end

-- The bar and the arrow follow the cursor. This screen's bar is a thinner drawing of the
-- menu's (the rows here are 27 apart, the menu's plate 45 tall), centred on the row.
function StageSelect:PlaceSelection()
    local L = MenuLayout
    local bar = L.parts.T_Menu_SelectBarThin
    local y = ROW_TOP + (self.index - 1) * ROW_PITCH - (bar.h - ROW_SIZE) * 0.5 + BAR_DROP
    self.quads.T_Menu_SelectBarThin:SetPosition(self.left + bar.x * self.k, self.top + y * self.k)
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
    self.previewFrame = -1                                  -- so the clip is redrawn from wherever it is
    self:PlayPreview()
    -- That stage's own emerald in its own colour once it is won; until then its shadow, a
    -- black silhouette drawn half transparent, so you can see which one is missing.
    if (self.won[n] and self.emeraldTex[n] ~= nil) then
        self.emerald:SetTexture(self.emeraldTex[n])
        self.emerald:SetColor(WHITE)
    else
        self.emerald:SetTexture(self.emeraldOff or self.emeraldTex[n])
        self.emerald:SetColor(GHOST)
    end
    self.label:SetText(EMERALD_NAME[n] or "")
    local colour = EMERALD_COLOUR[n] or LABEL
    self.label:SetColor(colour)
    self.quads.T_Menu_PreviewFrame:SetColor(colour)      -- the frame is white art, tinted
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
    self:PlaceWatermark()
end

-- The picked stage's clip, on a loop. Every stage's clip runs on the same clock, so moving
-- the cursor does not restart it.
function StageSelect:PlayPreview(deltaTime)
    self.previewClock = (self.previewClock or 0.0) + (deltaTime or 0.0)
    local clip = self.previewClip and self.previewClip[self.index]
    if (clip == nil or #clip == 0) then return end
    local fps = (MenuLayout ~= nil and MenuLayout.preview_fps) or 6
    local frame = math.floor(self.previewClock * fps) % #clip
    if (frame ~= self.previewFrame) then
        self.previewFrame = frame
        self.preview:SetTexture(clip[frame + 1])
    end
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
    -- For testing without a keyboard, as the menu has: S2_SELECT_PICK=3 chooses stage 3;
    -- S2_SELECT_AT=5 only puts the cursor on stage 5, to look at it.
    if (self.open and self.autoAt == nil) then
        self.autoAt = (os ~= nil and os.getenv ~= nil and tonumber(os.getenv("S2_SELECT_AT") or "")) or false
        if (self.autoAt) then
            self.index = math.max(1, math.min(STAGES, math.floor(self.autoAt)))
            self:PlaceSelection()
            self:Refresh()
        end
    end
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
    self:ScrollWatermark(deltaTime)
    self:BlinkCursor(deltaTime)
    self:PlayPreview(deltaTime)

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
