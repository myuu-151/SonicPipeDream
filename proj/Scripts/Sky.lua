-- Sky.lua
-- Sonic 2 special-stage sky: dome (SM_SkyDome) with M_Sky
-- (gradient + twinkling starfield, and the diamond show over them).
--
-- Keeps the dome on the camera, and animates it by swapping textures between
-- frames. Attach to the SkyDome StaticMesh3D node.
--
-- The animation is frames rather than anything clever with the material: stars
-- have to brighten independently of each other, and a single texture with a
-- colour or opacity applied to it can only pulse all of them together.
--
-- There are several skies. They share the dome and the material and differ only
-- in their textures, so changing sky is nothing more than which frames get
-- swapped in. `sky` picks one: 0 is the classic sky, 1-7 are the variants from
-- native/gen_sky_variants.py, in that script's order.

Sky = {}

Script.Require("PadInput")      -- a controller, folded into the keys the scripts ask about
Script.Require("MenuMusic")     -- the menus' music, while they are up

-- Material texture slots, 1-based: the stars (with the sky gradient under them),
-- then the diamonds.
local STAR_SLOT = 1
local DIAMOND_SLOT = 2

local STAR_FRAMES = 8
local CLUSTER_FRAMES = 8

-- Keep in step with SKIES in native/gen_sky_variants.py.
local SKY_NAMES = { "Midnight", "Dawn", "Pastel", "Sunset", "Aurora", "Inferno", "Noir" }

local MEDLEY_FRAMES = 384
-- Loading every medley frame in one go stalls the scene for seconds, so they
-- come in a few per tick, in the order they will be shown.
local MEDLEY_LOADS_PER_TICK = 8

-- Asset names for a sky. The classic one keeps its original names.
local function StarName(sky, i)
    if (sky == 0) then
        return "T_S2Sky_Stars_" .. i
    end
    return "T_Sky" .. SKY_NAMES[sky] .. "_Stars_" .. i
end

local function MedleyName(sky, i)
    if (sky == 0) then
        return string.format("T_S2Sky_Medley_%03d", i)
    end
    return string.format("T_Sky%s_Medley_%03d", SKY_NAMES[sky], i)
end

function Sky:Create()
    -- Which sky: 0 classic, 1 Midnight, 2 Dawn, 3 Pastel, 4 Sunset, 5 Aurora,
    -- 6 Inferno, 7 Noir. Change it in the inspector or from a level script.
    self.sky = 7
    -- Frames a second, so a full twinkle is STAR_FRAMES / this.
    self.twinklesPerSecond = 12.0
    self.colourShiftsPerSecond = 2.0
    -- The preview ran at 70ms a frame, which is about 14.
    self.medleyFramesPerSecond = 14.0
    self.time = 0.0
    self.medleyTime = 0.0
    self.shownSky = -1
    -- Start the playable special stage when the game runs. The sky is the one node every
    -- scene of this project already has, so starting it from here means there is nothing to
    -- set up in the editor: SpecialStage.lua spawns the track, the rings, Sonic, the camera
    -- and the UI for itself. Untick it in the inspector to look at the sky alone.
    self.startSpecialStage = true
    self.showMenu = true            -- the title menu opens over the sky; Main Game starts the stage
    TheSky = self                   -- so a stage can set `sky` to the one its palette names
    self.startedSpecialStage = false
    self.started = false
end

function Sky:GatherProperties()
    return
    {
        { name = "sky", type = DatumType.Integer },
        { name = "startSpecialStage", type = DatumType.Bool },
        { name = "showMenu", type = DatumType.Bool },
        { name = "twinklesPerSecond", type = DatumType.Float },
        { name = "medleyFramesPerSecond", type = DatumType.Float },
        { name = "colourShiftsPerSecond", type = DatumType.Float },
    }
end

