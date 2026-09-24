-- SavePrompt.lua
-- What SAVE and LOAD on the title menu open. On the GameCube it is about the
-- memory card in slot A; on the PC about the SAVES FOLDER beside the game -- a folder of its own,
-- holding the save file (`emeralds`), which can be copied out, or a save copied in from Windows
-- Explorer and loaded.
--
--     +--------------------------------------------+
--     |            MEMORY CARD  SLOT A             |       or  SAVES FOLDER
--     |                                            |
--     |      SAVE TO THE MEMORY CARD IN SLOT A     |
--     |   SAVING NEEDS 1 BLOCK     250 BLOCKS FREE  |
--     |                                            |
--     |            A  SAVE        B  BACK          |
--     +--------------------------------------------+
--
-- SAVE says, as the case is -- on the GameCube: no card; not a memory card; damaged or not
-- formatted; another region's card; FULL (with the blocks it needs and the blocks free); or ready
-- to save, a new file or over the game's own. On the PC: a new save in the folder, or over the one
-- there. LOAD says what save the card, or the folder, holds -- how many emeralds -- or that there is
-- none (and on the GameCube, what is wrong with slot A, when something is). The card, or the
-- folder, is looked at again every second while this is up, so a card put in, or a file dropped
-- into the folder, shows at once.
--
-- The GameCube's save is one block: the emeralds, and the name and icon the card's own screen
-- shows (SaveInfo.lua, handed to the engine by Screens.lua).
--
--     TheSavePrompt:Open(mode)   "save" (the default) or "load"; over the menu, which keeps still
--     TheSavePrompt.onClose      called when it closes

Script.Require("GameOptions")

SavePrompt = {}

local SAVE = "emeralds"                 -- StageSelect.lua's save
local SAVE_BYTES = 64                   -- the emeralds as written, rounded well up: still one block
local LOOK_EVERY = 1.0                  -- seconds between looks at the card, or the folder
local STAGES = 7

-- Blue and yellow on white: never red against green (the owner reads neither apart).
local WHITE = Vec(1.0, 1.0, 1.0, 1.0)
local YELLOW = Vec(1.0, 0.84, 0.18, 1.0)
local SKY = Vec(0.45, 0.78, 1.0, 1.0)
local DIM = Vec(0.0, 0.0, 0.0, 0.55)
local BOX = Vec(0.02, 0.10, 0.42, 0.94)
local EDGE = Vec(0.45, 0.78, 1.0, 1.0)

