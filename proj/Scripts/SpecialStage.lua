-- SpecialStage.lua
-- A basic playable special stage.
--
--     A / D      steer left and right round the inside of the pipe
--     Space      jump; again in the air to drop straight back down
--     Escape     pause: CONTINUE, or EXIT to the stage select
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
-- Momentum: keep the direction held and he winds up past STEER, faster and faster round the
-- pipe, to STEER_MAX; let go and it bleeds off at STEER_COAST rather than stopping dead
local STEER_BUILD = 160.0       -- 256ths a second a second, once he is at STEER and still holding: the
                                -- first loop round is the speeding up, the second is at STEER_MAX
local STEER_MAX = 320.0         -- round the pipe in 0.8 s
local STEER_COAST = 2.5         -- how fast the wound-up speed is lost with the direction let go
local SLIDE = 55.0              -- hands off, he slides back down toward the floor, this hard
-- The jump is S2's: he leaves the surface as a ball and FLIES, straight, under gravity,
-- across the pipe's section. Off the floor it is a stiff high hop; off the wall it throws
-- him across to land on the other side, spinning as he goes. His way ROUND the pipe is kept
-- in it: his run round the pipe leaves with him as sideways speed, so a jump while
-- running round flies off the way he was going (lower, the faster he goes, as the pipe curves
-- up to meet him), and he lands with the speed he came in with. A held direction only nudges
-- the flight sideways. The drop dash (jump again in the air) is straight down the screen.
local JUMP = 50.0               -- off the surface, units a second, once the push has built: 9.6 units up a
                                -- 10 unit pipe, the ball's middle well past its axis at the top of the hop
local JUMP_START = 0.4          -- of that at the instant he leaves; the rest builds over JUMP_RAMP seconds,
local JUMP_RAMP = 0.12          -- a weighted bounce off the surface rather than a flick
local GRAVITY = 110.0           -- units a second a second, toward the floor, off the floor: up and down
                                -- in 0.87 s. Off the wall the same, and the same push:
local WALL_GRAVITY = 110.0      -- this, at the wall gone vertical, and in between in between; and the push
local WALL_PUSH = 1.0           -- off it this much of JUMP. (80 and 0.9 made a side-to-side hop slower than
                                -- the rest; the same as a floor jump now, and it still crosses the pipe)
local AIR_STEER = 40.0          -- units a second a second: a direction held in the air nudges the flight
local AIR_STEER_MAX = 30.0      -- ...sideways, up to this sideways speed of its own making
-- Near the centre line none of that: a jump from level ground goes straight up and comes
-- straight down. (The surface's normal there leans toward the axis, and with the swing on top
-- a hop from a hair to one side crossed the axis and came down swinging on the other.)
local LEVEL = 12.0              -- within this (256ths) of the centre line it is a plain hop...
local LEVEL_BLEND = 24.0        -- ...and by here it is the full thing
-- The slide (hands let go, gravity taking him down the wall) carries into a jump from up the
-- wall: it is what arcs him down across to the other side instead of level into its lip. But
-- carried from near the centre it twirls him, so it is kept out of a hop from there:
local CARRY_FROM = 24.0         -- none of the slide carried within this (256ths) of the centre line...
local CARRY_FULL = 44.0         -- ...all of it from here up the wall
local FALL_ANGLE = 64.0         -- past here (256ths; 64 is the wall gone vertical) the surface overhangs:
local CLING = 0.45              -- with the steering let go he keeps his feet this long, then falls off it
local FALL_TURN = 0.25          -- seconds to swing from feet-on-the-wall to upright as the fall starts
local DIVE = 45.0               -- jump again in the air: straight back down onto the pipe, units a second,
local DIVE_KEEP = 0.7           -- and this much of the speed he was already flying at on top: a drop dash
                                -- out of a running jump is a dash, not a brake
