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
-- SONIC is his own model, animated a mesh a frame (native/export_sonic_to_octave.py): he runs
-- while he is on the pipe, curls into the BALL while he is in the air, as in the original, and
-- runs with his thumb up for a moment after a check is passed.

Script.Require("SpecialStageUI")

SpecialStage = {}

local TWO_PI = math.pi * 2.0

-- How it feels. Frames are the track's own unit: 8 to a straight piece.
local LAST_STAGE = 7            -- the gauntlet: StageData1..7, each with its own palette and emerald

local SPEED = 15.0              -- frames a second, forward. The original never lets you change it.
local STEER = 150.0             -- 256ths of a circle a second, at full tilt: round the pipe in 1.7 s
local STEER_GRIP = 9.0          -- how fast steering speed is reached and lost
local SLIDE = 55.0              -- hands off, he slides back down toward the floor, this hard
local JUMP = 16.0               -- off the surface, units a second
local GRAVITY = 42.0            -- back onto it
local REACH_FRAMES = 0.55       -- a hit: within this far along the track...
local REACH_ANGLE = 11.0        -- ...this far round it (256ths)...
local REACH_HEIGHT = 2.6        -- ...and no higher off the surface than this
local RING_SPIN_FRAMES = 12     -- meshes in half a turn of a ring (export_to_octave.py writes them)
local RING_SPIN_FPS = 20.0      -- steps a second: a full turn to the eye every 0.6 s
-- Sparkles where a ring was, and a fireball where a bomb was (native/gen_fx_assets.py). They are
-- flat squares turned to face the camera, and they RIDE WITH SONIC: he runs at 30 units a second,
-- so one left where the ring hung would be behind the camera before it had finished. Each is kept
-- in track coordinates relative to him (frames ahead, angle, height) and placed afresh every tick.
local SPARKLES = 5              -- to a ring
local SPARKLE_LIFE = 0.45
local SPARKLE_SIZE = 1.5
local BOOM_LIFE = 0.30
local BOOM_FRAMES = 3
local BOOM_SIZE = 3.6

-- Drop shadows: a dark blob on the pipe under Sonic and under every ring and bomb (SM_Shadow).
local SHADOW_LIFT = 0.06        -- off the pipe's surface, or it fights the pipe for the same depth
local SHADOW_RING = { along = 1.05, across = 1.05 }     -- round, like the others. (A thin ellipse is what a ring
                                                        -- really casts from above; round reads better.)
local SHADOW_BOMB = { along = 1.35, across = 1.35 }
local SHADOW_SONIC = 1.25
local SHADOW_SHRINK = 0.10      -- how fast Sonic's shadow draws in as he jumps away from the pipe
local SHADOW_RIM = 58.0         -- 256ths round from the floor's centre line: the pipe's surface ends at 57.7
                                -- (81 degrees; measured off the mesh). The track is a HALF pipe, and a
                                -- thing beyond its rim has nothing under it to cast a shadow on
local BOMB_COST = 10            -- rings a bomb takes, as in the original
local STUN = 0.6                -- seconds of stumbling after a bomb
local SEE_AHEAD, SEE_BEHIND = 110, 6    -- frames of rings and bombs kept alive round the player
local START_HOLD = 2.0          -- seconds standing at the start while START plays
local SONIC_FPS = 42.0          -- his animations were made at 24 frames a second, but at the speed
                                -- he covers the track that reads as a jog: played faster, by eye
local SONIC_FRAMES = 16         -- in a run cycle
local THUMBS_TIME = 2.8         -- seconds of thumbs-up running after a check is passed. The ring
                                -- check leaves 44 empty frames past the arch: 2.9 s at this speed.
local ORBIT_TIME = 0.75         -- of that, seconds the camera takes to swing round to his front, and back
local ORBIT_RADIUS = 6.5        -- how far from him it orbits. It has to stay INSIDE the pipe: at 11 the
                                -- camera was through the wall (which is about 8 out at that height) and
                                -- saw only pipe. With ORBIT_LIFT this keeps it 8.9 from the axis, of 10.