-- Point the frame tables at a sky. The show keeps its place: the medley clock is
-- not reset, so a change of sky is a change of colour, not a restart.
function Sky:LoadSky(sky)
    if (sky < 0 or sky > #SKY_NAMES or LoadAsset(StarName(sky, 1)) == nil) then
        Log.Warning("Sky: no sky " .. tostring(sky) .. "; using the classic one")
        sky = 0
    end
    self.shownSky = sky

    -- Held so the frames are not loaded and unloaded every time one comes back
    -- around.
    self.starFrames = {}
    for i = 1, STAR_FRAMES do
        self.starFrames[i] = LoadAsset(StarName(sky, i))
    end

    -- The diamond layer comes in two forms and the generator decides which: the
    -- medley, a long show that moves from one pattern to the next (384 frames),
    -- or, for the classic sky only, five static clusters (8 frames). If the
    -- medley's first frame exists, that is what plays.
    self.diamondFrames = {}
    local first = LoadAsset(MedleyName(sky, 1))
    self.medley = (first ~= nil)
    if (self.medley) then
        -- Load outward from wherever the show has got to, not from frame 1, so a
        -- change of sky shows its colours on the very next tick.
        local now = math.floor(self.medleyTime * self.medleyFramesPerSecond) % MEDLEY_FRAMES
        self.diamondFrames[1] = first
        self.medleyLoaded = 1
        self.medleyCursor = now
    else
        for i = 1, CLUSTER_FRAMES do
            self.diamondFrames[i] = LoadAsset("T_S2Sky_Diamonds_" .. i)
        end
    end

    -- Force both layers to be set again on this tick.
    self.frame = -1
    self.diamondFrame = -1
end

function Sky:UpdateSky(deltaTime)
    if (self.skyMat == nil) then
        self.skyMat = LoadAsset("M_Sky")
        if (self.skyMat == nil) then
            Log.Error("Sky: M_Sky material not found")
            return
        end
        self:EnableCollision(false)
        self:EnableOverlaps(false)
    end

    local wanted = math.floor(self.sky)
    if (wanted ~= self.shownSky and not (self.shownSky == 0 and self.fellBack == wanted)) then
        self:LoadSky(wanted)
        -- Remember a sky that was asked for and is not there, or it would be
        -- looked for again on every tick.
        self.fellBack = (self.shownSky ~= wanted) and wanted or nil
    end

    self.time = self.time + deltaTime

    -- Swap the star texture only when the frame actually changes, rather than
    -- setting it every tick.
    local frame = math.floor(self.time * self.twinklesPerSecond) % STAR_FRAMES
    if (frame ~= self.frame) then
        self.frame = frame
        local tex = self.starFrames[frame + 1]
        if (tex ~= nil) then
            self.skyMat:SetTexture(STAR_SLOT, tex)
        end
    end

    local dframe
    if (self.medley) then
        -- Bring in a few more frames, working forward from the cursor and round.
        local budget = MEDLEY_LOADS_PER_TICK
        while (budget > 0 and self.medleyLoaded < MEDLEY_FRAMES) do
            local i = (self.medleyCursor % MEDLEY_FRAMES) + 1
            if (self.diamondFrames[i] == nil) then
                self.diamondFrames[i] = LoadAsset(MedleyName(self.shownSky, i))
                self.medleyLoaded = self.medleyLoaded + 1
                budget = budget - 1
            end
            self.medleyCursor = self.medleyCursor + 1
        end

        -- Its own clock, which only runs while the next frame is in memory:
        -- playback can catch the loader up, and waiting a tick is better than
        -- skipping ahead and showing a gap.
        local nextTime = self.medleyTime + deltaTime
        local nextFrame = math.floor(nextTime * self.medleyFramesPerSecond) % MEDLEY_FRAMES
        if (self.diamondFrames[nextFrame + 1] ~= nil) then
            self.medleyTime = nextTime
        end
        dframe = math.floor(self.medleyTime * self.medleyFramesPerSecond) % MEDLEY_FRAMES
    else
        dframe = math.floor(self.time * self.colourShiftsPerSecond) % CLUSTER_FRAMES
    end

    if (dframe ~= self.diamondFrame) then
        local dtex = self.diamondFrames[dframe + 1]
        if (dtex ~= nil) then
            self.diamondFrame = dframe
            self.skyMat:SetTexture(DIAMOND_SLOT, dtex)
        end
    end

    -- Camera-anchored dome.
    local world = self:GetWorld()
    local cam = world and world:GetActiveCamera()
    if (cam ~= nil) then
        self:SetWorldPosition(cam:GetWorldPosition())
    end
end

-- The menu comes first, over the sky, and the stage starts when Main Game is chosen. Set
-- `startSpecialStage` and untick `showMenu` in the inspector to skip straight to playing,
-- which is what the S2_NOMENU environment variable does as well.
function Sky:StartSpecialStage(which)
    if (not self.startedSpecialStage) then
        self.startedSpecialStage = true
        local stage = self:GetWorld():SpawnNode("Node3D")
        stage:SetName("SpecialStage")
        stage:SetScript("SpecialStage")
        -- The script's Create picked stage 1 (or S2_STAGE); the stage select overrides it
        -- before the first Tick builds anything.
        if (which ~= nil and TheSpecialStage ~= nil) then TheSpecialStage.stage = which end
        return
    end
    -- Been here before: the node is still in the world with its meshes loaded, so it is put
    -- back to work rather than built again.
    if (TheSpecialStage ~= nil) then TheSpecialStage:Enter(which) end
end

-- Three screens in one world: the menu, the stage select it leads to, and the stage itself.
-- The two screens are Canvases that hide rather than unload, so going back to one is instant
-- and neither has to be built twice.
function Sky:ShowMenu()
    local world = self:GetWorld()
    local menu = world:SpawnNode("Canvas")
    menu:SetName("Menu")
    menu:SetScript("Menu")
    local select = world:SpawnNode("Canvas")
    select:SetName("StageSelect")
    select:SetScript("StageSelect")
    local prompt = world:SpawnNode("Canvas")
    prompt:SetName("SavePrompt")
    prompt:SetScript("SavePrompt")
    local options = world:SpawnNode("Canvas")
    options:SetName("OptionsPrompt")
    options:SetScript("OptionsPrompt")
    local loading = world:SpawnNode("Canvas")
    loading:SetName("Loading")
    loading:SetScript("Loading")

    -- TheMenu and TheStageSelect are set by each script's Create, which has run by the time
    -- SetScript returns.
    if (TheStageSelect ~= nil) then
        TheStageSelect:Close()
        TheStageSelect.onChoose = function(stage)
            TheStageSelect:Close()
            -- A stage not played last time comes in behind a short loading screen, as on the
            -- GameCube (the PC hardly needs one: it is for the look). Going back into the same
            -- stage does not show it, nor does a restart, which never leaves the stage.
            if (stage ~= self.lastStage and TheLoading ~= nil) then
                local won = TheStageSelect.won ~= nil and TheStageSelect.won[stage]
                TheLoading:Show(stage, won)
                self.stageStart = { stage = stage, step = 0, clock = 0.0 }
                return
            end
            self:EnterStage(stage)
        end
        TheStageSelect.onBack = function()
            TheStageSelect:Close()
            if (TheMenu ~= nil) then TheMenu:Open() end
        end
    end
    if (TheMenu ~= nil) then
        TheMenu.onChoose = function(key)
            if (key == "main_game" and TheStageSelect ~= nil) then
                TheMenu:Close()
                TheStageSelect:Open()
            elseif (key == "options" and TheOptions ~= nil) then
                -- the options, over the menu; the menu keeps still until they close
                TheMenu.busy = true
                TheOptions.onClose = function() TheMenu.busy = false end
                TheOptions.onStart = nil
                TheOptions:Open()
            elseif ((key == "save" or key == "load") and TheSavePrompt ~= nil) then
                -- the Saves folder, over the menu; the menu keeps still until it closes
                TheMenu.busy = true
                TheSavePrompt.onClose = function() TheMenu.busy = false end
                TheSavePrompt:Open(key)
            elseif ((key == "marathon" or key == "time_attack") and TheOptions ~= nil) then
                -- its setup first (OptionsPrompt.lua); START there begins the run: zone after zone,
                -- made as it is played (MarathonGen.lua), behind the loading screen while its first
                -- zone is built (see TickMarathonStart). A time attack is the same run, against the
                -- clock (SpecialStage.lua: data.timeAttack).
                local run = (key == "time_attack") and "timeAttack" or "marathon"
                TheMenu.busy = true
                TheOptions.onClose = function() TheMenu.busy = false end
                TheOptions.onStart = function()
                    TheOptions.onStart = nil
                    GameOptions.run = run
                    TheMenu:Close()
                    if (TheLoading ~= nil) then TheLoading:Show(key) end
                    self.marathonStart = { step = 0, clock = 0.0 }
                end
                TheOptions:Open(run)
            end
        end
    end
end

-- A stage from the stage select: started, and handing back to the select when it is over.
function Sky:EnterStage(stage)
    self.lastStage = stage
    self:StartSpecialStage(stage)
    -- The stage hands back here when its emerald is taken.
    if (TheSpecialStage ~= nil) then
        TheSpecialStage.onExit = function()
            TheStageSelect:Open()           -- paused and EXIT chosen
        end
        TheSpecialStage.onFinished = function(won)
            TheStageSelect:SetWon(won, true)
            -- All seven emeralds is what MARATHON waits for.
            if (TheStageSelect:AllWon() and TheMenu ~= nil) then
                TheMenu:SetUnlocked("marathon", true)
            end
            TheStageSelect:Open()
        end
    end
end

-- Into a marathon, behind the loading screen: shown for a frame first, so it is up before the
-- first zone is built; then the stage; then the screen comes down once the stage has drawn and it
-- has been up long enough to read -- and the run starts from the top, so the START run-up is
-- seen whole.
local LOADING_AT_LEAST = 1.0

function Sky:TickMarathonStart(deltaTime)
    local m = self.marathonStart
    m.clock = m.clock + deltaTime
    if (m.step == 0) then
        m.step = 1                                  -- the loading screen is drawn this frame
    elseif (m.step == 1) then
        self.lastStage = "Marathon"
        self:StartSpecialStage("Marathon")
        if (TheSpecialStage ~= nil) then
            TheSpecialStage.onExit = function() TheMenu:Open() end
            TheSpecialStage.onFinished = function() TheMenu:Open() end
        end
        m.step = 2
    elseif (TheSpecialStage ~= nil and TheSpecialStage.built and TheSpecialStage.data ~= nil
            and TheSpecialStage.data.marathon and m.clock >= LOADING_AT_LEAST) then
        TheSpecialStage:Restart()
        if (TheLoading ~= nil) then TheLoading:Hide() end
        self.marathonStart = nil
    end
end

-- Into a stage from the stage select, the same way: the screen up, the stage, the screen down.
local STAGE_LOADING_AT_LEAST = 0.8

function Sky:TickStageStart(deltaTime)
    local m = self.stageStart
    m.clock = m.clock + deltaTime
    if (m.step == 0) then
        m.step = 1                                  -- the loading screen is drawn this frame
    elseif (m.step == 1) then
        self:EnterStage(m.stage)
        m.step = 2
    elseif (TheSpecialStage ~= nil and TheSpecialStage.built and TheSpecialStage.stage == m.stage
            and m.clock >= STAGE_LOADING_AT_LEAST) then
        TheSpecialStage:Restart()                   -- from the top, so START is seen whole
        if (TheLoading ~= nil) then TheLoading:Hide() end
        self.stageStart = nil
    end
end

function Sky:Tick(deltaTime)
    -- Tick is the GAME's; the editor calls EditorTick. So nothing starts in the editor.
    if (self.marathonStart ~= nil) then self:TickMarathonStart(deltaTime) end
    if (self.stageStart ~= nil) then self:TickStageStart(deltaTime) end
    MenuMusic.Tick(deltaTime)
    if (not self.started) then
        self.started = true
        local skipMenu = (os ~= nil and os.getenv ~= nil and os.getenv("S2_NOMENU") ~= nil)
        if (self.showMenu and not skipMenu) then
            self:ShowMenu()
        elseif (self.startSpecialStage) then
            self:StartSpecialStage()
        end
    end
    self:UpdateSky(deltaTime)
end

function Sky:EditorTick(deltaTime)
    self:UpdateSky(deltaTime)
end