-- A drop dash does not land: it BOUNCES back up off the pipe, this much of a jump, his run round
-- the pipe kept -- so he bounces along it. Jump again in the bounce and it is another drop dash,
-- and another bounce; leave it and he comes down from it and lands. (0: no bounce.)
local BOUNCE = 0.8
local BALL_SPIN = 12.0          -- radians a second: two turns a second in the air
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
local START_HOLD = 4.5          -- seconds running up the lead-in at the start while START plays (2.5 s)
local SONIC_FPS = 42.0          -- his animations were made at 24 frames a second, but at the speed
                                -- he covers the track that reads as a jog: played faster, by eye
local SONIC_FRAMES = 16         -- in a run cycle
local THUMBS_TIME = 2.8         -- seconds of thumbs-up running after a check is passed. The ring
                                -- check leaves 44 empty frames past the arch: 2.9 s at this speed.
-- THE INTRO. While START is on the screen and he runs on the spot, the camera goes once right
-- round him: away behind, down his side, low across his front looking up at him, and round
-- back up into its place as he sets off.
local INTRO_TIME = START_HOLD   -- seconds: the whole of the hold
local LEAD_PIECES = 10          -- straights laid BEHIND the start for him to run up during it: he sets
                                -- off from START_HOLD seconds back up the track and reaches its
                                -- proper start as the hold ends (10 x 8 frames > 4.5 s x 15 a second)
local INTRO_RADIUS = 6.5        -- how far from him. It has to stay INSIDE the pipe all the way round:
                                -- beside him the wall is only 2.4 up at this distance out
local INTRO_LOW = -1.0          -- how far below his chest at the front of the sweep (a low angle, looking up)
local INTRO_HIGH = 3.5          -- and how far above it round the back and sides
local INTRO_IN = 1.3            -- seconds to ease out of the ordinary camera into the circuit, softly:
local INTRO_OUT = 0.9           -- no speed at either end of the move (smootherstep, below); and back
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
local function Dot(a, b) return a[1] * b[1] + a[2] * b[2] + a[3] * b[3] end
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
    if (frame < 0.0) then
        -- the lead-in: straight back from the start along its own heading, a frame a step
        local a, b = path[1], path[2]
        local pos = { a[1] + (b[1] - a[1]) * frame, a[2] + (b[2] - a[2]) * frame, a[3] + (b[3] - a[3]) * frame }
        return pos, Normalize({ a[4], a[5], a[6] }), Normalize({ a[7], a[8], a[9] })
    end
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
-- Off the surface where he stands, into the air: he becomes a point in the pipe's section,
-- (cx, cy) from its axis, cy up, the floor at cy = -radius, pushed away from the surface at
-- `push` (a jump; the rest of the push builds in Tick) or simply let go of (a fall, push 0).
function SpecialStage:LeaveSurface(push, held)
    local radius = self.data.pipe_radius
    local t = self.data.angle_00_side * self.angle * TWO_PI / 256.0
    local r = radius - 0.05                 -- a hair inside, so he is not "landed" again next tick
    self.cx, self.cy = r * math.sin(t), -r * math.cos(t)
    -- the push's direction: away from the surface, but straight up from level ground
    local k = math.max(0.0, math.min(1.0, (math.abs(self.angle) - LEVEL) / (LEVEL_BLEND - LEVEL)))
    local nx, ny = -math.sin(t) * k, (1.0 - k) + math.cos(t) * k
    local n = math.sqrt(nx * nx + ny * ny)
    self.nx, self.ny = nx / n, ny / n
    self.level = 1.0 - k                                      -- how much of a plain hop this is
    -- a HELD direction carries into the air whole; the slide of hands let go only from up
    -- the wall (CARRY_FROM .. CARRY_FULL)
    if (not held) then
        self.steer = self.steer * math.max(0.0, math.min(1.0, (math.abs(self.angle) - CARRY_FROM) / (CARRY_FULL - CARRY_FROM)))
    end
    local wall = math.min(1.0, math.abs(math.sin(t)))         -- 0 on the floor, 1 at the vertical wall
    push = push * (1.0 + (WALL_PUSH - 1.0) * wall)
    self.vx, self.vy = self.nx * push * JUMP_START, self.ny * push * JUMP_START
    self.push, self.ramp = push * (1.0 - JUMP_START), 0.0     -- what is still to come, and how far along
    self.gravity = GRAVITY + (WALL_GRAVITY - GRAVITY) * wall
    -- HIS RUN ROUND THE PIPE GOES WITH HIM, as SIDEWAYS speed: the part of it across the
    -- screen. The flight is then an ordinary throw -- a straight arc under gravity. (It used to
    -- be the whole section turning under him in the air, at his steering speed: a throw across
    -- the pipe curled into a spiral, and the speed he landed with had nothing to do with the way
    -- he had flown.) Only the sideways part: all of it off the floor, little of it up a wall.
    -- Given the whole of it, a jump from a wall he was running up launched him up past the rim
    -- into the sky.
    local omega = self.data.angle_00_side * self.steer * TWO_PI / 256.0      -- radians a second, in t
    self.vx = self.vx + r * omega * math.cos(t)
    self.takeoffSteer = math.abs(self.steer)
    self.height = radius - r
    self.falling = (push <= 0.0)
    self.diving, self.cling, self.fallTime = false, 0.0, 0.0