local ORBIT_LIFT = 1.5          -- and how far above his chest, toward the pipe's axis
local ORBIT_DEGREES = 135.0     -- how far round him the camera goes, on his LEFT (the way he turns his
                                -- head in RunThumbsUp). 135 is a three-quarter view: ahead of him and to
                                -- the side, so his FACE shows. Tried first: 180, dead ahead (not wanted),
                                -- and 90, beside him (a side profile, no face).
local BALL_RADIUS = 1.7

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
    -- The gauntlet is stages 1-7 in order. S2_STAGE starts somewhere else, for testing.
    self.stage = 1
    if (os ~= nil and os.getenv ~= nil) then
        local pick = tonumber(os.getenv("S2_STAGE") or "")
        if (pick ~= nil and pick >= 1 and pick <= LAST_STAGE) then self.stage = math.floor(pick) end
    end
    self.built = false
end

function SpecialStage:GatherProperties()
    return { { name = "stage", type = DatumType.Integer } }
end

-- Build is the things that outlive a stage: the meshes, the light, Sonic, the camera, the
-- UI and the music. LoadStage is the stage itself, and can be called again for the next one.
function SpecialStage:Build()
    local world = self:GetWorld()

    self.meshRing = LoadAsset("SM_Ring")
    -- the ring, turned a little further in each: half a turn in all, which is a whole one to look at
    self.meshRingSpin = {}
    for i = 0, RING_SPIN_FRAMES - 1 do
        self.meshRingSpin[i] = LoadAsset(string.format("SM_Ring_%02d", i)) or self.meshRing
    end
    self.ringStep = 0
    self.meshBomb = LoadAsset("SM_Bomb")

    -- The light, for the glossy things only (the pipe is unlit and carries its own shading).
    -- The light. The meshes carry their colours but not their shading: a sun from above and a
    -- little ahead, so the spheres catch a highlight. It is GENTLE on purpose -- ambient and sun
    -- add up to about 1, so the pipe keeps the colour it was given instead of burning out to
    -- white, which the first, brighter setting did.
    local sun = world:SpawnNode("DirectionalLight3D")
    sun:SetName("StageSun")
    sun:SetDirection(Vec(0.35, -1.0, -0.25))
    sun:SetColor(Vec(1.0, 0.98, 0.94, 1.0))
    sun:SetIntensity(0.45)
    world:SetAmbientLightColor(Vec(0.62, 0.62, 0.66, 1.0))

    self.meshBall = LoadAsset("SM_PlayerBall")
    self.meshSparkle, self.meshBoom = LoadAsset("SM_FxQuad"), LoadAsset("SM_FxQuadBoom")
    self.boomMaterial, self.boomTextures, self.boomFrame = LoadAsset("M_Explosion"), {}, -1
    for i = 0, BOOM_FRAMES - 1 do self.boomTextures[i] = LoadAsset("T_Explosion_" .. i) end
    self.meshShadow = LoadAsset("SM_Shadow")
    if (self.meshShadow ~= nil) then
        self.playerShadow = SpawnMesh(world, self.meshShadow)
    end
    self.sonicRun, self.sonicThumbs = {}, {}
    for i = 0, SONIC_FRAMES - 1 do
        self.sonicRun[i] = LoadAsset(string.format("SM_Sonic_Run_%02d", i))
        self.sonicThumbs[i] = LoadAsset(string.format("SM_Sonic_Thumbs_%02d", i))
    end
    self.sonicIdle = LoadAsset("SM_Sonic_Idle_00")
    self.player = SpawnMesh(world, self.sonicIdle or self.meshBall)
    self.playerMesh = nil

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

    self.built = true
    self:LoadStage(self.stage)
end

