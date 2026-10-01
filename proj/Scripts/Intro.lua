-- Intro.lua
-- The title screen. Before the menus: the winged emblem over the sea in a day sky, Sonic popping up from
-- behind its ribbon to a thumbs up, the title theme playing once, the camera swaying gently
-- from side to side; then PRESS START, and START (or A, or Enter) goes on to the menus.
--
-- A Canvas script (its one widget is PRESS START); everything else it spawns into the world and
-- takes away again when it is done. Sky:ShowMenu spawns it first and is called back
-- (onDone) to put up the menus. S2_NOINTRO skips it.
--
-- The assets are made in Blender and written by native/export_intro.py (the emblem: the ring
-- and ribbon wearing pictures of themselves, the wings chrome, from a matcap; Sonic, a mesh a
-- frame of the IntroPop action), native/gen_day_sky.py (the sky: OctaveSimpleSkies' Day pack),
-- native/gen_title_water.py (the sea) and
-- native/gen_music_assets.py (SW_TitleTheme). They
-- sit where they were in Blender: the emblem's middle is the origin and it faces +Z.

Intro = {}

local FPS, FRAMES = 24, 96              -- IntroPop: 24 a second, 96 frames, the pose held from 35
-- Of the 96, only 37 differ: until FIRST_MOVING he is out of sight below the ribbon (all as frame 0),
-- and from STILL_FROM he holds the pose (all as that one). Only those are loaded -- the title has to
-- fit beside the sky's stars when B on the menu brings it back -- and the rest shown by them.
local FIRST_MOVING, STILL_FROM = 11, 46
local function SonicFrame(f)
    if (f < FIRST_MOVING) then return 0 end
    return math.min(f, STILL_FROM)
end
local PRESS_AFTER = FRAMES / FPS + 0.3  -- PRESS START comes up once he has struck the pose
local BLINK = 0.55                      -- on, then off, this long each
local VOLUME = 2.0                      -- the title theme is quiet in its file: played up

-- The camera: in front, swinging a little to each side and back, always on the emblem.
local DISTANCE = 8.0                    -- as far as Blender's camera stood
local AIM = { 0.0, -0.10, 0.0 }         -- a little below the middle: room for PRESS START under it
local VIEW_WIDTH = 4.8                  -- what is across the screen at the emblem, at the widest it gets
local SWAY_DEGREES = 7.0                -- to each side
local SWAY_SECONDS = 9.0                -- there and back
local LIFT_DEGREES = 3.0                -- looking a touch down on it

local function Add(a, b) return { a[1] + b[1], a[2] + b[2], a[3] + b[3] } end
local function Sub(a, b) return { a[1] - b[1], a[2] - b[2], a[3] - b[3] } end
local function Scale(a, k) return { a[1] * k, a[2] * k, a[3] * k } end
local function Cross(a, b)
    return { a[2] * b[3] - a[3] * b[2], a[3] * b[1] - a[1] * b[3], a[1] * b[2] - a[2] * b[1] }
end
local function Normalize(a)
    local l = math.sqrt(a[1] * a[1] + a[2] * a[2] + a[3] * a[3])
    if (l < 1e-6) then return { 0, 1, 0 } end
    return { a[1] / l, a[2] / l, a[3] / l }
end
local function ToVec(a) return Vec(a[1], a[2], a[3]) end

-- A rotation from the three axes it turns X, Y and Z onto (as SpecialStage.lua).
local function QuatFromAxes(x, y, z)
    local m00, m01, m02 = x[1], y[1], z[1]
    local m10, m11, m12 = x[2], y[2], z[2]
    local m20, m21, m22 = x[3], y[3], z[3]
    local trace = m00 + m11 + m22
    local qx, qy, qz, qw
    if (trace > 0.0) then
        local s = math.sqrt(trace + 1.0) * 2.0
        qw, qx, qy, qz = 0.25 * s, (m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s
    elseif (m00 > m11 and m00 > m22) then
        local s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        qw, qx, qy, qz = (m21 - m12) / s, 0.25 * s, (m01 + m10) / s, (m02 + m20) / s
    elseif (m11 > m22) then
        local s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        qw, qx, qy, qz = (m02 - m20) / s, (m01 + m10) / s, 0.25 * s, (m12 + m21) / s
    else
        local s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
        qw, qx, qy, qz = (m10 - m01) / s, (m02 + m20) / s, (m12 + m21) / s, 0.25 * s
    end
    return Vec(qx, qy, qz, qw)
end

-- A camera looks down its own -Z.
local function CameraQuat(forward, up)
    local right = Normalize(Cross(forward, up))
    return QuatFromAxes(right, Cross(right, forward), Scale(forward, -1.0))
end

function Intro:Create()
    self.built = false
    self.done = false
    self.clock = 0.0
    self.frame = -1
    TheIntro = self
end

-- What the scene shows before the title: the special stage's sky (it waits, hidden, for the menus)
-- and the scene's default cube (a "Static Mesh" with SM_Cube, left at the origin from the start
-- and never seen behind the menus), which stands where the emblem is. Hidden from the title's
-- first frame -- before it is built, as it may wait a moment (Intro.waitFor) -- until it is done.
function Intro:HideScene()
    if (self.hidden ~= nil) then return end
    self.hidden = {}
    if (TheSky ~= nil) then TheSky:SetVisible(false) end
    for _, node in ipairs(self:GetWorld():FindNodesWithName("Static Mesh") or {}) do
        local mesh = node.GetStaticMesh ~= nil and node:GetStaticMesh() or nil
        if (mesh ~= nil and mesh:GetName() == "SM_Cube" and node:IsVisible()) then
            node:SetVisible(false)
            table.insert(self.hidden, node)
        end
    end
end

function Intro:Build()
    local world = self:GetWorld()
    self.nodes = {}
    local function Spawn(mesh)
        local node = world:SpawnNode("StaticMesh3D")
        node:SetStaticMesh(mesh)
        node:SetWorldPosition(Vec(0.0, 0.0, 0.0))
        if (node.EnableCollision ~= nil) then node:EnableCollision(false) end
        if (node.EnableOverlaps ~= nil) then node:EnableOverlaps(false) end
        table.insert(self.nodes, node)
        return node
    end

    self:HideScene()
    local dome = Spawn(LoadAsset("SM_DaySkyDome"))
    dome:SetScript("DaySky")
    -- and the sea under it, rippling (WaterBed.lua, native/gen_title_water.py)
    local water = Spawn(LoadAsset("SM_WaterBed"))
    water:SetScript("WaterBed")

    for _, name in ipairs({ "SM_IntroWings", "SM_IntroRing", "SM_IntroRibbon" }) do
        Spawn(LoadAsset(name))
    end
    self.sonicFrames = {}
    for i = 0, FRAMES - 1 do
        local k = SonicFrame(i)
        if (self.sonicFrames[k] == nil) then
            self.sonicFrames[k] = LoadAsset(string.format("SM_SonicIntro_%02d", k))
        end
    end
    self.sonic = Spawn(self.sonicFrames[0])

    -- Sonic is lit (the emblem carries its own light): a key from the upper left, in front, as
    -- in Blender
    self.sun = world:SpawnNode("DirectionalLight3D")
    self.sun:SetName("IntroSun")
    self.sun:SetDirection(Vec(0.45, -0.55, -0.70))
    self.sun:SetColor(Vec(1.0, 0.98, 0.95, 1.0))
    self.sun:SetIntensity(0.75)
    world:SetAmbientLightColor(Vec(0.55, 0.55, 0.60, 1.0))

    -- the camera, borrowed and given back as it was
    self.camera = world:GetActiveCamera()
    if (self.camera == nil) then
        self.camera = world:SpawnNode("Camera3D")
        world:SetActiveCamera(self.camera)
    end
    local cam = self.camera
    self.cameraWas = { pos = cam:GetWorldPosition(), rot = cam:GetWorldRotationQuat(), fov = cam:GetFieldOfView(),
                       far = cam.GetFar ~= nil and cam:GetFar() or nil }
    cam:SetFar(2000.0)

    self.music = LoadAsset("SW_TitleTheme")
    if (self.music ~= nil) then Audio.PlaySound2D(self.music, VOLUME, 1.0, 0.0, false, 100) end

    -- PRESS START in the UI's own lettering (F_SonicUI: the loading screen's STAGE 2)
    self.press = self:CreateChild("Text")
    self.press:SetAnchorMode(AnchorMode.TopLeft)
    local font = LoadAsset("F_SonicUI")
    if (font ~= nil) then self.press:SetFont(font) end
    self.press:SetColor(Vec(1.0, 1.0, 1.0, 1.0))
    self.press:SetText("PRESS START")
    self.press:SetVisible(false)

    self.built = true