end

function SpecialStage:WrapAngle(angle)
    if (angle > 128.0) then return angle - 256.0 end        -- over the top and on
    if (angle < -128.0) then return angle + 256.0 end
    return angle
end

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
    TheSpecialStage = self          -- so the stage select can say which stage to build
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
    self.uiNode = ui                -- kept so the HUD can be hidden when the stage is left

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
    -- and the lead-in behind the start: the first piece (a straight: every level opens on
    -- them) laid again and again back along its own heading
    local first = self.data.pieces[1]
    local a, b = self.data.path[1], self.data.path[9]                -- one straight is eight frames
    for k = 1, LEAD_PIECES do
        for _, name in ipairs({ first.mesh, first.gloss }) do
            local node = SpawnMesh(world, self:PieceMesh(name, self.palette))
            node:SetWorldPosition(Vec(first.pos[1] - (b[1] - a[1]) * k, first.pos[2] - (b[2] - a[2]) * k,
                                      first.pos[3] - (b[3] - a[3]) * k))
            node:SetWorldRotationQuat(Vec(first.quat[1], first.quat[2], first.quat[3], first.quat[4]))
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

-- ------------------------------------------------------------------ coming and going
-- The emerald ends the stage: it is won, and the stage select comes back with that emerald
-- in colour. One stage does not run into the next -- you choose the next one yourself.
function SpecialStage:Finish()
    local won = self.stage
    self:Leave()
    if (self.onFinished ~= nil) then self.onFinished(won) end
end

-- Put the stage away: everything it spawned goes, and what it keeps is hidden. The world
-- is left as it was before the stage started -- the sky, and a menu over it.
function SpecialStage:Leave()
    self.active = false
    self.paused = false
    if (self.uiReady) then TheSpecialStageUI:ShowPause(false, 1) end
    self:ClearStage()
    for _, node in ipairs({ self.player, self.playerShadow, self.uiNode }) do
        if (node ~= nil) then node:SetVisible(false) end
    end
    for _, fx in ipairs(self.fx or {}) do fx.node:SetVisible(false) end
    if (TheSpecialStageMusic ~= nil and TheSpecialStageMusic.Stop ~= nil) then
        TheSpecialStageMusic:Stop()
    end
end

-- And back in, at whichever stage was chosen.
function SpecialStage:Enter(n)
    self.active = true
    for _, node in ipairs({ self.player, self.playerShadow, self.uiNode }) do
        if (node ~= nil) then node:SetVisible(true) end
    end
    self:LoadStage(n or self.stage)
    if (TheSpecialStageMusic ~= nil and TheSpecialStageMusic.Restart ~= nil) then
        TheSpecialStageMusic:Restart()
    end
end

function SpecialStage:SetPaused(paused)
    self.paused = paused
    self.pauseIndex = 1
    if (self.uiReady) then TheSpecialStageUI:ShowPause(paused, 1) end
end

