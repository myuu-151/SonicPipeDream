-- DaySky.lua
-- The title's sky: the Day pack of OctaveSimpleSkies (its Sky.lua, renamed, since Sky is the
-- special stage's sky here). A dome (SM_DaySkyDome) wearing M_DaySky -- a gradient, two-tone
-- clouds and a horizon haze -- whose clouds this scrolls with the wind, kept round the camera.
-- Intro.lua spawns it and puts it away again. See native/gen_day_sky.py.

DaySky = {}

function DaySky:Create()
    -- The title's clouds come at the camera (it looks down -Z; the clouds' V runs with world Z, and
    -- a falling offset carries them toward +Z), and fast: the pack drifts them sideways at 0.02.
    self.windSpeed = 0.30
    self.windDirX = 0.0
    self.windDirY = -1.0
    self.time = 0.0
end

function DaySky:UpdateSky(deltaTime)
    if (self.skyMat == nil) then
        self.skyMat = LoadAsset("M_DaySky")
        if (self.skyMat == nil) then
            Log.Error("DaySky: M_DaySky material not found")
            return
        end
        self:EnableCollision(false)
        self:EnableOverlaps(false)
    end

    self.time = self.time + deltaTime

    -- the clouds drift (UV0); kept in 0-1 so a long session keeps its precision
    local len = math.sqrt(self.windDirX * self.windDirX + self.windDirY * self.windDirY)
    if (len < 0.0001) then len = 1.0 end
    local ox = (self.windDirX / len) * self.windSpeed * self.time
    local oy = (self.windDirY / len) * self.windSpeed * self.time
    self.skyMat:SetUvOffset(Vec(ox - math.floor(ox), oy - math.floor(oy)), 1)

    -- round the camera, wherever it is
    local world = self:GetWorld()
    local cam = world and world:GetActiveCamera()
    if (cam ~= nil) then
        self:SetWorldPosition(cam:GetWorldPosition())
    end
end

function DaySky:Tick(deltaTime)
    self:UpdateSky(deltaTime)
end