-- ------------------------------------------------------------------ a stage
-- Everything a stage owns, and nothing a stage does not: called once at startup and again
-- for each stage of the gauntlet. Whatever the last stage spawned is destroyed first.
function SpecialStage:LoadStage(n)
    local world = self:GetWorld()
    self:ClearStage()
    self.stage = n
    Script.Require("StageData" .. n)
    self.data = _G["StageData" .. n]
    if (self.data == nil) then          -- a build that ships fewer stages than seven
        self.stage = 1
        Script.Require("StageData1")
        self.data = _G["StageData1"]
    end

    self.meshRainbow = {}
    for i = 0, self.data.arch.rings - 1 do self.meshRainbow[i] = LoadAsset("SM_RingRainbow_" .. i) end

    -- the track: every piece, once. (The engine culls what is out of sight.)
    -- A piece is two meshes at the same place: the matte pipe, and the glossy spheres and rails.
    -- A mesh name ends in the PALETTE's number (SM_Piece_Straight_P4): the data gives the name
    -- without it, and each node remembers its own, so the palette can be changed under it.
    self.pieceNodes = {}
    self.pieceMeshes = {}
    self.palette = self.data.palette
    for _, piece in ipairs(self.data.pieces) do
        for _, name in ipairs({ piece.mesh, piece.gloss }) do
            local node = SpawnMesh(world, self:PieceMesh(name, self.palette))
            node:SetWorldPosition(Vec(piece.pos[1], piece.pos[2], piece.pos[3]))
            node:SetWorldRotationQuat(Vec(piece.quat[1], piece.quat[2], piece.quat[3], piece.quat[4]))
            self.pieceNodes[#self.pieceNodes + 1] = { node = node, name = name }
        end
    end

    -- every ring and bomb in one list, in the order they are met
    self.objects = {}
    for s, section in ipairs(self.data.sections) do
        for _, o in ipairs(section.objects) do
            self.objects[#self.objects + 1] = { frame = o[1], angle = o[2], bomb = (o[3] == 1), section = s }
        end
    end
    table.sort(self.objects, function(a, b) return a.frame < b.frame end)
    -- StaticMesh3D nodes not in use. It OUTLIVES a stage: a ring is a ring in all seven, so
    -- the next stage takes the same nodes back out of it rather than spawning its own.
    self.pool = self.pool or {}

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
    -- SM_Emerald_<stage>: each stage has its own chaos emerald (native/export_emeralds.py).
    -- Its reflection is fixed to the gem and drawn to be seen along its X, so it is turned to
    -- face back down the track, as a ring is.
    local emeraldFrame = last.check_frame + 10.0
    -- For looking at the emerald without playing to it: S2_TEST_EMERALD puts it just past the start.
    if (os ~= nil and os.getenv ~= nil and os.getenv("S2_TEST_EMERALD") ~= nil) then emeraldFrame = 16.0 end
    local where, emeraldFwd, emeraldUp = self:Place(emeraldFrame, 0.0, 4.0)
    self.emerald = SpawnMesh(world, LoadAsset("SM_Emerald_" .. self.data.stage) or LoadAsset("SM_Emerald"))
    self.emerald:SetWorldPosition(ToVec(where))
    self.emerald:SetWorldRotationQuat(FacingQuat(emeraldFwd, emeraldUp))

    -- the emerald, past the last check
    local last = self.data.sections[#self.data.sections]
    -- SM_Emerald_<stage>: each stage has its own chaos emerald (native/export_emeralds.py).
    -- Its reflection is fixed to the gem and drawn to be seen along its X, so it is turned to
    -- face back down the track, as a ring is.
    local emeraldFrame = last.check_frame + 10.0
    -- For looking at the emerald without playing to it: S2_TEST_EMERALD puts it just past the start.
    if (os ~= nil and os.getenv ~= nil and os.getenv("S2_TEST_EMERALD") ~= nil) then emeraldFrame = 16.0 end
    local where, emeraldFwd, emeraldUp = self:Place(emeraldFrame, 0.0, 4.0)
    self.emerald = SpawnMesh(world, LoadAsset("SM_Emerald_" .. self.data.stage) or LoadAsset("SM_Emerald"))
    self.emerald:SetWorldPosition(ToVec(where))
    self.emerald:SetWorldRotationQuat(FacingQuat(emeraldFwd, emeraldUp))

    -- the sky that goes with this stage's colours (stage_palettes.py's SKY). Sky.lua picks
    -- up a change of `sky` on its next tick.
    if (TheSky ~= nil and self.data.sky ~= nil) then TheSky.sky = self.data.sky end
    self:Restart()
end

-- What LoadStage spawned, taken down again. The pooled ring and bomb nodes are NOT destroyed:
-- their meshes are the same in every stage, so the next one reuses them.
function SpecialStage:ClearStage()
    for _, p in ipairs(self.pieceNodes or {}) do p.node:Destruct() end
    self.pieceNodes = {}
    for _, rings in ipairs(self.arches or {}) do
        for _, node in pairs(rings) do node:Destruct() end
    end
    self.arches = {}
    for _, o in ipairs(self.objects or {}) do
        if (o.node ~= nil) then self:Release(o) end
    end
    self.objects = {}
    if (self.emerald ~= nil) then self.emerald:Destruct() end
    self.emerald = nil
end

-- The gauntlet: stage 1 to 7, and the seventh emerald unlocks MARATHON in the menu. There is
-- nowhere else to go afterwards yet, so it leads back to the first stage.
function SpecialStage:NextStage()
    local next_ = self.stage + 1
    if (next_ > LAST_STAGE) then
        next_ = 1
        if (TheMenu ~= nil) then TheMenu:SetUnlocked("marathon", true) end
    end
    self:LoadStage(next_)
    self.announce = next_           -- shown once the UI says it is ready, in UpdateUI
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
    -- For testing the checks without playing to them: set S2_TEST_RINGS in the environment.
    if (os ~= nil and os.getenv ~= nil and os.getenv("S2_TEST_RINGS") ~= nil) then
        self.rings = tonumber(os.getenv("S2_TEST_RINGS")) or 0
    end
    self.section = 1
    self.stun = 0.0
    self.hold = START_HOLD
    self.over = -1.0                -- >= 0: the stage has ended, and this is the countdown to starting again
    self.spin = 0.0
    self.thumbs = 0.0               -- > 0: running with the thumb up
    self.runClock = 0.0
    self.emerald:SetVisible(true)
    self.uiReady = false
    self.failed = false
    self.fxPool = self.fxPool or { sparkle = {}, boom = {} }
    for _, fx in ipairs(self.fx or {}) do                   -- whatever was mid-flight goes back to the pool
        fx.node:SetVisible(false)
        table.insert(self.fxPool[fx.kind], fx.node)
    end
    self.fx = {}
end

-- ------------------------------------------------------------------ effects
function SpecialStage:FxNode(kind)
    local node = table.remove(self.fxPool[kind])
    if (node == nil) then
        local mesh = (kind == "boom") and self.meshBoom or self.meshSparkle
        if (mesh == nil) then return nil end
        node = SpawnMesh(self:GetWorld(), mesh)
    end
    node:SetVisible(true)
    return node
end

function SpecialStage:SpawnSparkles(o)
    for i = 1, SPARKLES do
        local node = self:FxNode("sparkle")
        if (node == nil) then return end
        local a = (i / SPARKLES) * TWO_PI + math.random() * 1.2
        local push = 0.6 + math.random() * 0.8
        self.fx[#self.fx + 1] = { kind = "sparkle", node = node, age = -0.05 * (i - 1), life = SPARKLE_LIFE,
                                  ahead = o.frame - self.frame, angle = o.angle, height = self.data.hover,
                                  dAngle = math.cos(a) * push * 14.0, dHeight = math.sin(a) * push * 2.4,
                                  size = SPARKLE_SIZE * (0.7 + math.random() * 0.6) }
    end
end

function SpecialStage:SpawnBoom(o)
    local node = self:FxNode("boom")
    if (node == nil) then return end
    self.fx[#self.fx + 1] = { kind = "boom", node = node, age = 0.0, life = BOOM_LIFE,
                              ahead = o.frame - self.frame, angle = o.angle, height = self.data.hover,
                              dAngle = 0.0, dHeight = 1.5, size = BOOM_SIZE }
end

-- Move, size and face every live effect; retire the finished ones. `facing` is the camera's
-- own rotation: a square given it faces the camera exactly.
function SpecialStage:UpdateFx(dt, facing)
    local keep = {}
    for _, fx in ipairs(self.fx) do
        fx.age = fx.age + dt
        if (fx.age >= fx.life) then
            fx.node:SetVisible(false)
            table.insert(self.fxPool[fx.kind], fx.node)
        else
            local t = math.max(0.0, fx.age) / fx.life
            local place = self:Place(self.frame + fx.ahead, fx.angle + fx.dAngle * t, fx.height + fx.dHeight * t)
            local size
            if (fx.kind == "boom") then
                size = fx.size * (0.55 + 0.45 * t)
                local frame = math.min(BOOM_FRAMES - 1, math.floor(t * BOOM_FRAMES))
                if (frame ~= self.boomFrame and self.boomMaterial ~= nil and self.boomTextures[frame] ~= nil) then
                    self.boomFrame = frame
                    self.boomMaterial:SetTexture(1, self.boomTextures[frame])
                end
            else
                -- a sparkle swells, twinkles and goes
                size = fx.size * math.sin(math.pi * t) * (0.75 + 0.25 * math.sin(fx.age * 50.0))
            end
            fx.node:SetVisible(fx.age >= 0.0)
            fx.node:SetWorldPosition(ToVec(place))
            fx.node:SetWorldRotationQuat(facing)
            fx.node:SetScale(Vec(size, size, size))
            keep[#keep + 1] = fx
        end
    end
    self.fx = keep
end

-- ------------------------------------------------------------------ rings and bombs
function SpecialStage:Release(o)
    o.node:SetVisible(false)
    if (o.shadow ~= nil) then o.shadow:SetVisible(false) end
    self.pool[#self.pool + 1] = { node = o.node, shadow = o.shadow }
    o.node, o.shadow = nil, nil
end

-- A shadow lies ON THE PIPE UNDER THE THING, "under" meaning toward the pipe's surface: a ring up
-- on the wall has its shadow on the wall beside it, as the original has. Seen from down the track
-- a disc lying on the wall is a long slanted blob, and at the side a thin sliver, which is exactly
-- what the original's shadow sprites are. It is dark wherever it is. (Two other ways were tried:
-- dropped straight down to the floor, and fading with the drop. Neither is what the game does.)
-- The track is a HALF pipe: past its rim there is no surface, and a shadow put there floats in
-- mid air, so a thing beyond the rim casts none. `height` only matters for Sonic: his draws in
-- as he jumps away from the pipe.
function SpecialStage:PlaceShadow(shadow, frame, angle, height, along, across)
    local round = angle
    if (round > 128.0) then round = round - 256.0 end
    if (round < -128.0) then round = round + 256.0 end
    if (math.abs(round) > SHADOW_RIM) then
        shadow:SetVisible(false)
        return false
    end
    local shrink = 1.0 / (1.0 + math.max(0.0, height) * SHADOW_SHRINK)
    local place, fwd, inward = self:Place(frame, angle, SHADOW_LIFT)
    shadow:SetWorldPosition(ToVec(place))
    shadow:SetWorldRotationQuat(FacingQuat(fwd, inward))
    shadow:SetScale(Vec(along * shrink, 1.0, across * shrink))
    shadow:SetVisible(true)
    return true
end

function SpecialStage:Acquire(o)
    local pair = table.remove(self.pool)
    local node = pair and pair.node or self:GetWorld():SpawnNode("StaticMesh3D")
    local shadow = pair and pair.shadow
    if (shadow == nil and self.meshShadow ~= nil) then
        shadow = self:GetWorld():SpawnNode("StaticMesh3D")
        shadow:SetStaticMesh(self.meshShadow)
    end
    node:SetStaticMesh(o.bomb and self.meshBomb or self.meshRingSpin[self.ringStep])
    local place, fwd, inward = self:Place(o.frame, o.angle, self.data.hover)
    node:SetWorldPosition(ToVec(place))
    if (o.bomb) then
        node:SetWorldRotationQuat(FacingQuat(fwd, inward))      -- a bomb stands square to the pipe under it
    else
        -- A ring's gold is a reflection PAINTED onto it, sky side up, so it keeps the track's
        -- own up wherever it is round the pipe. (A ring looks the same rolled; the paint does not.)
        local _, _, up = self:TrackAt(o.frame)
        node:SetWorldRotationQuat(FacingQuat(fwd, up))
    end
    node:SetVisible(true)
    o.node = node
    o.shadow = shadow
    if (shadow ~= nil) then
        local size = o.bomb and SHADOW_BOMB or SHADOW_RING
        self:PlaceShadow(shadow, o.frame, o.angle, 0.0, size.along, size.across)
    end
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
                local had = self.rings
                self.rings = math.max(0, self.rings - BOMB_COST)
                self.stun = STUN
                self:Sound("Explosion")
                if (had > 0) then self:Sound("LoseRings") end      -- only if there were any to lose
                self:SpawnBoom(o)
            else
                self.rings = self.rings + 1
                self:Sound("Ring")
                self:SpawnSparkles(o)
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
        -- COOL ! and the thumbs-up emblem are for a CHECK. The emerald has its own words.
        if (self.uiReady and section.leads_to ~= "EMERALD") then TheSpecialStageUI:ShowCool() end
        self.thumbs = THUMBS_TIME
        self:Sound((section.leads_to == "EMERALD") and "GetEmerald" or "Checkpoint")
        if (section.leads_to == "EMERALD") then
            self.emerald:SetVisible(false)
            self.over = 5.0
            if (self.uiReady) then TheSpecialStageUI:ShowBanner("EMERALD GET !", 4.5) end
        end
        self.section = self.section + 1
    else
        self.over = 3.5
        self.failed = true
        self:Sound("Fail")
        if (self.uiReady) then TheSpecialStageUI:ShowTooBad() end
    end
end

function SpecialStage:UpdateUI()
    if (not self.uiReady) then
        if (TheSpecialStageUI == nil or not TheSpecialStageUI.built) then return end
        TheSpecialStageUI.demo = false
        TheSpecialStageUI:ShowStart()
        self.uiReady = true
        if (self.announce ~= nil) then
            TheSpecialStageUI:ShowBanner("STAGE " .. self.announce, 2.5)
            self.announce = nil
        end
    end
    local section = self.data.sections[math.min(self.section, #self.data.sections)]
    TheSpecialStageUI:SetRings(self.rings)
    TheSpecialStageUI:SetTotal(section.quota)      -- what this round ASKS for: it does not count down
end

-- ------------------------------------------------------------------ sounds
-- The effects are SW_<name> assets (native/gen_music_assets.py makes them from external/audio).
-- Loaded the first time each is wanted; a missing one is silence, not an error.
--
-- THE MIX. The files are nowhere near one loudness: measured, the ring is TWICE as loud as the
-- music (rms 0.34 against 0.16) and it is the one sound that plays in bursts, several a second,
-- each on top of the last. So every effect has its own level here, set against the music at 1.0:
-- the ring well under it, the one-off fanfares about level with it.
local MIX = { Ring = 0.22, LoseRings = 0.55, Jump = 0.40, Checkpoint = 0.65, GetEmerald = 1.0,
              Explosion = 0.60, Fail = 0.70, ExitStage = 0.60 }

function SpecialStage:Sound(name)
    self.sounds = self.sounds or {}
    if (self.sounds[name] == nil) then self.sounds[name] = LoadAsset("SW_" .. name) or false end
    if (self.sounds[name]) then Audio.PlaySound2D(self.sounds[name], MIX[name] or 0.6) end
end

-- ------------------------------------------------------------------ palettes
function SpecialStage:PieceMesh(name, palette)
    local full = name .. palette
    if (self.pieceMeshes[full] == nil) then self.pieceMeshes[full] = LoadAsset(full) end
    return self.pieceMeshes[full]
end

-- Stage n's colours, 1-7: the pipe (every piece swaps to that palette's mesh) and the sky that
-- goes with it. Nothing else changes -- the track, the rings and the run carry on.
function SpecialStage:SetPalette(n)
    if (n == self.palette or self:PieceMesh(self.pieceNodes[1].name, n) == nil) then return end
    self.palette = n
    for _, p in ipairs(self.pieceNodes) do p.node:SetStaticMesh(self:PieceMesh(p.name, n)) end
    if (TheSky ~= nil) then TheSky.sky = self.data.palette_skies[n] end
end

local PALETTE_KEYS = { Key.N1, Key.N2, Key.N3, Key.N4, Key.N5, Key.N6, Key.N7 }

-- ------------------------------------------------------------------ every frame
function SpecialStage:Tick(deltaTime)
    if (not self.built) then self:Build() end
    local dt = math.min(deltaTime, 0.05)

    if (Input.IsKeyJustDown(Key.R)) then self:Restart() end
    for n, key in ipairs(PALETTE_KEYS) do
        if (Input.IsKeyJustDown(key)) then self:SetPalette(n) end
    end
    -- Eight skies and seven stages: Midnight (sky 1) belongs to no stage, so 8 puts it over
    -- whatever pipe is showing. Any of 1-7 brings that stage and its own sky back.
    if (Input.IsKeyJustDown(Key.N8) and TheSky ~= nil) then
        TheSky.sky = 1
        self.palette = 0                -- so pressing the current stage again restores its sky
    end
    if (self.over >= 0.0) then
        self.over = self.over - dt
        if (self.over < 0.0) then
            if (self.failed) then
                self:Sound("ExitStage")
                self:Restart()                  -- a failed stage is played again
            else
                self:NextStage()                -- the emerald was taken: on to the next
            end
        end
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
    if (self.height <= 0.0 and self.hold <= 0.0 and Input.IsKeyJustDown(Key.Space)) then
        self.rise = JUMP
        self:Sound("Jump")
    end
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

    -- Sonic: on the pipe he runs, feet on the surface; in the air he is the ball
    self.runClock = self.runClock + dt
    self.thumbs = math.max(0.0, self.thumbs - dt)
    local airborne = (self.height > 0.0)
    local mesh
    if (airborne) then
        mesh = self.meshBall
    elseif (self.hold > 0.0) then
        mesh = self.sonicIdle
    else
        local k = math.floor(self.runClock * SONIC_FPS) % SONIC_FRAMES
        mesh = (self.thumbs > 0.0) and self.sonicThumbs[k] or self.sonicRun[k]
    end
    if (mesh == nil) then mesh = self.meshBall end
    if (mesh ~= self.playerMesh) then
        self.playerMesh = mesh
        self.player:SetStaticMesh(mesh)
    end
    local lift = airborne and (BALL_RADIUS + self.height) or 0.0
    local place, fwd, inward = self:Place(self.frame, self.angle, lift)
    self.player:SetWorldPosition(ToVec(place))
    self.player:SetWorldRotationQuat(FacingQuat(fwd, inward))
    self.player:SetVisible(self.stun <= 0.0 or (math.floor(self.stun * 20.0) % 2 == 0))   -- flickers when hit
    -- his shadow stays on the pipe under him, and draws in as he jumps away from it
    if (self.playerShadow ~= nil) then
        self:PlaceShadow(self.playerShadow, self.frame, self.angle, self.height, SHADOW_SONIC, SHADOW_SONIC)
    end

    -- the camera rides the centre line behind him: it follows the TRACK, not the player,
    -- so steering moves Sonic round the screen as it does in the original
    local back = self:TrackAt(self.frame - 3.2)
    local herePos, fwdHere, upHere = self:TrackAt(self.frame)
    local ahead = self:TrackAt(self.frame + 6.0)
    local eye = Add(back, Scale(upHere, 7.6))
    local target = Add(ahead, Scale(upHere, 4.2))

    -- THE PASS. When a check is passed the camera ORBITS round to Sonic's side, so he is seen
    -- running past with his thumb up; holds there; and swings back behind him before the next
    -- section's shapes arrive. `swing` is how far round it is: 0 behind, 1 all the way.
    -- It is blended with the ordinary camera rather than cut to, so it leaves from exactly
    -- where the camera was and comes back to exactly where it will be.
    local swing = 0.0
    if (self.thumbs > 0.0) then
        local t = THUMBS_TIME - self.thumbs
        if (t < ORBIT_TIME) then
            swing = t / ORBIT_TIME
        elseif (self.thumbs < ORBIT_TIME) then
            swing = self.thumbs / ORBIT_TIME
        else
            swing = 1.0
        end
        swing = swing * swing * (3.0 - 2.0 * swing)             -- ease in and out
    end
    if (swing > 0.0) then
        -- In SONIC'S OWN frame, not the track's: his left, and his up (toward the pipe's axis).
        -- So wherever he is round the pipe the camera is beside him and inside it, and he is
        -- upright on the screen.
        local chest = Add(place, Scale(inward, 2.4))
        local left = Cross(inward, fwdHere)
        local phi = swing * math.rad(ORBIT_DEGREES)
        local orbit = Add(chest, Add(Scale(fwdHere, -math.cos(phi) * ORBIT_RADIUS),
                                     Add(Scale(left, math.sin(phi) * ORBIT_RADIUS), Scale(inward, ORBIT_LIFT))))
        eye = Add(Scale(eye, 1.0 - swing), Scale(orbit, swing))
        local aim = Add(chest, Scale(inward, 1.6))              -- a little over his chest: he sits low, the emblem above him
        target = Add(Scale(target, 1.0 - swing), Scale(aim, swing))
    end
    local look = Normalize(Add(target, Scale(eye, -1.0)))
    local camUp = Normalize(Add(Scale(upHere, 1.0 - swing), Scale(inward, swing)))
    self.camera:SetWorldPosition(ToVec(eye))
    local facing = CameraQuat(look, camUp)
    self.camera:SetWorldRotationQuat(facing)
    -- For looking at the effects without having to steer into anything: S2_TEST_FX sets one of
    -- each off in front of Sonic every second.
    if (os ~= nil and os.getenv ~= nil and os.getenv("S2_TEST_FX") ~= nil) then
        self.testFx = (self.testFx or 0.0) + dt
        if (self.testFx >= 1.0) then
            self.testFx = 0.0
            self:SpawnSparkles({ frame = self.frame + 5.0, angle = -14.0 })
            self:SpawnBoom({ frame = self.frame + 6.0, angle = 14.0 })
        end
    end
    self:UpdateFx(dt, facing)

    -- the rings spin: every ring in sight steps to the next mesh of the turn, all together
    self.clock = (self.clock or 0.0) + dt
    local ringStep = math.floor(self.clock * RING_SPIN_FPS) % RING_SPIN_FRAMES
    if (ringStep ~= self.ringStep) then
        self.ringStep = ringStep
        local mesh = self.meshRingSpin[ringStep]
        for _, o in ipairs(self.objects) do
            if (o.node ~= nil and not o.bomb) then o.node:SetStaticMesh(mesh) end
        end
    end

    -- the rainbow arches: each ring steps through the colours, one on from its neighbour
    local step = math.floor(self.clock * self.data.arch.steps_per_second)
    if (step ~= self.rainbowStep) then
        self.rainbowStep = step
        local n = self.data.arch.rings
        for _, rings in pairs(self.arches) do
            for i = 0, n - 1 do rings[i]:SetStaticMesh(self.meshRainbow[(i + step) % n]) end
        end
    end
end
