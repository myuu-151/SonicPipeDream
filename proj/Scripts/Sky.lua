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
    self.sky = 1
    -- Frames a second, so a full twinkle is STAR_FRAMES / this.
    self.twinklesPerSecond = 12.0
    self.colourShiftsPerSecond = 2.0
    -- The preview ran at 70ms a frame, which is about 14.
    self.medleyFramesPerSecond = 14.0
    self.time = 0.0
    self.medleyTime = 0.0
    self.shownSky = -1
end

function Sky:GatherProperties()
    return
    {
        { name = "sky", type = DatumType.Integer },
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

function Sky:Tick(deltaTime)
    self:UpdateSky(deltaTime)
end

function Sky:EditorTick(deltaTime)
    self:UpdateSky(deltaTime)
end
