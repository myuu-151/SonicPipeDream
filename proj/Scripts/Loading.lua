-- Loading.lua
-- (It began as the GameCube build's own; the PC's marathon uses it too now. Sized for a 480-line
-- television and scaled with the window, so on the GameCube it is as it always was.)
--
-- The screen between the stage select and a stage, and back. The PC goes straight from one to
-- the other, because it keeps everything in memory at once. This machine cannot: the menus and a
-- stage are never loaded together (Screens.lua puts one away before bringing the other in), and
-- a stage's pipe, emerald and sky take a few seconds to come off the disc. This is what is on
-- the screen meanwhile:
--
--                          (that stage's emerald)
--                               STAGE 3
--                               PURPLE
--                                                    NOW LOADING
--
-- The emerald is the stage select's: in colour once it has been won, its black shadow until
-- then. Going back to the menus there is no stage to name, and only NOW LOADING shows. Going into
-- a MARATHON it says so, over the emerald its first zone leads to.
--
--     TheLoading:Show(stage, won)    stage nil: NOW LOADING alone; "marathon": the marathon's
--     TheLoading:Hide()

Loading = {}

Script.Require("MenuLayout")            -- the emerald texture's padding

local WHITE = Vec(1.0, 1.0, 1.0, 1.0)
local BLACK = Vec(0.0, 0.0, 0.0, 1.0)
-- An emerald not yet won. The stage select shows its black silhouette on the yellow panel; on
-- this black screen that would be nothing, so here it is the gem itself, faint.
local GHOST = Vec(1.0, 1.0, 1.0, 0.22)
-- As StageSelect.lua (they are its locals): each stage's emerald, its colour and its name.
local EMERALD_NAME = { "BLUE", "YELLOW", "PURPLE", "GREEN", "RED", "SKY", "WHITE" }
local EMERALD_COLOUR = {
    Vec(0.12, 0.38, 1.00, 1.0), Vec(1.00, 0.82, 0.12, 1.0), Vec(0.62, 0.22, 0.92, 1.0),
    Vec(0.12, 0.78, 0.32, 1.0), Vec(0.92, 0.16, 0.16, 1.0), Vec(0.32, 0.78, 1.00, 1.0),
    Vec(1.00, 1.00, 1.00, 1.0),
}
local BLINK = 0.45                          -- NOW LOADING: on, then off, this long each
local REF_H = 480.0                         -- the height it is drawn for (the GameCube's); scaled to others
local MARGIN = 0.06                         -- of the screen kept clear at the edges: a TV's overscan

local function MakeText(parent, font, size)
    local t = parent:CreateChild("Text")
    if (font ~= nil) then t:SetFont(font) end
    t:SetAnchorMode(AnchorMode.TopLeft)
    t:SetTextSize(size)
    t:SetColor(WHITE)
    t:SetText("")
    return t
end

function Loading:Create()
    self.built = false
    self.shown = false
    self.clock = 0.0
    TheLoading = self
end

function Loading:Build()
    local res = Renderer.GetScreenResolution()
    self.w, self.h = res.x, res.y
    self:SetAnchorMode(AnchorMode.TopLeft)
    self:SetPosition(0.0, 0.0)
    self:SetDimensions(self.w, self.h)

    self.back = self:CreateChild("Quad")
    self.back:SetAnchorMode(AnchorMode.TopLeft)
    self.back:SetPosition(0.0, 0.0)
    self.back:SetDimensions(self.w, self.h)
    self.back:SetColor(BLACK)

    self.gem = self:CreateChild("Quad")
    self.gem:SetAnchorMode(AnchorMode.TopLeft)

    local font = LoadAsset("F_SonicUI")
    self.title = MakeText(self, font, 44.0)
    self.name = MakeText(self, font, 24.0)
    self.wait = MakeText(self, font, 18.0)
    self.font = font
    self.wait:SetText("NOW LOADING")
    -- a line for testing (GcTest.free): what has arrived, and free memory
    self.debug = self:CreateChild("Text")
    self.debug:SetAnchorMode(AnchorMode.TopLeft)
    self.debug:SetPosition(self.w * MARGIN, self.h * (1.0 - MARGIN) - 18.0)
    self.debug:SetTextSize(14.0)
    self.debug:SetColor(Vec(0.3, 0.9, 1.0, 1.0))
    self.debug:SetText("")

    self.built = true
    self:Refresh()
end

-- Text is centred by its measured width, which is only known once it has been drawn: so every
-- tick while it shows.
function Loading:Place()
    local res = Renderer.GetScreenResolution()
    if (res.x ~= self.w or res.y ~= self.h) then        -- (a PC window can change size)
        self.w, self.h = res.x, res.y
        self:SetDimensions(self.w, self.h)
        self.back:SetDimensions(self.w, self.h)
    end
    local k = self.h / REF_H
    self.title:SetTextSize(44.0 * k)
    self.name:SetTextSize(24.0 * k)
    self.wait:SetTextSize(18.0 * k)
    local function Centre(t, y)
        local wide = (t.GetTextWidth ~= nil) and t:GetTextWidth() or 0.0
        t:SetPosition((self.w - wide) * 0.5, y)
    end
    local gemW, gemH = 76.0 * k, 60.0 * k   -- the select's emerald at twice its size there
    self.gem:SetPosition((self.w - gemW) * 0.5, self.h * 0.5 - 118.0 * k)
    -- the texture is padded to 64 x 32 with the gem's 38 x 30 at its top left (MenuLayout.lua)
    local part = MenuLayout ~= nil and MenuLayout.parts.T_Menu_Emerald1
    if (part ~= nil) then
        self.gem:SetDimensions(gemW * part.cw / part.aw, gemH * part.ch / part.ah)
    else
        self.gem:SetDimensions(gemW, gemH)
    end
    Centre(self.title, self.h * 0.5 - 44.0 * k)
    Centre(self.name, self.h * 0.5 + 10.0 * k)
    local wide = (self.wait.GetTextWidth ~= nil) and self.wait:GetTextWidth() or 0.0
    self.wait:SetPosition(self.w * (1.0 - MARGIN) - wide, self.h * (1.0 - MARGIN) - 22.0 * k)
end

function Loading:Refresh()
    if (not self.built) then return end
    local n = self.stage
    self:SetVisible(self.shown)
    local named = self.shown and n ~= nil
    self.title:SetVisible(named)
    self.name:SetVisible(named)
    self.gem:SetVisible(named)
    if (named and n == "marathon") then
        -- the emerald the first zone leads to (SpecialStage.lua's SpawnItem: the first of them)
        self.title:SetText("MARATHON")
        self.name:SetText(EMERALD_NAME[1])
        self.name:SetColor(EMERALD_COLOUR[1])
        self.gem:SetTexture(LoadAsset("T_Menu_Emerald1"))
        self.gem:SetColor(WHITE)
    elseif (named) then
        self.title:SetText("STAGE " .. n)
        self.name:SetText(EMERALD_NAME[n] or "")
        self.name:SetColor(EMERALD_COLOUR[n] or WHITE)
        self.gem:SetTexture(LoadAsset("T_Menu_Emerald" .. n))
        self.gem:SetColor(self.won and WHITE or GHOST)
    end
    self:Place()
end

function Loading:Show(stage, won)
    self.stage, self.won, self.shown = stage, won and true or false, true
    self.clock = 0.0
    self:Refresh()
end

function Loading:SetDebug(text)
    if (self.built) then self.debug:SetText(text) end
end

function Loading:Hide()
    self.shown = false
    self:Refresh()
end

function Loading:Tick(deltaTime)
    if (not self.built) then self:Build() end
    if (not self.shown) then return end
    -- Drawn over everything: canvases draw in the order they sit in the world, and the stage's
    -- HUD is spawned while this is up, after it. Attaching again puts it back at the end. (The
    -- world gathers what it ticks before ticking any of it, so this is safe mid-tick.)
    self:Attach(self:GetWorld():GetRootNode(), false)
    self.clock = self.clock + deltaTime
    self.wait:SetVisible((self.clock % (BLINK * 2.0)) < BLINK)
    self:Place()
end