end

function Intro:Layout()
    local res = Renderer.GetScreenResolution()
    local width, height = res.x, res.y
    if (self.SetDimensions ~= nil) then
        self:SetAnchorMode(AnchorMode.TopLeft)
        self:SetPosition(0.0, 0.0)
        self:SetDimensions(width, height)
    end
    -- PRESS START: as big as the loading screen's STAGE line (44 at 480 high), centred, under
    -- the emblem
    local size = 44.0 * height / 480.0
    self.press:SetTextSize(size)
    local wide = (self.press.GetTextWidth ~= nil) and self.press:GetTextWidth() or 0.0
    self.press:SetPosition((width - wide) * 0.5, height * 0.86 - size * 0.5)

    -- the field of view (up and down) that puts VIEW_WIDTH across the screen at the emblem
    local aspect = width / math.max(1.0, height)
    local half = math.atan((VIEW_WIDTH * 0.5) / aspect / DISTANCE)
    self.camera:SetFieldOfView(math.deg(half * 2.0))
end

function Intro:Place(t)
    local yaw = math.rad(SWAY_DEGREES) * math.sin(t * 2.0 * math.pi / SWAY_SECONDS)
    local lift = math.rad(LIFT_DEGREES)
    local eye = Add(AIM, { math.sin(yaw) * math.cos(lift) * DISTANCE, math.sin(lift) * DISTANCE,
                           math.cos(yaw) * math.cos(lift) * DISTANCE })
    self.camera:SetWorldPosition(ToVec(eye))
    self.camera:SetWorldRotationQuat(CameraQuat(Normalize(Sub(AIM, eye)), { 0.0, 1.0, 0.0 }))
