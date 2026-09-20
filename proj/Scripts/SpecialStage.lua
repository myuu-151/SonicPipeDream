-- SpecialStage.lua
-- A basic playable special stage.
--
--     A / D      steer left and right round the inside of the pipe
--     Space      jump
--     R          start again
--
-- Sonic runs forward by himself, as in the original: the player only ever moves ROUND the
-- pipe. And he can keep going -- up the wall, over the top, down the other side, round
-- again, without end -- because where he is is just an angle, and an angle wraps.
--
-- EVERYTHING IS IN TRACK COORDINATES. A ring is (frame, angle): how far along the track,
-- how far round the pipe. So is a bomb, and so is Sonic. That is the original's own way of
-- holding a stage, and it is why there is no physics in here: a hit is two numbers being
-- close. The track's shape comes in only at the end, to turn (frame, angle) into a place,
-- and for that the stage carries its centre line frame by frame (StageData.path) -- where
-- the floor is, which way is forward, which way is up.
--
-- The stage is native/gen_stage.py's, exported by native/export_to_octave.py into
-- StageData<N>.lua and the SM_* meshes. This script spawns all of it, so the scene needs
-- nothing but this node. Sky.lua starts it (startSpecialStage) so there is nothing to set
-- up in the editor either.
--
-- Placeholder: Sonic is a blue ball.

Script.Require("SpecialStageUI")

SpecialStage = {}

local TWO_PI = math.pi * 2.0

-- How it feels. Frames are the track's own unit: 8 to a straight piece.
local SPEED = 15.0              -- frames a second, forward. The original never lets you change it.
local STEER = 150.0             -- 256ths of a circle a second, at full tilt: round the pipe in 1.7 s
local STEER_GRIP = 9.0          -- how fast steering speed is reached and lost
local SLIDE = 55.0              -- hands off, he slides back down toward the floor, this hard
local JUMP = 16.0               -- off the surface, units a second
local GRAVITY = 42.0            -- back onto it
local REACH_FRAMES = 0.55       -- a hit: within this far along the track...
local REACH_ANGLE = 11.0        -- ...this far round it (256ths)...
local REACH_HEIGHT = 2.6        -- ...and no higher off the surface than this
local BOMB_COST = 10            -- rings a bomb takes, as in the original
local STUN = 0.6                -- seconds of stumbling after a bomb
local SEE_AHEAD, SEE_BEHIND = 110, 6    -- frames of rings and bombs kept alive round the player
local START_HOLD = 2.0          -- seconds standing at the start while START plays

-- ------------------------------------------------------------------ small vector maths
local function Add(a, b) return { a[1] + b[1], a[2] + b[2], a[3] + b[3] } end
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

-- A rotation from the three axes it turns X, Y and Z onto.
local function QuatFromAxes(x, y, z)
    local m00, m01, m02 = x[1], y[1], z[1]
    local m10, m11, m12 = x[2], y[2], z[2]
    local m20, m21, m22 = x[3], y[3], z[3]
    local trace = m00 + m11 + m22
    local qx, qy, qz, qw
    if (trace > 0.0) then
        local s = math.sqrt(trace + 1.0) * 2.0
        qw = 0.25 * s
        qx = (m21 - m12) / s
        qy = (m02 - m20) / s
        qz = (m10 - m01) / s
    elseif (m00 > m11 and m00 > m22) then
        local s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        qw = (m21 - m12) / s
        qx = 0.25 * s
        qy = (m01 + m10) / s
        qz = (m02 + m20) / s
    elseif (m11 > m22) then
        local s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        qw = (m02 - m20) / s
        qx = (m01 + m10) / s
        qy = 0.25 * s
        qz = (m12 + m21) / s
    else
        local s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
        qw = (m10 - m01) / s
        qx = (m02 + m20) / s
        qy = (m12 + m21) / s
        qz = 0.25 * s
    end
    return Vec(qx, qy, qz, qw)
end

-- Something whose own X is forward and whose own Y is up (every exported mesh).
local function FacingQuat(forward, up)
    return QuatFromAxes(forward, up, Cross(forward, up))
end

-- A camera looks down its own -Z.
local function CameraQuat(forward, up)
    local right = Normalize(Cross(forward, up))
    local trueUp = Cross(right, forward)
    return QuatFromAxes(right, trueUp, Scale(forward, -1.0))
end