function SpecialStage:Restart()
    for _, o in ipairs(self.objects) do
        o.taken = false
        if (o.node ~= nil) then self:Release(o) end
    end
    self.frame = -SPEED * START_HOLD    -- back up the lead-in: at the start proper as START scatters
    self.angle = 0.0                -- 0 is the floor's centre line; it wraps at +-128
    self.steer = 0.0
    self.height = 0.0               -- off the pipe's surface
    self.cx, self.cy = 0.0, 0.0     -- in the air: where he is in the pipe's section, and
    self.vx, self.vy = 0.0, 0.0     -- how he is moving through it
    self.nx, self.ny = 0.0, 1.0     -- which way the jump pushed him, and how much of the push
    self.push, self.ramp = 0.0, 0.0 -- is still building (LeaveSurface)
    self.gravity = GRAVITY          -- the pull down through this flight, softer for a throw off the wall
    self.level = 1.0                -- 1 for a plain hop off level ground, 0 for a throw off the wall
    self.spin = 0.0
    self.cling = 0.0                -- how long he has hung on up the overhang with the steering let go
    self.falling = false            -- in the air because he let go up there, on his feet, not as the ball
    self.fallTime = 0.0             -- how long he has been in the air
    self.diving = false             -- jumped again in the air: dropping straight back down
    self.rings = 0
    -- For testing the checks without playing to them: set S2_TEST_RINGS in the environment.
    self.autoplay = (os ~= nil and os.getenv ~= nil and os.getenv("S2_AUTOPLAY") ~= nil)
    if (os ~= nil and os.getenv ~= nil and os.getenv("S2_AUTOJUMP") ~= nil) then
        self.testJump = tonumber(os.getenv("S2_AUTOJUMP"))
        self.testLog = true
        -- and S2_AUTODIVE=<seconds>: drop dash that long into the flight; S2_AUTOBOUNCES=<n>:
        -- and again that long into each of the next n bounces
        self.testDive = tonumber(os.getenv("S2_AUTODIVE") or "")
        self.testDiveAt = self.testDive
        self.testBounces = tonumber(os.getenv("S2_AUTOBOUNCES") or "") or 0
    end
    if (os ~= nil and os.getenv ~= nil and os.getenv("S2_TEST_RINGS") ~= nil) then
        self.rings = tonumber(os.getenv("S2_TEST_RINGS")) or 0
    end
    self.section = 1
    self.stun = 0.0
    self.hold = START_HOLD
    self.intro = INTRO_TIME         -- > 0: the camera is going round him while START is up
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
            -- Won, and remembered: the stage select shows it in colour from now on, this
            -- session and the next.
            if (TheStageSelect ~= nil) then TheStageSelect:SetWon(self.stage, true) end
        end
        self.section = self.section + 1
    else
        self.over = 3.5
        self.failed = true
        self:Sound("Fail")
        if (self.uiReady) then TheSpecialStageUI:ShowBanner("NOT ENOUGH RINGS", 3.2) end
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

-- ------------------------------------------------------------------ the autopilot
-- For the stage select's previews (native/make_stage_previews.py): with S2_AUTOPLAY set the
-- stage plays itself, steering for the nearest ring ahead and round any bomb in the way.
local PILOT_LOOK = 14.0         -- frames ahead it looks for a ring
local PILOT_DODGE = 18.0        -- 256ths: a bomb this close to his line, this near, is steered round
local PILOT_NEAR = 9.0          -- frames

function SpecialStage:Pilot()
    local target, bomb = nil, nil
    for _, o in ipairs(self.objects) do
        if (o.frame > self.frame + PILOT_LOOK) then break end
        if (not o.taken and o.frame > self.frame) then
            if (o.bomb) then
                if (bomb == nil and o.frame < self.frame + PILOT_NEAR and AngleBetween(o.angle, self.angle) < PILOT_DODGE) then
                    bomb = o
                end
            elseif (target == nil) then
                target = o
            end
        end
    end
    local d = 0.0
    if (bomb ~= nil) then
        d = self.angle - bomb.angle                             -- away from it
        if (d > 128.0) then d = d - 256.0 elseif (d < -128.0) then d = d + 256.0 end
        if (math.abs(d) < 1.0) then d = 1.0 end
    elseif (target ~= nil) then
        d = target.angle - self.angle                           -- toward it
        if (d > 128.0) then d = d - 256.0 elseif (d < -128.0) then d = d + 256.0 end
        if (math.abs(d) < 2.0) then d = 0.0 end
    end
    if (d == 0.0) then return 0.0 end
    return (d > 0.0) and 1.0 or -1.0
