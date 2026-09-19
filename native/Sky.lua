-- Sky.lua
-- Windward-style sky: hemisphere dome (SM_SkyDome) with M_Sky material
-- (gradient + baked two-tone FBM clouds + horizon haze).
-- This script scrolls the cloud layer with wind and keeps the dome
-- anchored to the active camera. Attach to the SkyDome StaticMesh3D node.

Sky = {}

function Sky:Create()
    self.windSpeed = 0.02
    self.windDirX = 1.0
    self.windDirY = 0.35
    self.time = 0.0
end

function Sky:GatherProperties()
    return
    {
        { name = "windSpeed", type = DatumType.Float },
        { name = "windDirX", type = DatumType.Float },
        { name = "windDirY", type = DatumType.Float },
    }
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

    self.time = self.time + deltaTime

    -- wind scroll on UV0 (cloud layer); wrap to keep precision over long sessions
    local len = math.sqrt(self.windDirX * self.windDirX + self.windDirY * self.windDirY)
    if (len < 0.0001) then len = 1.0 end
    local ox = (self.windDirX / len) * self.windSpeed * self.time
    local oy = (self.windDirY / len) * self.windSpeed * self.time
    self.skyMat:SetUvOffset(Vec(ox - math.floor(ox), oy - math.floor(oy)), 1)

    -- camera-anchored dome
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