-- Sized for a 480-line screen (the GameCube's), and scaled up with the window on the PC.
local REF_H = 480.0
local BOX_W, BOX_H = 540.0, 214.0

local function Blocks(n)
    return n .. ((n == 1) and " BLOCK" or " BLOCKS")
end

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

-- A memory card to talk about (the GameCube), or the Saves folder (anywhere else).
local function OnCard()
    if (System.GetSaveCard == nil) then return false end
    return System.GetSaveCard(SAVE, SAVE_BYTES) ~= "none"
end

-- The emeralds a save holds, read without taking them: nil if there is no save.
local function EmeraldsIn()
    if (System.DoesSaveExist == nil or not System.DoesSaveExist(SAVE)) then return nil end
    local stream = Stream.Create()
    System.ReadSave(SAVE, stream)
    stream:SetPos(0)
    local text = stream:ReadString() or ""
    local n = 0
    for i = 1, math.min(STAGES, #text) do
        if (text:sub(i, i) == "1") then n = n + 1 end
    end
    return n
end

function SavePrompt:Create()
    self.built = false
    self.shown = false
    self.mode = "save"
    TheSavePrompt = self
end

function SavePrompt:Build()
    self.dim = MakeQuad(self, DIM)
    self.edge = MakeQuad(self, EDGE)
    self.box = MakeQuad(self, BOX)
    local font = LoadAsset("F_SonicUI")
    self.title = MakeText(self, font, YELLOW)
    self.lines = {}
    for i = 1, 3 do self.lines[i] = MakeText(self, font, WHITE) end
    self.buttons = MakeText(self, font, SKY)
    self.built = true
    self:Show(false)
end

-- Laid out every tick while it shows: text is centred by its measured width, known once drawn,
-- and on the PC the window can change size.
function SavePrompt:Place()
    local res = Renderer.GetScreenResolution()
    local w, h = res.x, res.y
    local k = h / REF_H
    self:SetAnchorMode(AnchorMode.TopLeft)
    self:SetPosition(0.0, 0.0)
    self:SetDimensions(w, h)
    self.dim:SetPosition(0.0, 0.0)
    self.dim:SetDimensions(w, h)
    local bw, bh = BOX_W * k, BOX_H * k
    local x, top = (w - bw) * 0.5, (h - bh) * 0.5
    self.edge:SetPosition(x - 3.0 * k, top - 3.0 * k)
    self.edge:SetDimensions(bw + 6.0 * k, bh + 6.0 * k)
    self.box:SetPosition(x, top)
    self.box:SetDimensions(bw, bh)
    self.title:SetTextSize(22.0 * k)
    for _, t in ipairs(self.lines) do t:SetTextSize(15.0 * k) end
    self.buttons:SetTextSize(16.0 * k)
    local function Centre(t, y)
        local wide = (t.GetTextWidth ~= nil) and t:GetTextWidth() or 0.0
        t:SetPosition((w - wide) * 0.5, top + y * k)
    end
    Centre(self.title, 20.0)
    for i, t in ipairs(self.lines) do Centre(t, 66.0 + (i - 1) * 28.0) end
    Centre(self.buttons, BOX_H - 40.0)
end

function SavePrompt:Say(a, b, c, buttons)
    self.lines[1]:SetText(a or "")
    self.lines[2]:SetText(b or "")
    self.lines[3]:SetText(c or "")
    self.buttons:SetText(buttons or "")
end

-- Look at the card, or the folder, and say what is there. (No punctuation: the HUD font has
-- letters, digits and spaces, and none of . ? ' ( ).)
function SavePrompt:Look()
    local back = "B  BACK"
    self.lookIn = LOOK_EVERY
    if (self.mode == "load") then
        self.title:SetText(self.onCard and "MEMORY CARD  SLOT A" or "SAVES FOLDER")
        if (self.onCard) then
            -- what is in slot A first: no card, or one that cannot be read, says so
            local state = System.GetSaveCard(SAVE, SAVE_BYTES)
            local problem = {
                nocard = { "THERE IS NO MEMORY CARD IN SLOT A", "PUT ONE IN TO LOAD" },
                wrongdevice = { "THE DEVICE IN SLOT A IS NOT", "A MEMORY CARD" },
                damaged = { "THE MEMORY CARD IN SLOT A IS DAMAGED", "OR NOT FORMATTED" },
                encoding = { "THE MEMORY CARD IN SLOT A IS", "FROM ANOTHER REGION" },
                busy = { "THE MEMORY CARD IN SLOT A", "CANNOT BE READ" },
                error = { "THE MEMORY CARD IN SLOT A", "CANNOT BE READ" },
            }
            if (problem[state] ~= nil) then
                self.state = state
                self:Say(problem[state][1], problem[state][2], nil, back)
                return
            end
        end
        local n = EmeraldsIn()
        local where = self.onCard and "ON THE MEMORY CARD IN SLOT A" or "IN THE SAVES FOLDER"
        if (n == nil) then
            self.state = "nofile"
            self:Say("THERE IS NO SONIC PIPE DREAM SAVE", where,
                     (not self.onCard) and "PUT ONE THERE TO LOAD IT" or nil, back)
        else
            self.state = "loadable"
            self:Say("LOAD THE SAVE " .. where, n .. " OF " .. STAGES .. " EMERALDS", nil,
                     "A  LOAD        B  BACK")
        end
        return
    end

    local yesNo = "A  SAVE        B  BACK"
    if (not self.onCard) then
        self.title:SetText("SAVES FOLDER")
        if (System.DoesSaveExist ~= nil and System.DoesSaveExist(SAVE)) then
            self.state = "exists"
            self:Say("SAVE OVER THE SAVE IN THE SAVES FOLDER", "BESIDE THE GAME", nil, yesNo)
        else
            self.state = "ready"
            self:Say("SAVE TO THE SAVES FOLDER", "BESIDE THE GAME", nil, yesNo)
        end
        return
    end

    self.title:SetText("MEMORY CARD  SLOT A")
    local state, needed, free = System.GetSaveCard(SAVE, SAVE_BYTES)
    if (needed == nil or needed <= 0) then needed = 1 end      -- no card to ask: the save is one block
    self.state = state
    local need = "SAVING NEEDS " .. Blocks(needed)
    local space = need .. "     " .. Blocks(free) .. " FREE"
    if (state == "ready") then
        self:Say("SAVE TO THE MEMORY CARD IN SLOT A", space, nil, yesNo)
    elseif (state == "exists") then
        self:Say("SAVE OVER YOUR SONIC PIPE DREAM DATA", "ON THE MEMORY CARD IN SLOT A",
                 "IT USES " .. Blocks(needed), yesNo)
    elseif (state == "full") then
        local why = (free >= needed) and "IT HAS NO ROOM FOR ANOTHER FILE" or space
        self:Say("THE MEMORY CARD IN SLOT A IS FULL", why,
                 "MAKE ROOM ON IT FROM THE GAMECUBE MENU", back)
    elseif (state == "nocard") then
        self:Say("THERE IS NO MEMORY CARD IN SLOT A", "PUT ONE IN TO SAVE", need, back)
    elseif (state == "wrongdevice") then
        self:Say("THE DEVICE IN SLOT A IS NOT", "A MEMORY CARD", need, back)
    elseif (state == "damaged") then
        self:Say("THE MEMORY CARD IN SLOT A IS DAMAGED", "OR NOT FORMATTED",
                 "FORMAT IT FROM THE GAMECUBE MENU", back)
    elseif (state == "encoding") then
        self:Say("THE MEMORY CARD IN SLOT A IS", "FROM ANOTHER REGION", need, back)
    else
        self:Say("THE MEMORY CARD IN SLOT A", "CANNOT BE READ", need, back)
    end
end

function SavePrompt:CanAct()
    if (self.mode == "load") then return self.state == "loadable" end
    return self.state == "ready" or self.state == "exists"
end

function SavePrompt:Show(visible)
    self.shown = visible and true or false
    if (self.built) then self:SetVisible(self.shown) end
end

function SavePrompt:Open(mode)
    if (not self.built) then self:Build() end
    self.mode = mode or "save"
    self.onCard = OnCard()
    self.step, self.armed = "look", false
    self:Show(true)
    self:Look()
    self:Place()
end

function SavePrompt:Close()
    self:Show(false)
    if (self.onClose ~= nil) then self.onClose() end
end

-- As the menus: not armed until the key that opened it is let go.
function SavePrompt:Armed()
    if (self.armed) then return true end
    if (not Input.IsKeyDown(Key.Enter) and not Input.IsKeyDown(Key.Space)
        and not Input.IsKeyDown(Key.Backspace)) then
        self.armed = true
    end
    return false
end

function SavePrompt:Tick(deltaTime)
    if (not self.built) then self:Build() end
    if (not self.shown) then return end
    -- over the menus, which were spawned before it: attached again, it draws last
    self:Attach(self:GetWorld():GetRootNode(), false)
    self:Place()

    if (self.step == "working") then
        -- "SAVING" / "LOADING" has been on the screen for a frame; now the work (it holds the game still)
        self.step, self.armed = "done", false
        local select = TheStageSelect
        if (self.mode == "load") then
            local ok = select ~= nil and EmeraldsIn() ~= nil
            if (ok) then
                GameOptions.touched = false         -- a save loaded on purpose brings its settings
                select:LoadWon()
                if (select.built) then select:Refresh() end
                local n = 0
                for i = 1, STAGES do if (select.won[i]) then n = n + 1 end end
                self:Say("LOADED", n .. " OF " .. STAGES .. " EMERALDS", nil, "A  OK")
                if (MenuSound ~= nil) then MenuSound("MenuSelect", 0.7) end
            else
                self:Say("THE SAVE COULD NOT BE LOADED", nil, nil, "A  OK")
            end
            return
        end
        local ok = select ~= nil and select:SaveWon(true)
        if (ok) then
            self:Say("SAVED", self.onCard and nil or "TO THE SAVES FOLDER", nil, "A  OK")
            if (MenuSound ~= nil) then MenuSound("MenuSelect", 0.7) end
        else
            self:Say("THE SAVE DID NOT WORK", self.onCard and "CHECK THE MEMORY CARD IN SLOT A" or nil,
                     "AND TRY AGAIN", "A  OK")
        end
        return
    end

    if (self.step == "look") then
        self.lookIn = (self.lookIn or LOOK_EVERY) - deltaTime
        if (self.lookIn <= 0.0) then self:Look() end
    end

    if (not self:Armed()) then return end
    local yes = Input.IsKeyJustDown(Key.Enter) or Input.IsKeyJustDown(Key.Space)
    local no = Input.IsKeyJustDown(Key.Backspace) or Input.IsKeyJustDown(Key.Escape)
    if (self.step == "done") then
        if (yes or no) then self:Close() end
    elseif (no) then
        if (MenuSound ~= nil) then MenuSound("MenuBack") end
        self:Close()
    elseif (yes and self:CanAct()) then
        if (self.mode == "load") then
            self:Say("LOADING", nil, nil, nil)
        else
            self:Say("SAVING", self.onCard and "DO NOT TOUCH THE MEMORY CARD" or nil,
                     self.onCard and "OR THE POWER BUTTON" or nil, nil)
        end
        self.step = "working"
    end
end