end

function Intro:Finish()
    self.done = true
    if (self.music ~= nil) then Audio.StopSounds(self.music) end
    for _, node in ipairs(self.nodes) do node:Destruct() end
    self.nodes = {}
    if (self.sun ~= nil) then self.sun:Destruct(); self.sun = nil end
    local cam, was = self.camera, self.cameraWas
    cam:SetWorldPosition(was.pos)
    cam:SetWorldRotationQuat(was.rot)
    cam:SetFieldOfView(was.fov)
    if (was.far ~= nil) then cam:SetFar(was.far) end
    if (TheSky ~= nil) then TheSky:SetVisible(true) end
    for _, node in ipairs(self.hidden or {}) do node:SetVisible(true) end
    self:SetVisible(false)
    self.sonicFrames = nil
    if (self.onDone ~= nil) then self.onDone() end
end

function Intro:Tick(deltaTime)
    -- Something else to finish first (the GameCube's sky loads its stars before anything of the
    -- title is loaded: Screens.lua sets this): until then, nothing.
    if (not self.done) then self:HideScene() end
    if (not self.built and Intro.waitFor ~= nil and not Intro.waitFor()) then return end
    if (self.done) then return end
    if (not self.built) then self:Build() end
    self.clock = self.clock + deltaTime
    self:Layout()
    self:Place(self.clock)

    local frame = SonicFrame(math.min(math.floor(self.clock * FPS), FRAMES - 1))
    if (frame ~= self.frame and self.sonicFrames[frame] ~= nil) then
        self.frame = frame
        self.sonic:SetStaticMesh(self.sonicFrames[frame])
    end

    local ready = self.clock >= PRESS_AFTER
    self.press:SetVisible(ready and ((self.clock - PRESS_AFTER) % (BLINK * 2.0)) < BLINK)
    if (Input.IsKeyJustDown(Key.Enter)) then
        if (ready) then
            -- the menus' "on to the next" (Menu.lua's MenuSound; the menus are not loaded yet)
            -- (held in a global: the intro's own things are let go of right after, and the sound
            -- must not go with them while it plays; the menus use the same one)
            IntroSelectSound = IntroSelectSound or LoadAsset("SW_MenuSelect")
            if (IntroSelectSound ~= nil) then Audio.PlaySound2D(IntroSelectSound, 0.7, 1.0, 0.0, false, 50) end
            self:Finish()
        else
            self.clock = PRESS_AFTER        -- START before the pose: straight to it
        end
    end
end