end

-- ------------------------------------------------------------------ every frame
function SpecialStage:Tick(deltaTime)
    if (not self.built) then self:Build() end
    if (self.active == false) then return end       -- put away; the menu has the screen
    local dt = math.min(deltaTime, 0.05)

    -- paused: nothing moves; Up and Down pick CONTINUE or EXIT, Enter takes it, Escape continues
    if (self.paused) then
        if (Input.IsKeyJustDown(Key.Up) or Input.IsKeyJustDown(Key.W)
                or Input.IsKeyJustDown(Key.Down) or Input.IsKeyJustDown(Key.S)) then
            self.pauseIndex = 3 - self.pauseIndex
            self:Sound("MenuMove")
            if (self.uiReady) then TheSpecialStageUI:ShowPause(true, self.pauseIndex) end
        end
        if (Input.IsKeyJustDown(Key.Escape)) then
            self:SetPaused(false)
        elseif (Input.IsKeyJustDown(Key.Enter) or Input.IsKeyJustDown(Key.Space)) then
            if (self.pauseIndex == 1) then
                self:SetPaused(false)
            else
                self:Sound("MenuWarp")
                self:SetPaused(false)
                self:Leave()
                if (self.onExit ~= nil) then self.onExit() end
            end
        end
        return
    end
    if (Input.IsKeyJustDown(Key.Escape) and self.hold <= 0.0 and self.intro <= 0.0 and self.over < 0.0) then
        self:Sound("MenuSelect")
        self:SetPaused(true)
        return
    end

    if (Input.IsKeyJustDown(Key.R)) then
        self:Sound("MenuWarp")                          -- SpecialWarp, as for EXIT and a failed check
        self:Restart()
    end
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
                self:Sound("MenuWarp")                  -- SpecialWarp: the stage starts again
                self:Restart()                  -- a failed stage is played again
            else
                self:Finish()                   -- the emerald was taken: back to the menu
            end
        end
    end

    local before = self.frame
    -- THE PLAYER HAS NO CONTROL while the stage has it: the run up at the start (START on the
    -- screen), the thumbs-up after a check is passed, and from the emerald taken (or a check
    -- failed) to the end of the stage. Hands off, he slides back down to the floor.
    local locked = (self.hold > 0.0 or self.intro > 0.0 or self.thumbs > 0.0 or self.over >= 0.0)
    -- steering: round the pipe, and only round it, while his feet are on it
    local want = 0.0
    if (not locked and self.stun <= 0.0) then
        if (Input.IsKeyDown(Key.A)) then want = want + 1.0 end
        if (Input.IsKeyDown(Key.D)) then want = want - 1.0 end
    end
    want = want * self.data.angle_00_side                 -- A is always the player's left
    if (self.autoplay and not locked and self.stun <= 0.0) then
        want = self:Pilot()                               -- already in the angle's own sense
    end
    if (self.autoplay) then
        -- and says where it is, four times a second, for the photographer to time its shots by
        self.pilotSaid = (self.pilotSaid or 0.0) + dt
        if (self.pilotSaid >= 0.25) then
            self.pilotSaid = 0.0
            print(string.format("FRAME %.1f", self.frame))
            io.stdout:flush()
        end
    end
    local radius = self.data.pipe_radius
    if (self.height <= 0.0) then
        if (want ~= 0.0 and self.steer * want >= STEER * 0.97) then
            -- at full tilt (near enough: the grip only ever approaches it) and still holding:
            -- momentum builds
            self.steer = math.max(-STEER_MAX, math.min(STEER_MAX, self.steer + want * STEER_BUILD * dt))
        else
            local target, grip = want * STEER, STEER_GRIP
            if (want == 0.0) then
                -- hands off: gravity slides him back down toward the floor, and what speed he
                -- had round the pipe coasts off
                target, grip = -math.sin(self.angle * TWO_PI / 256.0) * SLIDE, STEER_COAST
            end
            self.steer = self.steer + (target - self.steer) * math.min(1.0, grip * dt)
        end
        self.angle = self:WrapAngle(self.angle + self.steer * dt)
        if (want == 0.0 and self.hold <= 0.0 and math.abs(self.angle) > FALL_ANGLE) then
            self.cling = self.cling + dt
            if (self.cling >= CLING) then
                self:LeaveSurface(0.0, false)   -- let go up the overhang: he drops off it, on his feet
                self.falling = true
            end
        else
            self.cling = 0.0
        end
    end

    -- jumping, and falling
    -- For testing the jump without playing: S2_AUTOJUMP=<frame> jumps there and logs the flight.
    local autoJump = false
    if (self.testJump ~= nil and self.frame >= self.testJump) then autoJump, self.testJump = true, nil end
    if (self.testDive ~= nil and self.height > 0.0 and not self.diving and self.fallTime >= self.testDive) then
        autoJump, self.testDive = true, nil
        if (self.testBounces > 0) then self.testBounces, self.testDive = self.testBounces - 1, self.testDiveAt end
    end
    if (not locked and (Input.IsKeyJustDown(Key.Space) or autoJump)) then
        if (self.height <= 0.0) then
            self:LeaveSurface(JUMP, want ~= 0.0)
            self:Sound("Jump")
        elseif (not self.diving) then
            -- THE DROP DASH (jump again in the air): straight DOWN, as the screen has it, from
            -- wherever he is, onto the pipe below him -- and his run round the pipe is kept for
            -- when he lands. It used to go away from the pipe's middle, which is down only from
            -- over the floor: from up a wall it threw him sideways into that wall.
            -- As fast as DIVE, and faster the faster he was flying: at a flat 45 it was a jolt of
            -- speed out of a standing hop but a brake out of a running jump.
            local speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
            self.vx, self.vy = 0.0, -(DIVE + DIVE_KEEP * speed)
            self.push, self.diving = 0.0, true
            self.diveSteer = self.steer
        end
    end
    if (self.height > 0.0) then
        -- A direction held in the air nudges the flight sideways (screen left or right), no
        -- more; a drop dash goes straight down regardless.
        if (want ~= 0.0 and not self.diving) then
            local dir = self.data.angle_00_side * want            -- +x is the player's left
            if (self.vx * dir < AIR_STEER_MAX) then
                self.vx = self.vx + dir * AIR_STEER * dt
            end
        end
        -- and the flight itself: the rest of the push builds over the first moments, then gravity
        if (not self.diving) then
            if (self.ramp < JUMP_RAMP and self.push > 0.0) then
                local step = math.min(dt, JUMP_RAMP - self.ramp) / JUMP_RAMP
                self.vx = self.vx + self.nx * self.push * step
                self.vy = self.vy + self.ny * self.push * step
                self.ramp = self.ramp + dt
            end
            self.vy = self.vy - self.gravity * dt
        end
        self.cx = self.cx + self.vx * dt
        self.cy = self.cy + self.vy * dt
        local r = math.sqrt(self.cx * self.cx + self.cy * self.cy)
        local t = math.atan(self.cx, -self.cy)                       -- round from the floor
        self.angle = self:WrapAngle(self.data.angle_00_side * t * 256.0 / TWO_PI)
        self.spin = self.spin + BALL_SPIN * dt
        self.fallTime = self.fallTime + dt
        if (self.testLog) then
            print(string.format("AIR frame %.2f height %.3f angle %.1f cx %.2f cy %.2f vx %.2f vy %.2f%s", self.frame,
                                radius - r, self.angle, self.cx, self.cy, self.vx, self.vy, self.diving and " DIVE" or ""))
        end
        if (r >= radius) then
            -- LANDED. His run round the pipe goes on at the speed he came in with along the
            -- surface: a throw across carries its momentum onto the other side. But never faster
            -- than he left it, or than plain steering -- the wind-up past STEER is earned by
            -- holding on the pipe, not by bouncing. After a drop dash, the run he had before it.
            if (self.diving) then
                self.steer = self.diveSteer or self.steer
            else
                local tangent = self.vx * math.cos(t) + self.vy * math.sin(t)     -- along the surface
                local landed = self.data.angle_00_side * tangent / radius * 256.0 / TWO_PI
                local cap = math.max(self.takeoffSteer or 0.0, STEER)
                self.steer = math.max(-cap, math.min(cap, landed))
            end
            self.steer = math.max(-STEER_MAX, math.min(STEER_MAX, self.steer))
            if (self.testLog) then print(string.format("LAND angle %.1f steer %.1f", self.angle, self.steer)) end
            local bounce = self.diving and BOUNCE > 0.0 and not locked
            self.height, self.diving, self.falling = 0.0, false, false
            if (bounce) then
                -- THE BOUNCE: straight back off the pipe where he hit it, his run round it going on
                -- as sideways speed (LeaveSurface), so he bounces along the pipe, not on one spot.
                self:LeaveSurface(JUMP * BOUNCE, true)
                self:Sound("Jump")
                if (self.testLog) then print(string.format("BOUNCE angle %.1f steer %.1f", self.angle, self.steer)) end
            end
        else
            self.height = radius - r
        end
    end

    -- forward, by himself
    if (self.hold > 0.0) then
        self.hold = self.hold - dt
        self.intro = self.hold
        self.frame = math.min(self.frame + SPEED * dt, 0.0)
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
    if (airborne and not self.falling) then
        mesh = self.meshBall
    else
        -- (at the start he is already running, up the lead-in, while START is up)
        local k = math.floor(self.runClock * SONIC_FPS) % SONIC_FRAMES
        mesh = (self.thumbs > 0.0) and self.sonicThumbs[k] or self.sonicRun[k]
    end
    if (mesh == nil) then mesh = self.meshBall end
    if (mesh ~= self.playerMesh) then
        self.playerMesh = mesh
        self.player:SetStaticMesh(mesh)
    end
    local place, fwd, inward = self:Place(self.frame, self.angle, 0.0)
    if (airborne) then
        -- in the air he is his point in the section, (cx, cy) from the axis, with the ball's
        -- radius added ALONG THE PUSH: added along his line to the axis instead, it would push
        -- his middle through the axis and out the other side near the top of a hop, a bob
        -- (The ball's middle is a radius in from his point, toward the pipe's axis -- so it sits on
        -- the surface he lands on, whichever side -- and less of one near the axis, where "toward
        -- the axis" swings right round and would make the ball jump.)
        local pos, fwdHere, upHere = self:TrackAt(self.frame)
        local left = Cross(upHere, fwdHere)
        local rr = math.sqrt(self.cx * self.cx + self.cy * self.cy)
        local x, y = self.cx, self.cy
        if (rr > 1e-3) then
            local k = BALL_RADIUS * math.min(1.0, rr / (self.data.pipe_radius * 0.6)) / rr
            x, y = x - self.cx * k, y - self.cy * k
        end
        place = Add(pos, Add(Scale(left, x), Scale(upHere, self.data.pipe_radius + y)))
    end
    self.player:SetWorldPosition(ToVec(place))
    if (airborne and not self.falling) then
        -- The ball rolls THE WAY IT IS GOING: about the line square to its flight (on along the
        -- track, and across and up or down the pipe's section) and to the track's up. It used to
        -- roll forward only, whichever way he flew, so a throw across the pipe looked like a spin
        -- on the spot while he sailed sideways.
        local _, fwdHere, upHere = self:TrackAt(self.frame)
        local left = Cross(upHere, fwdHere)
        local along = SPEED * (self.data.step or 1.0)
        local flight = Add(Scale(fwdHere, along), Add(Scale(left, self.vx), Scale(upHere, self.vy)))
        local axis = Cross(flight, upHere)
        if (Dot(axis, axis) < 1e-6) then axis = Cross(fwdHere, upHere) end
        axis = Normalize(axis)
        local function Turn(v)                                    -- v turned by spin about axis
            local c, sn = math.cos(self.spin), math.sin(self.spin)
            return Add(Add(Scale(v, c), Scale(Cross(axis, v), sn)), Scale(axis, Dot(axis, v) * (1.0 - c)))
        end
        self.player:SetWorldRotationQuat(FacingQuat(Turn(fwdHere), Turn(upHere)))
    elseif (airborne) then
        -- dropped off the wall: he swings upright as the fall starts, and falls feet first
        -- (turned about the track's forward, so upside down at the start is no trouble)
        local _, _, upHere = self:TrackAt(self.frame)
        local left = Cross(upHere, fwd)
        local theta = math.atan(Dot(inward, left), Dot(inward, upHere))
        local swing = theta * (1.0 - math.min(1.0, self.fallTime / FALL_TURN))
        local u = Add(Scale(upHere, math.cos(swing)), Scale(left, math.sin(swing)))
        self.player:SetWorldRotationQuat(FacingQuat(fwd, u))
    else
        self.player:SetWorldRotationQuat(FacingQuat(fwd, inward))
    end
    self.player:SetVisible(self.stun <= 0.0 or (math.floor(self.stun * 20.0) % 2 == 0))   -- flickers when hit
    -- his shadow stays on the pipe under him, and draws in as he jumps away from it. In the
    -- air "under him" is straight DOWN, onto the floor: his angle round the pipe means nothing
    -- near the axis (a hair to one side there is a quarter turn), and a shadow that followed it
    -- would fly to the rim on every hop
    if (self.playerShadow ~= nil) then
        local shadowAngle, drop = self.angle, self.height
        if (airborne) then
            local radius = self.data.pipe_radius
            local x = math.max(-radius, math.min(radius, self.cx))
            local floorY = -math.sqrt(radius * radius - x * x)
            shadowAngle = self.data.angle_00_side * math.asin(x / radius) * 256.0 / TWO_PI
            drop = math.max(0.0, self.cy - floorY)
        end
        self:PlaceShadow(self.playerShadow, self.frame, shadowAngle, drop, SHADOW_SONIC, SHADOW_SONIC)
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
    -- THE INTRO: a full circuit, blended out of the ordinary camera and back into it at its
    -- ends (both are behind him, where the circuit starts and ends). `phi` runs 0 .. 360.
    local introPhi, introLift = nil, 0.0
    if (self.intro > 0.0) then
        local u = 1.0 - self.intro / INTRO_TIME                 -- 0 at the start, 1 at the end
        local w = math.min(1.0, (INTRO_TIME - self.intro) / INTRO_IN, self.intro / INTRO_OUT)
        swing = w * w * w * (w * (w * 6.0 - 15.0) + 10.0)      -- smootherstep: starts and stops dead soft
        local ease = u * u * (3.0 - 2.0 * u)
        introPhi = ease * TWO_PI
        -- low at the front (phi near 180), up round the back and sides
        local front = 0.5 - 0.5 * math.cos(introPhi)            -- 0 behind, 1 in front
        front = front * front * front                           -- the dip is only at the front, not the sides
        introLift = INTRO_HIGH + (INTRO_LOW - INTRO_HIGH) * front
    end
    if (swing > 0.0) then
        -- In SONIC'S OWN frame, not the track's: his left, and his up (toward the pipe's axis).
        -- So wherever he is round the pipe the camera is beside him and inside it, and he is
        -- upright on the screen.
        local chest = Add(place, Scale(inward, 2.4))
        local left = Cross(inward, fwdHere)
        local phi, radius, lift = swing * math.rad(ORBIT_DEGREES), ORBIT_RADIUS, ORBIT_LIFT
        if (introPhi ~= nil) then phi, radius, lift = introPhi, INTRO_RADIUS, introLift end
        local orbit = Add(chest, Add(Scale(fwdHere, -math.cos(phi) * radius),
                                     Add(Scale(left, math.sin(phi) * radius), Scale(inward, lift))))
        eye = Add(Scale(eye, 1.0 - swing), Scale(orbit, swing))
        local aim = Add(chest, Scale(inward, 1.6))              -- a little over his chest: he sits low, the emblem above him
        if (introPhi ~= nil) then aim = chest end               -- the intro looks straight at him
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