-- ------------------------------------------------------------------ the track
-- The centre line at a (fractional) frame: where the floor is, forward, up.
function SpecialStage:TrackAt(frame)
    local path = self.data.path
    local f = math.max(0.0, math.min(frame, #path - 1.001))
    local i = math.floor(f)
    local t = f - i
    local a, b = path[i + 1], path[i + 2]
    local pos = { a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * t }
    local fwd = Normalize({ a[4] + (b[4] - a[4]) * t, a[5] + (b[5] - a[5]) * t, a[6] + (b[6] - a[6]) * t })
    local up = Normalize({ a[7] + (b[7] - a[7]) * t, a[8] + (b[8] - a[8]) * t, a[9] + (b[9] - a[9]) * t })
    return pos, fwd, up
end

-- (frame, angle, height off the pipe's surface) -> a place, and which way is "up" there:
-- toward the pipe's axis, so things stand square to the bit of pipe under them.
function SpecialStage:Place(frame, angle, height)
    local pos, fwd, up = self:TrackAt(frame)
    local left = Cross(up, fwd)
    local t = self.data.angle_00_side * angle * TWO_PI / 256.0
    local radius = self.data.pipe_radius
    local r = radius - height
    local place = Add(Add(pos, Scale(left, r * math.sin(t))), Scale(up, radius - r * math.cos(t)))
    local inward = Normalize(Add(Scale(left, -math.sin(t)), Scale(up, math.cos(t))))
    return place, fwd, inward
end

-- ------------------------------------------------------------------ building the stage
local function SpawnMesh(world, mesh)
    local node = world:SpawnNode("StaticMesh3D")
    node:SetStaticMesh(mesh)
    return node
end

function SpecialStage:Create()
    self.stage = 1
    self.built = false
end

function SpecialStage:GatherProperties()
    return { { name = "stage", type = DatumType.Integer } }
end

function SpecialStage:Build()
    local world = self:GetWorld()
    Script.Require("StageData" .. self.stage)
    self.data = _G["StageData" .. self.stage]

    self.meshRing = LoadAsset("SM_Ring")
    self.meshBomb = LoadAsset("SM_Bomb")
    self.meshRainbow = {}
    for i = 0, self.data.arch.rings - 1 do self.meshRainbow[i] = LoadAsset("SM_RingRainbow_" .. i) end

    -- the track: every piece, once. (The engine culls what is out of sight.)
    local loaded = {}
    for _, piece in ipairs(self.data.pieces) do
        if (loaded[piece.mesh] == nil) then loaded[piece.mesh] = LoadAsset(piece.mesh) end
        local node = SpawnMesh(world, loaded[piece.mesh])
        node:SetWorldPosition(Vec(piece.pos[1], piece.pos[2], piece.pos[3]))
        node:SetWorldRotationQuat(Vec(piece.quat[1], piece.quat[2], piece.quat[3], piece.quat[4]))
    end

    -- every ring and bomb in one list, in the order they are met
    self.objects = {}
    for s, section in ipairs(self.data.sections) do
        for _, o in ipairs(section.objects) do
            self.objects[#self.objects + 1] = { frame = o[1], angle = o[2], bomb = (o[3] == 1), section = s }
        end
    end
    table.sort(self.objects, function(a, b) return a.frame < b.frame end)
    self.pool = {}                  -- StaticMesh3D nodes not in use

    -- the rainbow arch over each check
    self.arches = {}
    local arch = self.data.arch
    for s, section in ipairs(self.data.sections) do
        local pos, fwd, up = self:TrackAt(section.check_frame)
        local left = Cross(up, fwd)
        local rings = {}
        for i = 0, arch.rings - 1 do
            local t = math.rad(arch.from_deg + (180.0 - 2.0 * arch.from_deg) * i / (arch.rings - 1))
            local place = Add(pos, Add(Scale(left, arch.reach * math.cos(t)),
                                       Add(Scale(up, self.data.pipe_radius + arch.reach * math.sin(t)),
                                           Scale(fwd, -arch.toward_player))))
            local node = SpawnMesh(world, self.meshRainbow[i])
            node:SetWorldPosition(ToVec(place))
            node:SetWorldRotationQuat(FacingQuat(fwd, up))
            node:SetWorldScale(Vec(arch.ring_scale, arch.ring_scale, arch.ring_scale))
            rings[i] = node
        end
        self.arches[s] = rings
    end
    self.rainbowStep = -1

    -- the emerald, past the last check
    local last = self.data.sections[#self.data.sections]
    local where = self:Place(last.check_frame + 10.0, 0.0, 4.0)
    self.emerald = SpawnMesh(world, LoadAsset("SM_Emerald"))
    self.emerald:SetWorldPosition(ToVec(where))

    self.player = SpawnMesh(world, LoadAsset("SM_PlayerBall"))

    self.camera = world:GetActiveCamera()
    if (self.camera == nil) then
        self.camera = world:SpawnNode("Camera3D")
        world:SetActiveCamera(self.camera)
    end
    self.camera:SetFar(6000.0)

    local ui = world:SpawnNode("Canvas")
    ui:SetScript("SpecialStageUI")

    -- the music: its script only needs to be on some node, and nothing in the scene has it
    local music = world:SpawnNode("Node3D")
    music:SetName("SpecialStageMusic")
    music:SetScript("SpecialStageMusic")

    -- the sky that goes with this stage's colours (stage_palettes.py's SKY). Sky.lua picks
    -- up a change of `sky` on its next tick.
    if (TheSky ~= nil and self.data.sky ~= nil) then TheSky.sky = self.data.sky end
    self.built = true
    self:Restart()
end

function SpecialStage:Restart()
    for _, o in ipairs(self.objects) do
        o.taken = false
        if (o.node ~= nil) then self:Release(o) end
    end
    self.frame = 0.0
    self.angle = 0.0                -- 0 is the floor's centre line; it wraps at +-128
    self.steer = 0.0
    self.height = 0.0               -- off the pipe's surface
    self.rise = 0.0
    self.rings = 0
    self.section = 1
    self.stun = 0.0
    self.hold = START_HOLD
    self.over = -1.0                -- >= 0: the stage has ended, and this is the countdown to starting again
    self.spin = 0.0
    self.emerald:SetVisible(true)
    self.uiReady = false
end

-- ------------------------------------------------------------------ rings and bombs
function SpecialStage:Release(o)
    o.node:SetVisible(false)
    self.pool[#self.pool + 1] = o.node
    o.node = nil
end

function SpecialStage:Acquire(o)
    local node = table.remove(self.pool)
    if (node == nil) then node = self:GetWorld():SpawnNode("StaticMesh3D") end
    node:SetStaticMesh(o.bomb and self.meshBomb or self.meshRing)
    local place, fwd, inward = self:Place(o.frame, o.angle, self.data.hover)
    node:SetWorldPosition(ToVec(place))
    node:SetWorldRotationQuat(FacingQuat(fwd, inward))
    node:SetVisible(true)
    o.node = node
end

-- Keep alive only what is near the player.
function SpecialStage:UpdateObjects()
    local lo, hi = self.frame - SEE_BEHIND, self.frame + SEE_AHEAD
    for _, o in ipairs(self.objects) do
        local near = (o.frame >= lo and o.frame <= hi and not o.taken)
        if (near and o.node == nil) then
            self:Acquire(o)
        elseif (not near and o.node ~= nil) then
            self:Release(o)
        end
    end
end

local function AngleBetween(a, b)
    local d = math.abs(a - b) % 256.0
    if (d > 128.0) then d = 256.0 - d end
    return d
end

function SpecialStage:Collide(fromFrame)
    if (self.height > REACH_HEIGHT) then return end
    for _, o in ipairs(self.objects) do
        if (o.frame > self.frame + REACH_FRAMES) then break end
        if (not o.taken and o.frame >= fromFrame - REACH_FRAMES and AngleBetween(o.angle, self.angle) <= REACH_ANGLE) then
            o.taken = true
            if (o.node ~= nil) then self:Release(o) end
            if (o.bomb) then
                self.rings = math.max(0, self.rings - BOMB_COST)
                self.stun = STUN
            else
                self.rings = self.rings + 1
            end
        end
    end
end

-- ------------------------------------------------------------------ the ring check
function SpecialStage:PassChecks(fromFrame)
    local section = self.data.sections[self.section]
    if (section == nil or self.frame < section.check_frame or fromFrame >= section.check_frame) then return end
    -- the instant he passes under the rainbow arch
    if (self.rings >= section.quota) then
        if (self.uiReady) then TheSpecialStageUI:ShowCool() end
        if (section.leads_to == "EMERALD") then
            self.emerald:SetVisible(false)
            self.over = 5.0
            if (self.uiReady) then TheSpecialStageUI:ShowBanner("EMERALD GET !", 4.5) end
        end
        self.section = self.section + 1
    else
        self.over = 3.5
        if (self.uiReady) then TheSpecialStageUI:ShowBanner("NOT ENOUGH RINGS", 3.2) end
    end
end

function SpecialStage:UpdateUI()
    if (not self.uiReady) then
        if (TheSpecialStageUI == nil or not TheSpecialStageUI.built) then return end
        TheSpecialStageUI.demo = false
        TheSpecialStageUI:ShowStart()
        self.uiReady = true
    end
    local section = self.data.sections[math.min(self.section, #self.data.sections)]
    TheSpecialStageUI:SetRings(self.rings)
    TheSpecialStageUI:SetTotal(math.max(0, section.quota - self.rings))
end

-- ------------------------------------------------------------------ every frame
function SpecialStage:Tick(deltaTime)
    if (not self.built) then self:Build() end
    local dt = math.min(deltaTime, 0.05)

    if (Input.IsKeyJustDown(Key.R)) then self:Restart() end
    if (self.over >= 0.0) then
        self.over = self.over - dt
        if (self.over < 0.0) then self:Restart() end
    end

    -- steering: round the pipe, and only round it
    local want = 0.0
    if (self.hold <= 0.0 and self.stun <= 0.0) then
        if (Input.IsKeyDown(Key.A)) then want = want + 1.0 end
        if (Input.IsKeyDown(Key.D)) then want = want - 1.0 end
    end
    want = want * self.data.angle_00_side                 -- A is always the player's left
    local target = want * STEER
    if (want == 0.0 and self.height <= 0.0) then
        -- hands off: gravity slides him back down toward the floor
        target = -math.sin(self.angle * TWO_PI / 256.0) * SLIDE
    end
    self.steer = self.steer + (target - self.steer) * math.min(1.0, STEER_GRIP * dt)
    self.angle = self.angle + self.steer * dt
    if (self.angle > 128.0) then self.angle = self.angle - 256.0 end       -- over the top and on
    if (self.angle < -128.0) then self.angle = self.angle + 256.0 end

    -- jumping: off the pipe's surface, toward its axis, and back
    if (self.height <= 0.0 and self.hold <= 0.0 and Input.IsKeyJustDown(Key.Space)) then self.rise = JUMP end
    if (self.height > 0.0 or self.rise > 0.0) then
        self.height = self.height + self.rise * dt
        self.rise = self.rise - GRAVITY * dt
        if (self.height <= 0.0) then self.height, self.rise = 0.0, 0.0 end
    end

    -- forward, by himself
    local before = self.frame
    if (self.hold > 0.0) then
        self.hold = self.hold - dt
    elseif (self.over < 0.0 or self.section > #self.data.sections) then
        local speed = SPEED
        if (self.stun > 0.0) then speed = SPEED * 0.45 end
        self.frame = math.min(self.frame + speed * dt, self.data.frames - 2.0)
    end
    self.stun = math.max(0.0, self.stun - dt)

    self:UpdateObjects()
    self:Collide(before)
    self:PassChecks(before)
    self:UpdateUI()

    -- Sonic
    local place, fwd, inward = self:Place(self.frame, self.angle, 1.7 + self.height)
    self.spin = self.spin + SPEED * dt * 2.2
    self.player:SetWorldPosition(ToVec(place))
    self.player:SetWorldRotationQuat(FacingQuat(fwd, inward))
    self.player:SetVisible(self.stun <= 0.0 or (math.floor(self.stun * 20.0) % 2 == 0))   -- flickers when hit

    -- the camera rides the centre line behind him: it follows the TRACK, not the player,
    -- so steering moves Sonic round the screen as it does in the original
    local back = self:TrackAt(self.frame - 3.2)
    local _, _, upHere = self:TrackAt(self.frame)
    local ahead = self:TrackAt(self.frame + 6.0)
    local eye = Add(back, Scale(upHere, 7.6))
    local look = Normalize(Add(Add(ahead, Scale(upHere, 4.2)), Scale(eye, -1.0)))
    self.camera:SetWorldPosition(ToVec(eye))
    self.camera:SetWorldRotationQuat(CameraQuat(look, upHere))

    -- the rainbow arches: each ring steps through the colours, one on from its neighbour
    self.clock = (self.clock or 0.0) + dt
    local step = math.floor(self.clock * self.data.arch.steps_per_second)
    if (step ~= self.rainbowStep) then
        self.rainbowStep = step
        local n = self.data.arch.rings
        for _, rings in pairs(self.arches) do
            for i = 0, n - 1 do rings[i]:SetStaticMesh(self.meshRainbow[(i + step) % n]) end
        end
    end
end
