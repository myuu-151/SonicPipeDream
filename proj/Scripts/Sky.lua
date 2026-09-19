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
local STAR_SLOT = 2
local STAR_FRAMES = 8

local DIAMOND_SLOT = 3
local DIAMOND_FRAMES = 8

function Sky:Create()
    -- Frames a second, so a full twinkle is STAR_FRAMES / this. At 16 frames
    -- that is about 1.3 seconds a cycle.
    self.twinklesPerSecond = 12.0
    self.colourShiftsPerSecond = 2.0
    self.time = 0.0
    self.frame = -1
    self.diamondFrame = -1
end

function Sky:GatherProperties()
    return
    {
        { name = "twinklesPerSecond", type = DatumType.Float },
        { name = "colourShiftsPerSecond", type = DatumType.Float },
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
        for i = 1, DIAMOND_FRAMES do
            self.diamondFrames[i] = LoadAsset("T_S2Sky_Diamonds_" .. i)
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
    local dframe = math.floor(self.time * self.colourShiftsPerSecond) % DIAMOND_FRAMES
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
