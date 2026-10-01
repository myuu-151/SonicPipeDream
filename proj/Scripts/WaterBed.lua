-- WaterBed.lua
-- The title's sea, after Sonic Adventure's GameCube beach water: SM_WaterBed (a flat disc of
-- radius 890) wearing M_Water -- a flat blue (T_WaterBase), a black-and-white light map added on
-- UV0 (T_WaterLight) and a dimmer copy at a larger scale added on UV1 (T_WaterLightDim), drifting
-- another way so the two swim through each other, and T_WaterBump (UV1, TevMode 8) wobbling them.
-- The disc's vertex colour deepens it to the open sea's blue with distance, and its alpha fades it
-- into the sky dome's horizon haze. Like DaySky.lua it is kept
-- under the camera, here at a fixed height; and it scrolls the layers, each its own way. The disc
-- moving with the camera would drag the water along with it, so each layer's offset also takes the
-- disc's position over that layer's tile size: the sea stays put in the world, and the emblem
-- sways over it.
-- Intro.lua spawns it and puts it away again. See native/gen_title_water.py.
--
--   node:SetStaticMesh(LoadAsset("SM_WaterBed")); node:SetScript("WaterBed")
--   WaterBed:SetHeight(y)    the surface's height (default WATER_Y)
--   WaterBed:SetWarp(on)     false: wear M_WaterNoWarp, for an engine without the Warp TEV mode

WaterBed = {}

-- in step with native/gen_title_water.py
local WATER_Y = -1.6                    -- 0.3 under the emblem's lowest point
local TILE_A = 7.0                      -- world units per repeat of UV0 (T_WaterLight)
local TILE_B = 11.0                     -- ...of UV1 (T_WaterLightDim, T_WaterBump)
local DRIFT_A = { 0.04, 0.10 }          -- the light, world units a second (x, z)
local DRIFT_B = { -0.14, 0.20 }         -- the dim copy and the bump: another way
local SWELL, SWELL_SECONDS = 0.02, 7.0  -- the whole sea rising and falling, gently
local WARP_STRENGTH = 0.04              -- UV units of bend at full offset (M_Water's Emission)
local USE_WARP = true

local function Wrap(x) return x - math.floor(x) end

function WaterBed:Create()
    self.time = 0.0
    self.height = WATER_Y
    self.useWarp = USE_WARP
    self.mat = nil
end

function WaterBed:SetHeight(y)
    self.height = y
end

function WaterBed:SetWarp(on)
    self.useWarp = on
    self.mat = nil                      -- picked again on the next tick
end

function WaterBed:PickMaterial()
    if (self.useWarp) then
        self.mat = LoadAsset("M_Water")
        self:SetMaterialOverride(nil)
        if (self.mat ~= nil and self.mat.SetEmission ~= nil and self.useWarp) then self.mat:SetEmission(WARP_STRENGTH) end   -- the Warp strength lives in Emission
    else
        self.mat = LoadAsset("M_WaterNoWarp")
        if (self.mat ~= nil) then self:SetMaterialOverride(self.mat) end
    end
    if (self.mat == nil) then
        Log.Error("WaterBed: water material not found")
    end
    self:EnableCollision(false)
    self:EnableOverlaps(false)
end

function WaterBed:UpdateWater(deltaTime)
    if (self.mat == nil) then
        self:PickMaterial()
        if (self.mat == nil) then return end
    end
    self.time = self.time + deltaTime
    local t = self.time

    -- under the camera, wherever it is, rising and falling a little
    local x, z = 0.0, 0.0
    local world = self:GetWorld()
    local cam = world and world:GetActiveCamera()
    if (cam ~= nil) then
        local p = cam:GetWorldPosition()
        x, z = p.x, p.z
    end
    local y = self.height + SWELL * math.sin(t * 2.0 * math.pi / SWELL_SECONDS)
    self:SetWorldPosition(Vec(x, y, z))

    -- each layer locked to the world (the disc's position over its tile), then drifting; kept
    -- in 0-1 so a long session keeps its precision. Index 1 is UV0, 2 is UV1.
    self.mat:SetUvOffset(Vec(Wrap((x - DRIFT_A[1] * t) / TILE_A), Wrap((z - DRIFT_A[2] * t) / TILE_A)), 1)
    self.mat:SetUvOffset(Vec(Wrap((x - DRIFT_B[1] * t) / TILE_B), Wrap((z - DRIFT_B[2] * t) / TILE_B)), 2)
end

function WaterBed:Tick(deltaTime)
    self:UpdateWater(deltaTime)
end
