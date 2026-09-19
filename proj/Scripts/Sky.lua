-- Sky.lua
-- Sonic 2 special-stage sky: dome (SM_SkyDome) with M_Sky
-- (gradient + twinkling starfield + a band of diamond clusters).
--
-- Keeps the dome on the camera, and animates the twinkle by swapping the star
-- texture between frames. Attach to the SkyDome StaticMesh3D node.
--
-- The twinkle is frames rather than anything clever with the material: stars
-- have to brighten independently of each other, and a single texture with a
-- colour or opacity applied to it can only pulse all of them together.

Sky = {}

-- Lua indices here are 1-based: slot 1 is the gradient, 2 the stars, 3 the
-- diamonds.

local STAR_SLOT = 1
local STAR_FRAMES = 8

local DIAMOND_SLOT = 2
local DIAMOND_FRAMES = 8

-- The diamond layer comes in two forms and the generator decides which: five
-- static clusters with a colour band sliding through them (8 frames), or the
-- medley, a long show that moves from one pattern to the next (384 frames,
-- editor only for now). If the medley's first frame exists, that is what plays.
local MEDLEY_FRAMES = 384
-- Loading every medley frame in one go stalls the scene for seconds, so they
-- come in a few per tick, in the order they will be shown.
local MEDLEY_LOADS_PER_TICK = 8

local function MedleyName(i)
    return string.format("T_S2Sky_Medley_%03d", i)
end

function Sky:Create()
    -- Frames a second, so a full twinkle is STAR_FRAMES / this. At 16 frames
    -- that is about 1.3 seconds a cycle.
    self.twinklesPerSecond = 12.0
    self.colourShiftsPerSecond = 2.0
    -- The preview ran at 70ms a frame, which is about 14.
    self.medleyFramesPerSecond = 14.0
    self.time = 0.0
    self.frame = -1
    self.diamondFrame = -1
end

function Sky:GatherProperties()
    return
    {
        { name = "twinklesPerSecond", type = DatumType.Float },
        { name = "colourShiftsPerSecond", type = DatumType.Float },
        { name = "medleyFramesPerSecond", type = DatumType.Float },
    }
end

function Sky:UpdateSky(deltaTime)
    if (self.skyMat == nil) then
        self.skyMat = LoadAsset("M_Sky")
        if (self.skyMat == nil) then
            Log.Error("Sky: M_Sky material not found")
            return
        end

        -- Held so the frames are not loaded and unloaded every time one comes
        -- back around.
        self.starFrames = {}
        for i = 1, STAR_FRAMES do
            self.starFrames[i] = LoadAsset("T_S2Sky_Stars_" .. i)
        end

        self.diamondFrames = {}
        local first = LoadAsset(MedleyName(1))
        self.medley = (first ~= nil)
        if (self.medley) then
            self.diamondFrames[1] = first
            self.medleyLoaded = 1
            self.medleyTime = 0.0
        else
            for i = 1, DIAMOND_FRAMES do
                self.diamondFrames[i] = LoadAsset("T_S2Sky_Diamonds_" .. i)
            end
        end

        self:EnableCollision(false)
        self:EnableOverlaps(false)
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

    -- And the diamonds, slower than the stars: the colour shift is meant to
    -- read as a wave moving through the clusters, not as flickering.
    local dframe
    if (self.medley) then
        local want = self.medleyLoaded + MEDLEY_LOADS_PER_TICK
        while (self.medleyLoaded < MEDLEY_FRAMES and self.medleyLoaded < want) do
            self.medleyLoaded = self.medleyLoaded + 1
            self.diamondFrames[self.medleyLoaded] = LoadAsset(MedleyName(self.medleyLoaded))
        end

        -- Its own clock, which only runs while the next frame is in memory: on
        -- the first pass playback can catch the loader up, and waiting a tick
        -- is better than skipping ahead and showing a gap.
        local nextTime = self.medleyTime + deltaTime
        local nextFrame = math.floor(nextTime * self.medleyFramesPerSecond) % MEDLEY_FRAMES
        if (nextFrame < self.medleyLoaded) then
            self.medleyTime = nextTime
        end
        dframe = math.floor(self.medleyTime * self.medleyFramesPerSecond) % MEDLEY_FRAMES
    else
        dframe = math.floor(self.time * self.colourShiftsPerSecond) % DIAMOND_FRAMES
    end

    if (dframe ~= self.diamondFrame) then
        self.diamondFrame = dframe
        local dtex = self.diamondFrames[dframe + 1]
        if (dtex ~= nil) then
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
