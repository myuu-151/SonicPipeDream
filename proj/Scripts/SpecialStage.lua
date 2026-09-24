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
Script.Require("GameOptions")   -- a marathon's (or time attack's) rounds and lives (OptionsPrompt.lua)

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
-- A drop dash does not land: it BOUNCES, like a tennis ball -- straight back up the screen, at once
-- and at full speed (no build-up, as a jump has: that rounded the bottom of the bounce off), under
-- stronger gravity, so it is quick and snappy rather than floaty. His run round the pipe is kept,
-- so he bounces along it. Jump again in the bounce: another drop dash, another bounce. Leave it
-- and he comes down from it and lands.
local BOUNCE = true
-- THE BOUNCE IS REACH: each one in a row goes higher than the last. Up the screen, units a second:
local BOUNCE_FIRST = 37.5       -- the first (about 4 units up)...
local BOUNCE_STEP = 9.5         -- ...each after it this much faster (6, then 9: a jump's height)...
local BOUNCE_TOP = 66.0         -- ...up to this (about 12 units: past a jump, still inside the pipe)
-- AND TIMING IS REACH: the drop dash asked for NEAR THE TOP of the flight -- the first press of A
-- in it within PEAK_WINDOW of the top -- sends the bounce straight to BOUNCE_TOP. Any other is one
-- step up from the last, as ever; so mashing A (the first press always early, on the way up) only
-- climbs, step by step. The drop dash itself still goes at the top of a bounce however early it
-- was asked for.
local BOUNCE_GRAVITY = 1.6      -- times GRAVITY while bouncing
-- and the ball squashes and stretches as a tennis ball does (visual only): tall as it drops, flat
-- as it hits, then springing tall and wobbling back to round
local DROP_STRETCH = 0.18       -- taller by this as a drop dash falls
local SQUASH = 0.42             -- flatter by this the instant it hits...
local SQUASH_DAMP = 7.0         -- ...the wobble dying away this fast...
local SQUASH_HZ = 4.5           -- ...at this many wobbles a second
local SQUASH_TIME = 0.5         -- and done by then

-- THE SPIN DASH. Hold R (the pad's R or ZR; E on a keyboard) with his feet on the pipe: he skids to
-- a stop, curled into the ball. Press A (Space) to rev it up -- each press adds charge, and charge
-- bleeds away between presses. Let go of R and he shoots off, and eases back to his own speed.
local PEAK_WINDOW = 0.1         -- seconds either side of the top of a flight that count as "near the top"
local SPIN_SKID = 0.35          -- seconds to skid from full speed to a stop
local SPIN_REV = 1.0            -- charge a press of A adds...
local SPIN_REV_MAX = 8.0        -- ...up to this
local SPIN_REV_BLEED = 1.2      -- charge lost a second, as a share of what there is (Sonic 2's 1/32 a frame)
local DASH_BASE = 1.6           -- times his speed at the launch, uncharged...
local DASH_PER_REV = 0.15       -- ...and this much more for each unit of charge (2.8 at full)
local DASH_EASE = 0.55          -- how fast the extra speed goes: a share a second
local DASH_BALL = 1.3           -- he stays curled up while he is going faster than this
local SPIN_TALL = 0.74          -- the ball's height while he revs, squashed down on the pipe...
local SPIN_PULSE = 0.16         -- ...and flatter still for a moment on each press, wobbling back
local DASH_LONG = 0.45          -- longer along the track by this the instant he goes, easing back
local DASH_STRETCH_TIME = 0.35
local BALL_ROLLS = true         -- the ball turns as it rolls (the GameCube's, gloss painted on, does not)

-- R held: the pad's R (a GameCube's) or ZR, or E on a keyboard.
local function SpinHeld()
    if (Input.IsKeyDown(Key.E)) then return true end
    return Input.IsGamepadButtonDown(Gamepad.R1) or Input.IsGamepadButtonDown(Gamepad.R2)
end
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
-- The spin dash's effects (native/gen_fx_assets.py's squares): shards thrown off the rev, puffs of
-- cloud left behind the dash, and a blue streak along the pipe behind the ball.
local RAZOR_EVERY, RAZOR_LIFE, RAZOR_SIZE = 0.03, 0.22, 1.0      -- while revving; a burst at each press
local RAZOR_BURST = 6
local PUFF_EVERY, PUFF_LIFE, PUFF_SIZE = 0.11, 0.55, 2.6         -- while dashing
local TRAIL_LIFE = 0.32         -- the tube traced behind the ball: how long a point of it lasts
local TRAIL_FADE = 1.3          -- how it fades along its length: 1 evenly, more for a longer bright head
local TRAIL_RADIUS = 1.15       -- its radius at the ball, as a share of the ball's (round it, not inside
                                -- it); it narrows to nothing, and its front is a dome over the ball
local TRACE_RINGS, TRACE_SIDES = 24, 10     -- native/gen_fx_assets.py's SM_FxTrace: keep in step
local TRACE_CAP = 4             -- of its rings, these are the dome over the ball
-- round a ring, once (cos, sin), for the trace's every frame
local TRACE_ROUND = {}
for k = 0, TRACE_SIDES do
    local a = 2.0 * math.pi * k / TRACE_SIDES
    TRACE_ROUND[k] = { math.cos(a), math.sin(a) }
end
-- Its colour, unlit: a deep blue through its middle, brightening to a light glowing blue at its edges
-- as the camera sees them (and more solid there), as an energy trail -- a flat blue read as dull.
local TRACE_CORE = { 0.04, 0.20, 0.95 }
local TRACE_RIM = { 0.22, 0.58, 1.0 }       -- (still a strong blue: lighter than this washed it out)
local TRACE_ALPHA = 0.9         -- at the ball, at its edges...
local TRACE_CLEAR = 0.55        -- ...and through its middle, as a share of that
local DASH_FX = 1.15            -- the puffs and the streak while he is going faster than this

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
-- THE MARATHON (StageDataMarathon, made ahead of time by gen_stage.py and written by
-- export_to_octave.py `-- marathon <seed>`): one run, zone after zone, each three checks, each
-- harder. A zone's third check leads to an ITEM (the chaos emerald, for now), and taking it is
-- THE HOLD: the thumbs-up, the camera on him, running on down plain straight pipe -- the zone's
-- ring check zone runs long for it (gen_stage.py, HOLD_PLAYS) -- while the pipe and the sky
-- change into the next zone's colours. A check failed ends the run: back to the menu.
-- (For now the colours SWITCH, once, with the camera on him. A crossfade drawn as a second copy
-- of the pipe over the first strobed -- two surfaces in one place fight over which is in front
-- -- and is not to come back; the crossfade is to be done in the pipe's material instead.)
local HOLD_MARGIN = 0.4         -- seconds before the hold's straights run out that control comes back
local SWITCH_AT = 1.6           -- seconds into the hold when the colours change
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
local function Sub(a, b) return { a[1] - b[1], a[2] - b[2], a[3] - b[3] } end
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

-- A time attack's time left as the screen shows it: M:SS, rounded UP (it reads 0:00 only when it
-- has run out). Whole seconds, so the text changes once a second, not every frame.
TIME_BONUS = 10.0               -- seconds a check passed puts back on a time attack's clock
function FormatClock(t)
    local s = math.max(0, math.ceil((t or 0.0) - 1e-6))
    return string.format("%d:%02d", s // 60, s % 60)
end

-- Quaternions as plain {x, y, z, w} tables, for laying a marathon's zones end to end.
local function QuatT(q) return { q.x, q.y, q.z, q.w } end
local function QuatMul(a, b)
    return { a[4] * b[1] + a[1] * b[4] + a[2] * b[3] - a[3] * b[2],
             a[4] * b[2] - a[1] * b[3] + a[2] * b[4] + a[3] * b[1],
             a[4] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[4],
             a[4] * b[4] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3] }
end
local function QuatConj(q) return { -q[1], -q[2], -q[3], q[4] } end

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
    self.bounceClock, self.bouncePress, self.firstPressToTop = nil, nil, nil     -- (a bounce sets its own, after this)
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
    self.meshFx = { sparkle = self.meshSparkle, boom = self.meshBoom, razor = LoadAsset("SM_FxQuadRazor"),
                    puff = LoadAsset("SM_FxQuadPuff") }
    self.meshTrace = LoadAsset("SM_FxTrace")
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
    if (n == "Marathon") then
        self.data = self:BuildMarathon()        -- a new one every run
    else
        Script.Require("StageData" .. n)
        self.data = _G["StageData" .. n]
    end
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
            self.pieceNodes[#self.pieceNodes + 1] = { node = node, name = name, frame = piece.first_frame }
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
    self.objStart = 1
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
    for s = 1, #self.data.sections do self:SpawnArch(s) end
    self.rainbowStep = -1

    -- the emerald, past the last check
    local last = self.data.sections[#self.data.sections]
    -- SM_Emerald_<stage>: each stage has its own chaos emerald (native/export_emeralds.py).
    -- Its reflection is fixed to the gem and drawn to be seen along its X, so it is turned to
    -- face back down the track, as a ring is.
    local emeraldFrame = last.check_frame + 10.0
    -- For looking at the emerald without playing to it: S2_TEST_EMERALD puts it just past the start.
    if (os ~= nil and os.getenv ~= nil and os.getenv("S2_TEST_EMERALD") ~= nil) then emeraldFrame = 16.0 end
    self.items = {}
    if (self.data.marathon) then
        -- an item past each zone's third check: the emeralds in turn, for now
        for s, section in ipairs(self.data.sections) do
            if (section.leads_to == "PALETTE SHIFT") then self:SpawnItem(s) end
        end
    else
        local where, emeraldFwd, emeraldUp = self:Place(emeraldFrame, 0.0, 4.0)
        self.emerald = SpawnMesh(world, LoadAsset("SM_Emerald_" .. self.data.stage) or LoadAsset("SM_Emerald"))
        self.emerald:SetWorldPosition(ToVec(where))
        self.emerald:SetWorldRotationQuat(FacingQuat(emeraldFwd, emeraldUp))
    end

    -- the sky that goes with this stage's colours (stage_palettes.py's SKY). Sky.lua picks
    -- up a change of `sky` on its next tick.
    if (TheSky ~= nil and self.data.sky ~= nil) then TheSky.sky = self.data.sky end
    self:Restart()
end

-- ------------------------------------------------------------------ the marathon, made as it is played
-- MarathonGen.lua builds a zone from nothing but (this run's seed, the zone's number) -- in the
-- game, so every run is new and no zone is ever seen twice. The first is built as the run starts;
-- each after it is built WHILE THE ONE BEFORE IS PLAYED, a slice a frame (a coroutine), and added
-- on the end of the track when it is done: its start set down exactly on the last one's end,
-- turned to carry on from it. Each zone gets a colour theme at random, never the last one's.
-- What has been passed goes, so a run can go on for as long as the player does.
local GEN_SLICE_MS = 4              -- milliseconds of building a frame, where the clock can be read
local BEHIND_FRAMES = 160           -- track kept behind him; pieces, arches and items further back go

-- Milliseconds, read NOW (not the frame's time): the engine's clock where it has one -- the
-- GameCube's os.clock is not to be trusted -- else os.clock. nil if there is neither.
local function ClockMs()
    if (System.GetClockMs ~= nil) then return System.GetClockMs() end
    if (os ~= nil and os.clock ~= nil) then return math.floor(os.clock() * 1000) end
    return nil
end

function SpecialStage:BuildMarathon()
    Script.Require("MarathonGen")
    local kit = MarathonKit
    -- the time of day, and the milliseconds since the game started (which the player's own timing
    -- decides): no two runs alike
    local seed = 12345
    if (os ~= nil and os.time ~= nil) then seed = math.floor(os.time()) * 1000 end
    seed = seed + (ClockMs() or math.floor(((Engine ~= nil and Engine.GetRealElapsedTime ~= nil)
                                            and Engine.GetRealElapsedTime() or 0) * 1000003))
    -- a whole number: the engine's Lua is 32-bit, and a float here made every number after it
    -- one (a palette of 2.0 named a mesh "..._P2.0", and the pipe was not there)
    seed = math.floor(seed % 2147483647)
    self.runSeed = seed
    self.trimmedTo = 0
    -- For native/check_marathon_gen.py: S2_GEN_DUMP=<dir> builds zones 1..S2_GEN_ZONES (default 10)
    -- of a few runs here and now, and writes each out to be solved.
    local dump = (os ~= nil and os.getenv ~= nil) and os.getenv("S2_GEN_DUMP") or nil
    if (dump ~= nil) then
        local zones = tonumber(os.getenv("S2_GEN_ZONES") or "") or 10
        local runs = tonumber(os.getenv("S2_GEN_RUNS") or "") or 1
        for r = 1, runs do
            for z = 1, zones do
                local t0 = os.clock()
                local zone = MarathonGen.BuildZone(seed + r, z)
                if (zone ~= nil) then MarathonGen.Dump(zone, string.format("%s/gen_%d_%d.json", dump, r, z)) end
                print(string.format("GENDUMP run %d zone %d %s %.3f s, %d tries", r, z, zone and "ok" or "FAILED", os.clock() - t0, zone and zone.tries or 0))
            end
        end
        print("GENDUMP done")
    end
    local data = { name = "Marathon", stage = "Marathon", marathon = true, step = kit.step,
                   pipe_radius = kit.pipe_radius, hover = kit.hover, angle_00_side = kit.angle_00_side,
                   arch = kit.arch, palette_skies = kit.palette_skies, pieces = {}, sections = {}, path = {},
                   frames = 0 }
    data.join = { offset = 0, quota = 0, rng = seed }
    -- THE TIME ATTACK is this same run against the clock (GameOptions.run, set by the menu): the
    -- rings ask nothing at the checks, they only save him from a hit, and a hit with none costs a
    -- life (Collide). The clock counts DOWN from the setup's time; each check passed puts
    -- TIME_BONUS back, and at 0 the run is over.
    data.timeAttack = (GameOptions ~= nil and GameOptions.run == "timeAttack") or nil
    local t0 = (os ~= nil and os.clock ~= nil) and os.clock() or 0
    local zone = MarathonGen.BuildZone(seed, 1)
    if (zone == nil) then return nil end
    if (os ~= nil and os.clock ~= nil) then print(string.format("MARATHON zone 1 built in %.3f s", os.clock() - t0)) end
    self:JoinZone(data, zone)
    data.palette = data.sections[1].palette
    data.sky = data.palette_skies[data.palette]
    self.zonesBuilt = 1
    self.gen = nil
    print("MARATHON run " .. seed)
    return data
end

-- A zone added to the run's table: set on the end of the last, its frames counted on from there.
function SpecialStage:JoinZone(data, zone)
    local j = data.join
    local s0 = zone.path[1]
    local o0, f0, u0 = { s0[1], s0[2], s0[3] }, { s0[4], s0[5], s0[6] }, { s0[7], s0[8], s0[9] }
    local l0 = Cross(f0, u0)
    local pE, fE, uE, lE = j.endPos or o0, j.endF or f0, j.endU or u0, j.endL or l0
    local function Turn(v) return Add(Add(Scale(fE, Dot(v, f0)), Scale(uE, Dot(v, u0))), Scale(lE, Dot(v, l0))) end
    local function Put(p) return Add(pE, Turn({ p[1] - o0[1], p[2] - o0[2], p[3] - o0[3] })) end
    local turnQ = QuatMul(QuatT(QuatFromAxes(fE, uE, lE)), QuatConj(QuatT(QuatFromAxes(f0, u0, l0))))
    -- a colour theme at random, never the last one's (a small generator of its own: math.random
    -- is shared with everything else)
    j.rng = math.floor((j.rng * 1103515245 + 12345) % 2147483648)
    local palette = math.floor((j.rng // 65536) % 7) + 1
    if (palette == j.lastPalette) then palette = palette % 7 + 1 end
    j.lastPalette = palette
    local offset = j.offset
    for _, piece in ipairs(zone.pieces) do
        data.pieces[#data.pieces + 1] = { mesh = piece.mesh, gloss = piece.gloss, pos = Put(piece.pos),
                                          quat = QuatMul(turnQ, piece.quat), first_frame = piece.first_frame + offset,
                                          last_frame = piece.last_frame + offset }
    end
    -- The zone's own tables are TAKEN, moved into place, not copied: at difficulty 7 a zone is some
    -- 3000 frames and 1500 rings and bombs, and a copy of each, made while the zone's were still
    -- alive, was what ran a console's heap out as the second zone joined.
    for i, e in ipairs(zone.path) do
        if (#data.path == 0 or i > 1) then           -- the join is one frame, the last zone's end
            local p = Put({ e[1], e[2], e[3] })
            local f = Turn({ e[4], e[5], e[6] })
            local u = Turn({ e[7], e[8], e[9] })
            e[1], e[2], e[3], e[4], e[5], e[6], e[7], e[8], e[9] = p[1], p[2], p[3], f[1], f[2], f[3], u[1], u[2], u[3]
            data.path[#data.path + 1] = e
        end
    end
    for _, sec in ipairs(zone.sections) do
        j.quota = j.quota + sec.asks
        local objects = sec.objects
        for _, o in ipairs(objects) do o[1] = o[1] + offset end
        data.sections[#data.sections + 1] = {
            first_frame = sec.first_frame + offset, check_frame = sec.check_frame + offset,
            last_frame = sec.last_frame + offset, quota = j.quota, asks = sec.asks, rings = sec.rings,
            leads_to = sec.leads_to, objects = objects, palette = palette }
    end
    j.offset = offset + zone.frames
    data.frames = j.offset
    local last = data.path[#data.path]
    j.endPos, j.endF, j.endU = { last[1], last[2], last[3] }, { last[4], last[5], last[6] }, { last[7], last[8], last[9] }
    j.endL = Cross(j.endF, j.endU)
end

-- A zone built while the run went on: joined on, and everything it needs on the screen spawned --
-- its pieces (in the colours up now: the whole track takes the next zone's at the hold), its
-- rings and bombs, the arches over its checks, the item after its third.
function SpecialStage:AppendZone(zone)
    local world = self:GetWorld()
    local data = self.data
    local p0, s0 = #data.pieces, #data.sections
    self:JoinZone(data, zone)
    for i = p0 + 1, #data.pieces do
        local piece = data.pieces[i]
        for _, name in ipairs({ piece.mesh, piece.gloss }) do
            local node = SpawnMesh(world, self:PieceMesh(name, self.palette))
            node:SetWorldPosition(Vec(piece.pos[1], piece.pos[2], piece.pos[3]))
            node:SetWorldRotationQuat(Vec(piece.quat[1], piece.quat[2], piece.quat[3], piece.quat[4]))
            self.pieceNodes[#self.pieceNodes + 1] = { node = node, name = name, frame = piece.first_frame }
        end
    end
    for s = s0 + 1, #data.sections do
        local section = data.sections[s]
        for _, o in ipairs(section.objects) do
            self.objects[#self.objects + 1] = { frame = o[1], angle = o[2], bomb = (o[3] == 1), section = s }
        end
        self:SpawnArch(s)
        if (section.leads_to == "PALETTE SHIFT") then self:SpawnItem(s) end
    end
    self.zonesBuilt = self.zonesBuilt + 1
    print(string.format("MARATHON zone %d joined: %d pieces, %d sections, track %d frames",
                        self.zonesBuilt, #data.pieces - p0, #data.sections - s0, data.frames))
    -- a hold that ran out of track waiting for this zone takes its colours now
    if (self.waitingZone) then
        self.waitingZone = false
        self.holding = { clock = 0.0, to = data.sections[s0 + 1].palette }
    end
end

-- Run a slice of the next zone's building, and start the one after when the player is into the
-- last one built: one zone ahead, never more.
function SpecialStage:TickMarathonGen()
    if (not self.data.marathon) then return end
    local spz = MarathonKit.design.sections_per_zone
    local playing = (self.section - 1) // spz + 1              -- the zone he is in
    -- the run's length (GameOptions: ROUNDS, 0 endless): no zone is built past the last, and the
    -- last one's hold ends the run (PassZone)
    local rounds = (GameOptions ~= nil and GameOptions.Run().rounds) or 0
    if (rounds > 0 and self.zonesBuilt >= rounds) then return end
    if (self.gen == nil and self.zonesBuilt <= playing) then
        local seed, z = self.runSeed, self.zonesBuilt + 1
        self.gen = coroutine.create(function() return MarathonGen.BuildZone(seed, z) end)
        self:TrimBehind()
    end
    if (self.gen == nil) then return end
    local t0 = ClockMs()
    repeat
        local ok, zone = coroutine.resume(self.gen)
        if (not ok) then
            Log.Error("MarathonGen: " .. tostring(zone))
            self.genError = tostring(zone)          -- (kept for a console's on-screen readout)
            self.gen = nil
            return
        end
        if (coroutine.status(self.gen) == "dead") then
            self.gen = nil
            if (zone ~= nil) then
                self:AppendZone(zone)
            else
                self.genError = "zone " .. (self.zonesBuilt + 1) .. " could not be built"
            end
            return
        end
    until (t0 == nil or ClockMs() - t0 >= GEN_SLICE_MS)
end

-- What is well behind him goes: the track's pieces, the arches, the items, the rings and bombs
-- already met. (The sections themselves stay: they are small, and counted by number.)
function SpecialStage:TrimBehind()
    local limit = self.frame - BEHIND_FRAMES
    local keep = {}
    for _, p in ipairs(self.pieceNodes) do
        if (p.frame ~= nil and p.frame < limit - 100) then p.node:Destruct() else keep[#keep + 1] = p end
    end
    self.pieceNodes = keep
    for s, rings in pairs(self.arches) do
        if (self.data.sections[s].check_frame < limit) then
            for _, node in pairs(rings) do node:Destruct() end
            self.arches[s] = nil
        end
    end
    for s, node in pairs(self.items) do
        if (self.data.sections[s].check_frame < limit) then
            node:Destruct()
            self.items[s] = nil
        end
    end
    local kept = {}
    for _, o in ipairs(self.objects) do
        if (o.frame < limit) then
            if (o.node ~= nil) then self:Release(o) end
        else
            kept[#kept + 1] = o
        end
    end
    self.objects = kept
    self.objStart = 1
    -- and the run's own table: the centre line and the rings of what is long gone (a zone's path
    -- is a table a frame, and a run can go on for as long as the player does). The frames gone all
    -- share the oldest one kept -- not nil, which would leave #path, and so the next zone's join,
    -- to chance.
    local data = self.data
    local upTo = math.min(math.floor(limit) - 100, #data.path - 1)
    if (upTo > (self.trimmedTo or 0)) then
        local oldest = data.path[upTo + 1]
        for f = (self.trimmedTo or 0) + 1, upTo do data.path[f] = oldest end
        self.trimmedTo = upTo
    end
    for _, section in ipairs(data.sections) do
        if (section.last_frame < limit) then section.objects = {} end
    end
end

-- The rainbow arch over check s.
function SpecialStage:SpawnArch(s)
    local world = self:GetWorld()
    local arch = self.data.arch
    local section = self.data.sections[s]
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

-- The item past a marathon zone's third check (section s): the emerald of the zone's colours (the
-- palette of stage n is stage n's colours, and so its emerald) -- which the loading screen shows too.
function SpecialStage:SpawnItem(s)
    local palette = self.data.sections[s].palette or 1
    local at, fwd, up = self:Place(self.data.sections[s].check_frame + 10.0, 0.0, 4.0)
    local node = SpawnMesh(self:GetWorld(), LoadAsset("SM_Emerald_" .. ((palette - 1) % LAST_STAGE + 1)) or LoadAsset("SM_Emerald"))
    node:SetWorldPosition(ToVec(at))
    node:SetWorldRotationQuat(FacingQuat(fwd, up))
    self.items[s] = node
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
    for _, node in pairs(self.items or {}) do node:Destruct() end
    self.items = {}
    self:EndFade(false)
end

-- ------------------------------------------------------------------ coming and going
-- The emerald ends the stage: it is won, and the stage select comes back with that emerald
-- in colour. One stage does not run into the next -- you choose the next one yourself.
-- THE RUN-OUT: when the run ends he runs on for some seconds, and the track he had ended there --
-- he ran into its end and stopped dead, as if against a wall. So it goes on: the centre line
-- carried straight on from its last frame, and the last piece (a straight: every zone and stage
-- ends on them) laid again and again ahead, as the lead-in is laid behind the start.
function SpecialStage:LayRunOut(seconds)
    local data = self.data
    local path, pieces = data.path, data.pieces
    local want = math.ceil(self.frame + seconds * SPEED) + 16 - (#path - 1)
    local last = pieces[#pieces]
    if (want <= 0 or last == nil or #path < 9) then return end
    -- the centre line: one frame's step, on and on, facing as the last frame does
    local n = #path
    local e, d = path[n], path[n - 1]
    local sx, sy, sz = e[1] - d[1], e[2] - d[2], e[3] - d[3]
    for i = 1, want do
        path[n + i] = { e[1] + sx * i, e[2] + sy * i, e[3] + sz * i, e[4], e[5], e[6], e[7], e[8], e[9] }
    end
    -- the pieces: the last one again, a straight's length (eight frames) further each time
    local world = self:GetWorld()
    local lengths = math.ceil(want / 8)
    for k = 1, lengths do
        for _, name in ipairs({ last.mesh, last.gloss }) do
            local node = SpawnMesh(world, self:PieceMesh(name, self.palette))
            node:SetWorldPosition(Vec(last.pos[1] + sx * 8 * k, last.pos[2] + sy * 8 * k, last.pos[3] + sz * 8 * k))
            node:SetWorldRotationQuat(Vec(last.quat[1], last.quat[2], last.quat[3], last.quat[4]))
            -- (first and last: the frames it spans, which the GameCube's UpdatePieces shows it by)
            self.pieceNodes[#self.pieceNodes + 1] = { node = node, name = name, frame = last.first_frame + 8 * k,
                                                      first = last.first_frame + 8 * k, last = last.last_frame + 8 * k }
        end
    end
end

-- A time attack's hit with no rings to lose: a life gone, or, the last, the run over.
function SpecialStage:LoseLife()
    if (self.lives == 0) then return end                -- never out
    if (self.lives > 1) then
        self.lives = self.lives - 1
        self:Sound("Fail")
        if (self.uiReady) then
            TheSpecialStageUI:ShowBanner((self.lives == 1) and "LAST LIFE" or (self.lives .. " LIVES LEFT"), 2.5)
        end
        return
    end
    self.clockStopped = true
    self.over = 3.5
    self.failed = true
    self:Sound("Fail")
    if (self.uiReady) then TheSpecialStageUI:ShowBanner("GAME OVER", 3.2) end
end

function SpecialStage:Finish()
    local won = (not self.data.marathon) and self.stage or nil
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
    self.objStart = 1
    self.frame = -SPEED * START_HOLD    -- back up the lead-in: at the start proper as START scatters
    self.angle = 0.0                -- 0 is the floor's centre line; it wraps at +-128
    self.steer = 0.0
    self.height = 0.0               -- off the pipe's surface
    self.bounces = 0                -- drop dash bounces in a row
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
    self.spinDash = nil             -- revving a spin dash: { rev, pulse }
    self.skid = nil                 -- his speed while he skids into it (1 is his own)
    self.boost = 1.0                -- his speed after one (1 is his own; eases back to it)
    self.dashClock = nil            -- time since the last launch (the stretch)
    self.dashRoll = 0.0             -- the curled ball's turn on the pipe
    -- For testing the spin dash without a pad: S2_TEST_SPIN=<seconds> holds R that long into the
    -- run, revs four times and lets go, and again every 8 seconds.
    self.testSpin = (os ~= nil and os.getenv ~= nil and tonumber(os.getenv("S2_TEST_SPIN") or "")) or nil
    self.testSpinClock = 0.0
    -- A time attack's lives (GameOptions: LIVES; 0 is never out): a hit with no rings costs one.
    self.lives = (self.data.timeAttack and GameOptions ~= nil) and GameOptions.timeAttack.lives or 1
    -- a time attack's time left: from the setup's, down
    self.timeLeft = (self.data.timeAttack and GameOptions ~= nil) and GameOptions.timeAttack.time or 0.0
    self.clockStopped = false
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
        self.testHold = os.getenv("S2_AUTOHOLD") ~= nil           -- as if jump were held down
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
    self.thumbsTotal = THUMBS_TIME  -- how long this thumbs-up is, all told (a marathon's hold is longer)
    self.runClock = 0.0
    if (self.emerald ~= nil) then self.emerald:SetVisible(true) end
    for _, node in pairs(self.items or {}) do node:SetVisible(true) end
    self.holding = nil
    if (self.data.marathon) then
        self:EndFade(false)
        self:SetPalette(self.data.palette)          -- from the first zone's colours again
    end
    self.uiReady = false
    self.failed = false
    self.fxPool = self.fxPool or {}
    for _, kind in ipairs({ "sparkle", "boom", "razor", "puff" }) do
        self.fxPool[kind] = self.fxPool[kind] or {}
    end
    self.fxClock = { razor = 0.0, puff = 0.0 }
    self.trace = {}
    self.tubeNodes = self.tubeNodes or {}
    self.tubeMats = self.tubeMats or {}
    for _, node in ipairs(self.tubeNodes) do node:SetVisible(false) end
    if (self.tubeCap ~= nil) then self.tubeCap:SetVisible(false) end
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
        local mesh = (self.meshFx ~= nil and self.meshFx[kind]) or ((kind == "boom") and self.meshBoom or self.meshSparkle)
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

-- THE SPIN DASH'S EFFECTS, spawned as he goes. Shards spray back off the ball while he revs (a burst
-- at each press); while he dashes, puffs of cloud are left behind and a blue streak runs along the
-- pipe behind the ball. The puffs and the streak stay where they were dropped (`at`, a frame of the
-- track); a ring's sparkles move with him (`ahead`).
function SpecialStage:SpinFx(dt, burst)
    local clock = self.fxClock
    if (clock == nil) then return end
    local back = BALL_RADIUS / (self.data.step or 5.0)          -- the ball's back, in frames behind him
    local function Razor()
        -- from the back of the ball, spat outward: back, and up or round the pipe, fanned out
        local node = self:FxNode("razor")
        if (node == nil) then return end
        -- (where the ball meets the pipe, at its back: sprayed out round the pipe and back along it,
        -- rising only a little, as sparks off a wheel spinning on the spot)
        local side = (math.random() < 0.5) and -1.0 or 1.0
        self.fx[#self.fx + 1] = { kind = "razor", node = node, age = 0.0, life = RAZOR_LIFE * (0.7 + math.random() * 0.6),
                                  ahead = -back * 0.6, angle = self.angle, height = 0.15,
                                  dAngle = side * (6.0 + math.random() * 22.0), dHeight = 0.2 + math.random() * 1.2,
                                  dAhead = -(0.4 + math.random() * 0.9), size = RAZOR_SIZE * (0.7 + math.random() * 0.6),
                                  long = 2.6, floor = 0.1 }
    end
    if (self.spinDash ~= nil) then
        for _ = 1, (burst and RAZOR_BURST or 0) do Razor() end
        clock.razor = clock.razor + dt
        while (clock.razor >= RAZOR_EVERY) do
            clock.razor = clock.razor - RAZOR_EVERY
            Razor()
        end
    else
        clock.razor = 0.0
    end
    if (self.boost > DASH_FX and self.height <= 0.0) then
        clock.puff = clock.puff + dt
        -- the tube: where the ball's middle is, every frame (see TraceTube)
        if (dt > 0.0) then
            local here = self:Place(self.frame, self.angle, BALL_RADIUS)
            table.insert(self.trace, 1, { pos = here, age = 0.0 })
        end
        while (clock.puff >= PUFF_EVERY) do
            clock.puff = clock.puff - PUFF_EVERY
            local node = self:FxNode("puff")
            if (node ~= nil) then
                self.fx[#self.fx + 1] = { kind = "puff", node = node, age = 0.0, life = PUFF_LIFE,
                                          at = self.frame - 0.8, angle = self.angle + (math.random() - 0.5) * 10.0,
                                          height = 0.6, dAngle = (math.random() - 0.5) * 12.0,
                                          dHeight = 1.2 + math.random() * 0.8, size = PUFF_SIZE * (0.8 + math.random() * 0.4) }
            end
        end
    else
        clock.puff = 0.0
    end
    self:TraceTube(dt)
end

-- The trace as ONE mesh (SM_FxTrace): its rings laid along the path every frame -- the dome over the
-- ball first, then back along the way it went, spaced evenly by distance -- each ring a little
-- narrower and more see-through than the last, so it is one tube that fades out, with no joins.
function SpecialStage:TraceMesh(trace)
    local node = self.traceNode
    if (node == nil) then
        node = SpawnMesh(self:GetWorld(), self.meshTrace)
        node:SetWorldPosition(Vec(0.0, 0.0, 0.0))    -- its vertices are where they are in the world
        self.traceNode = node
    end
    if (#trace < 2) then
        node:SetVisible(false)
        return
    end
    -- the path's length, point to point from the ball back
    local lengths, total = { 0.0 }, 0.0
    for i = 2, #trace do
        local v = Sub(trace[i - 1].pos, trace[i].pos)
        total = total + math.sqrt(Dot(v, v))
        lengths[i] = total
    end
    if (total < 1e-3) then
        node:SetVisible(false)
        return
    end
    local head = trace[1].pos
    local ahead = Sub(trace[1].pos, trace[2].pos)
    ahead = Scale(ahead, 1.0 / math.max(1e-4, math.sqrt(Dot(ahead, ahead))))
    local _, _, upHere = self:Place(self.frame, self.angle, 0.0)
    local radius = BALL_RADIUS * TRAIL_RADIUS
    -- the same two tables every frame, filled in place (a GameCube notices the garbage otherwise)
    self.traceXyz, self.traceRgba = self.traceXyz or {}, self.traceRgba or {}
    local xyz, rgba = self.traceXyz, self.traceRgba
    local vi, ci = 0, 0
    local look = Normalize(self.camLook or { 0.0, 0.0, -1.0 })
    local lx, ly, lz = look[1], look[2], look[3]
    local seg = 2
    for r = 1, TRACE_RINGS do
        local centre, along, ringR, u
        if (r <= TRACE_CAP) then
            -- the dome: from its tip ahead of the ball back to its rim round the ball
            local lat = (math.pi * 0.5) * (TRACE_CAP - r) / TRACE_CAP
            centre = Add(head, Scale(ahead, radius * math.sin(lat)))
            ringR, along, u = radius * math.cos(lat), ahead, 0.0
        else
            -- back along the path, evenly by distance
            u = (r - TRACE_CAP) / (TRACE_RINGS - TRACE_CAP)
            local want = u * total
            while (seg < #trace and lengths[seg] < want) do seg = seg + 1 end
            local a, b = trace[seg - 1].pos, trace[seg].pos
            local span = math.max(1e-4, lengths[seg] - lengths[seg - 1])
            local t = math.min(1.0, math.max(0.0, (want - lengths[seg - 1]) / span))
            centre = Add(a, Scale(Sub(b, a), t))
            along = Sub(a, b)
            along = Scale(along, 1.0 / math.max(1e-4, math.sqrt(Dot(along, along))))
            ringR = radius * (1.0 - u) ^ 0.7
        end
        local y = Sub(upHere, Scale(along, Dot(upHere, along)))
        if (Dot(y, y) < 1e-6) then y = { 0.0, 1.0, 0.0 } end
        y = Normalize(y)
        local z = Cross(along, y)
        -- where it is wider than the ball, lifted by the difference: its bottom stays on the pipe
        centre = Add(centre, Scale(upHere, math.max(0.0, ringR - BALL_RADIUS * 0.97)))
        local alpha = TRACE_ALPHA * (1.0 - u) ^ TRAIL_FADE
        local ox, oy, oz = centre[1], centre[2], centre[3]
        for k = 0, TRACE_SIDES do
            local cs = TRACE_ROUND[k]
            -- the way this vertex faces, and how edge-on the camera sees it (1 at the edge)
            local nx = y[1] * cs[1] + z[1] * cs[2]
            local ny = y[2] * cs[1] + z[2] * cs[2]
            local nz = y[3] * cs[1] + z[3] * cs[2]
            local rim = 1.0 - math.abs(nx * lx + ny * ly + nz * lz)
            rim = rim * rim
            xyz[vi + 1], xyz[vi + 2], xyz[vi + 3] = ox + nx * ringR, oy + ny * ringR, oz + nz * ringR
            rgba[ci + 1] = TRACE_CORE[1] + (TRACE_RIM[1] - TRACE_CORE[1]) * rim
            rgba[ci + 2] = TRACE_CORE[2] + (TRACE_RIM[2] - TRACE_CORE[2]) * rim
            rgba[ci + 3] = TRACE_CORE[3] + (TRACE_RIM[3] - TRACE_CORE[3]) * rim
            rgba[ci + 4] = alpha * (TRACE_CLEAR + (1.0 - TRACE_CLEAR) * rim)
            vi, ci = vi + 3, ci + 4
        end
    end
    node:SetVisible(self.meshTrace:SetVertexData(xyz, rgba))
end

-- THE TUBE TRACED BEHIND THE BALL, as Sonic Adventure's: the ball's middle, frame by frame, joined
-- up by lengths of an open cylinder, each from one point to the next, so it is one unbroken tube
-- along exactly the way the ball went. Each point is dropped as it ages, and the tube narrows to
-- nothing toward its tail.
function SpecialStage:TraceTube(dt)
    local trace = self.trace
    for _, p in ipairs(trace) do p.age = p.age + dt end
    while (#trace > 0 and trace[#trace].age >= TRAIL_LIFE) do table.remove(trace) end
    if (self.meshTrace ~= nil and self.meshTrace.SetVertexData ~= nil) then
        self:TraceMesh(trace)
        return
    end
    local nodes = self.tubeNodes
    local used = 0
    if (self.meshTube ~= nil) then
        for i = 1, #trace - 1 do
            local a, b = trace[i], trace[i + 1]
            local v = Sub(a.pos, b.pos)
            local len = math.sqrt(Dot(v, v))
            if (len > 1e-3) then
                used = used + 1
                local node = nodes[used]
                if (node == nil) then
                    node = SpawnMesh(self:GetWorld(), self.meshTube)
                    nodes[used] = node
                    -- its own material, so each length can fade on its own
                    self.tubeMats[used] = (node.InstantiateMaterial ~= nil) and node:InstantiateMaterial() or nil
                end
                local mat = self.tubeMats[used]
                if (mat ~= nil and mat.SetOpacity ~= nil) then
                    -- bright at the ball, fading out to nothing at the tail
                    local along = (i - 1) / math.max(1, #trace - 1)
                    mat:SetOpacity(math.max(0.0, 1.0 - along) ^ TRAIL_FADE)
                end
                local x = Scale(v, 1.0 / len)
                local ref = (math.abs(x[2]) < 0.9) and { 0.0, 1.0, 0.0 } or { 1.0, 0.0, 0.0 }
                local y = Normalize(Sub(ref, Scale(x, Dot(ref, x))))
                local r = BALL_RADIUS * TRAIL_RADIUS * math.max(0.0, 1.0 - b.age / TRAIL_LIFE) ^ 0.7
                node:SetVisible(true)
                node:SetWorldPosition(ToVec(b.pos))
                node:SetWorldRotationQuat(QuatFromAxes(x, y, Cross(x, y)))
                node:SetScale(Vec(len, r * 2.0, r * 2.0))
            end
        end
    end
    for i = used + 1, #nodes do nodes[i]:SetVisible(false) end

    -- the front: a dome over the ball, turned the way it is going, as wide as the tube there
    if (self.tubeCap == nil and self.meshTubeCap ~= nil) then
        self.tubeCap = SpawnMesh(self:GetWorld(), self.meshTubeCap)
    end
    if (self.tubeCap ~= nil) then
        local shown = false
        if (#trace >= 2 and trace[1].age < 0.05) then
            local v = Sub(trace[1].pos, trace[2].pos)
            local len = math.sqrt(Dot(v, v))
            if (len > 1e-3) then
                local x = Scale(v, 1.0 / len)
                local ref = (math.abs(x[2]) < 0.9) and { 0.0, 1.0, 0.0 } or { 1.0, 0.0, 0.0 }
                local y = Normalize(Sub(ref, Scale(x, Dot(ref, x))))
                local d = BALL_RADIUS * TRAIL_RADIUS * 2.0
                self.tubeCap:SetWorldPosition(ToVec(trace[1].pos))
                self.tubeCap:SetWorldRotationQuat(QuatFromAxes(x, y, Cross(x, y)))
                self.tubeCap:SetScale(Vec(d, d, d))
                shown = true
            end
        end
        self.tubeCap:SetVisible(shown)
    end
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
            local function At(u)
                local frame = fx.at or (self.frame + fx.ahead + (fx.dAhead or 0.0) * u)
                return self:Place(frame, fx.angle + fx.dAngle * u, math.max(fx.floor or -99.0, fx.height + fx.dHeight * u))
            end
            local place = At(t)
            local size, sx, rotation = nil, nil, facing
            if (fx.kind == "boom") then
                size = fx.size * (0.55 + 0.45 * t)
                local frame = math.min(BOOM_FRAMES - 1, math.floor(t * BOOM_FRAMES))
                if (frame ~= self.boomFrame and self.boomMaterial ~= nil and self.boomTextures[frame] ~= nil) then
                    self.boomFrame = frame
                    self.boomMaterial:SetTexture(1, self.boomTextures[frame])
                end
            elseif (fx.kind == "razor") then
                -- a shard flies off and thins away, pointed the way it flies (on the screen)
                size = fx.size * (1.0 - t)
                sx = size * fx.long
                local toward = Scale(Normalize(self.camLook or { 0.0, 0.0, -1.0 }), -1.0)   -- to the camera
                local v = Sub(At(t + 0.05), place)
                v = Sub(v, Scale(toward, Dot(v, toward)))
                if (Dot(v, v) > 1e-8) then
                    local x = Normalize(v)
                    rotation = QuatFromAxes(x, Cross(toward, x), toward)
                end
            elseif (fx.kind == "puff") then
                -- a puff swells as it rises, and shrinks away at the end
                size = fx.size * (0.5 + 0.7 * t) * math.min(1.0, (1.0 - t) * 4.0)
            else
                -- a sparkle swells, twinkles and goes
                size = fx.size * math.sin(math.pi * t) * (0.75 + 0.25 * math.sin(fx.age * 50.0))
            end
            fx.node:SetVisible(fx.age >= 0.0)
            fx.node:SetWorldPosition(ToVec(place))
            fx.node:SetWorldRotationQuat(rotation)
            fx.node:SetScale(Vec(sx or size, size, size))
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
    -- The list is in frame order: start at the first not yet left behind (everything before it
    -- has been let go), and stop past what he can see. A marathon's list is thousands long.
    local objects = self.objects
    local start = self.objStart or 1
    while (start <= #objects and objects[start].frame < lo - 1.0 and objects[start].node == nil) do
        start = start + 1
    end
    self.objStart = start
    for i = start, #objects do
        local o = objects[i]
        if (o.frame > hi) then break end
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
    for i = self.objStart or 1, #self.objects do
        local o = self.objects[i]
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
                if (had == 0 and self.data.timeAttack and self.over < 0.0) then self:LoseLife() end
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
    local quota = self.data.timeAttack and 0 or section.quota      -- a time attack's checks ask nothing
    if (self.data.timeAttack and not self.clockStopped) then self.timeLeft = self.timeLeft + TIME_BONUS end
    if (self.rings >= quota) then
        if (self.data.marathon and section.leads_to == "PALETTE SHIFT") then
            self:PassZone(section)
            self.section = self.section + 1
            return
        end
        -- COOL ! and the thumbs-up emblem are for a CHECK. The emerald has its own words.
        if (self.uiReady and section.leads_to ~= "EMERALD") then TheSpecialStageUI:ShowCool() end
        self.thumbs, self.thumbsTotal = THUMBS_TIME, THUMBS_TIME
        self:Sound((section.leads_to == "EMERALD") and "GetEmerald" or "Checkpoint")
        if (section.leads_to == "EMERALD") then
            self.emerald:SetVisible(false)
            self.over = 5.0
            self:LayRunOut(self.over)
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

-- A marathon zone's third check passed: its item is taken, and THE HOLD begins -- thumbs up,
-- the camera on him, running on down the long straight after the check while the colours
-- crossfade into the next zone's. The last zone of the run ends it instead.
function SpecialStage:PassZone(section, missed)
    local s = self.section
    local say = function(text, seconds)
        -- (a missed check with a life to spare has already said so: PassChecks)
        if (self.uiReady and not missed) then TheSpecialStageUI:ShowBanner(text, seconds) end
    end
    if (not missed) then
        if (self.items[s] ~= nil) then self.items[s]:SetVisible(false) end
        self:Sound("GetEmerald")
    end
    local nextSection = self.data.sections[s + 1]
    -- the thumbs-up lasts as long as the straights past the check do, less a moment to take hold
    -- (none for a check he missed: the colours still change, he just does not celebrate)
    if (not missed) then
        self.thumbs = math.max(THUMBS_TIME, (section.last_frame - section.check_frame) / SPEED - HOLD_MARGIN)
        self.thumbsTotal = self.thumbs
    end
    if (nextSection == nil and self.gen ~= nil) then
        -- the next zone is still being built: the hold waits for it (AppendZone takes it from here)
        say("EMERALD GET !", 3.0)
        self.waitingZone = true
        return
    end
    if (nextSection == nil) then
        self:LayRunOut(7.0)                     -- the run is over: pipe for him to run on down meanwhile
        if (self.data.timeAttack) then
            self.clockStopped = true
            if (self.uiReady) then TheSpecialStageUI:ShowBanner("CLEAR  " .. FormatClock(self.timeLeft) .. " LEFT", 6.0) end
            self.over = 6.5
        else
            if (self.uiReady) then TheSpecialStageUI:ShowBanner("MARATHON CLEAR !", 4.5) end
            self.over = 5.0
        end
        return
    end
    say("EMERALD GET !", 3.0)       -- (the item's own words, later)
    self.holding = { clock = 0.0, to = nextSection.palette or self.palette }
end

-- The hold's change of colours: the pipe and the sky, at once, SWITCH_AT into it.
function SpecialStage:TickFade(dt)
    local h = self.holding
    if (h == nil) then return end
    h.clock = h.clock + dt
    if (h.clock >= SWITCH_AT) then
        self:SetPalette(h.to)
        self.holding = nil
    end
end

function SpecialStage:EndFade()
    self.holding = nil
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
    if (self.data.timeAttack) then
        TheSpecialStageUI:SetClock(FormatClock(self.timeLeft))            -- the time, where TOTAL was
    else
        TheSpecialStageUI:SetClock(nil)
        TheSpecialStageUI:SetTotal(section.quota)                      -- what this round ASKS for: it does not count down
    end
    -- a time attack's lives, when it has a number of them
    TheSpecialStageUI:SetLives((self.data.timeAttack and (self.lives or 0) > 0) and self.lives or nil)
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
              Explosion = 0.60, Fail = 0.70, ExitStage = 0.60, SpinRev = 0.45, SpinRelease = 0.70 }
-- A sound played from another's asset (none now).
local SOUND_ASSET = {}

-- THERE ARE ONLY 8 VOICES (a GameCube's; the engine gives the PC the same), and the music has one or
-- two. With every sound alike, a burst of rings -- each 0.67 s -- filled the rest, and anything played
-- then was dropped: a checkpoint, the emerald, silent. So each sound has a PRIORITY, and one that
-- matters takes the voice of one that matters less (the engine evicts a lower priority to play a
-- higher; the music is the highest of all, SpecialStageMusic.lua); and the ones that come in bursts
-- play ONE AT A TIME, each cutting the last off, so a burst holds one voice however long it goes on.
local PRIORITY = { Ring = 10, SpinRev = 15, Jump = 20, LoseRings = 30, Explosion = 30, SpinRelease = 40,
                   Checkpoint = 60, GetEmerald = 60, Fail = 60, ExitStage = 60, MenuWarp = 60 }
local ONE_AT_A_TIME = { Ring = true, SpinRev = true, Jump = true }

function SpecialStage:Sound(name, pitch)
    self.sounds = self.sounds or {}
    -- (not remembered as missing: a load that failed once -- short of memory, on a GameCube -- is
    -- tried again the next time, rather than leaving that sound silent for the rest of the run)
    local sound = self.sounds[name] or LoadAsset("SW_" .. (SOUND_ASSET[name] or name))
    self.sounds[name] = sound
    if (sound == nil) then return end
    if (ONE_AT_A_TIME[name]) then Audio.StopSounds(sound) end
    Audio.PlaySound2D(sound, MIX[name] or 0.6, pitch or 1.0, 0.0, false, PRIORITY[name] or 20)
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
        if (self.data.marathon) then
            self:LoadStage("Marathon")                  -- a marathon starts again as a new run
        else
            self:Restart()
        end
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
    self:TickFade(dt)
    if (self.data.marathon) then self:TickMarathonGen() end
    if (self.over >= 0.0) then
        self.over = self.over - dt
        if (self.over < 0.0) then
            if (self.failed and self.data.marathon) then
                self:Finish()                   -- a marathon is one run: a failed check ends it
            elseif (self.failed) then
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
    -- a time attack's clock: down, from the end of START; at 0 the run is over
    if (self.data.timeAttack and not self.clockStopped and self.hold <= 0.0 and self.intro <= 0.0 and self.over < 0.0) then
        self.timeLeft = self.timeLeft - dt
        if (self.timeLeft <= 0.0) then
            self.timeLeft, self.clockStopped = 0.0, true
            self.over = 3.5
            self.failed = true
            self:Sound("Fail")
            if (self.uiReady) then TheSpecialStageUI:ShowBanner("TIME OVER", 3.2) end
        end
    end
    -- steering: round the pipe, and only round it, while his feet are on it
    local want = 0.0
    if (not locked and self.stun <= 0.0 and self.spinDash == nil) then
        if (Input.IsKeyDown(Key.A)) then want = want + 1.0 end
        if (Input.IsKeyDown(Key.D)) then want = want - 1.0 end
        -- A controller (PadInput.lua does its buttons): the stick, and the d-pad as a held key.
        -- The stick reaches full steering at STICK_FULL and is a held key from there on: the
        -- momentum winds up only once he is at (97% of) full steering, and a GameCube stick never
        -- reads 1.0 -- the engine divides by 127 and a real stick tops out near 100, less off the
        -- horizontal, 0.7 or so. Below STICK_FULL it steers in proportion.
        local stick = Input.GetGamepadAxisValue(Gamepad.AxisLX)
        local STICK_DEAD, STICK_FULL = 0.2, 0.55
        local tilt = math.abs(stick)
        if (tilt > STICK_DEAD) then
            local amount = math.min(1.0, (tilt - STICK_DEAD) / (STICK_FULL - STICK_DEAD))
            want = want - ((stick > 0.0) and amount or -amount)
        end
        if (Input.IsGamepadButtonDown(Gamepad.Left)) then want = want + 1.0 end
        if (Input.IsGamepadButtonDown(Gamepad.Right)) then want = want - 1.0 end
        want = math.max(-1.0, math.min(1.0, want))
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
        if (want == 0.0 and self.hold <= 0.0 and self.spinDash == nil and math.abs(self.angle) > FALL_ANGLE) then
            self.cling = self.cling + dt
            if (self.cling >= CLING) then
                self:LeaveSurface(0.0, false)   -- let go up the overhang: he drops off it, on his feet
                self.falling = true
            end
        else
            self.cling = 0.0
        end
    end


    -- THE SPIN DASH: R down on the pipe curls him up and he skids to a stop; A revs; R up launches.
    local grounded = self.height <= 0.0 and not self.falling
    local testHold, testRev = false, false
    if (self.testSpin ~= nil and not locked) then
        -- (the test: 1.4 s held from each 8 s mark, a rev every 0.25 s of it)
        self.testSpinClock = self.testSpinClock + dt
        local into = self.testSpinClock - self.testSpin
        if (into >= 0.0) then
            local t = into % 8.0
            testHold = t < 1.4
            local before = (t - dt) / 0.25
            testRev = testHold and t > 0.3 and math.floor(t / 0.25) ~= math.floor(before)
        end
    end
    local function SpinDown() return SpinHeld() or testHold end
    if (self.spinDash == nil) then
        if (not locked and grounded and self.stun <= 0.0 and SpinDown()) then
            self.spinDash = { rev = 0.0, pulse = 1.0 }
            self.skid = self.boost            -- from whatever speed he had
            self.boost = 1.0
            self:Sound("Jump")
        end
    elseif (locked or not grounded or not SpinDown()) then
        -- let go: off he goes (unless the stage took the controls, or he left the pipe)
        if (not locked and grounded) then
            self.boost = DASH_BASE + DASH_PER_REV * self.spinDash.rev
            self.dashClock = 0.0
            self:Sound("SpinRelease")
        end
        self.spinDash, self.skid = nil, nil
    else
        local s = self.spinDash
        s.rev = s.rev * math.exp(-SPIN_REV_BLEED * dt)
        s.pulse = s.pulse + dt
        if (Input.IsKeyJustDown(Key.Space) or testRev) then
            s.rev = math.min(SPIN_REV_MAX, s.rev + SPIN_REV)
            s.pulse = 0.0
            self:SpinFx(0.0, true)
            self:Sound("SpinRev", 1.0 + 0.05 * s.rev)     -- higher the more it is charged
        end
    end

    -- jumping, and falling
    -- For testing the jump without playing: S2_AUTOJUMP=<frame> jumps there and logs the flight.
    local autoJump = false
    -- A BOUNCE CANNOT BE CUT SHORT: in one, a press on the way up is REMEMBERED and the drop dash
    -- goes at the top (so every bounce gets its full height, however early it was asked for). Out
    -- of a jump it is there at once, as ever. Held until he lands, the next bounce goes all the way.
    local inBounce = self.bounceClock ~= nil
    local rising = inBounce and self.vy > 0.0
    if (self.testJump ~= nil and self.frame >= self.testJump) then autoJump, self.testJump = true, nil end
    if (self.testDive ~= nil and self.height > 0.0 and not self.diving and self.bouncePress == nil and self.fallTime >= self.testDive) then
        autoJump, self.testDive = true, nil
        if (self.testBounces > 0) then self.testBounces, self.testDive = self.testBounces - 1, self.testDiveAt end
    end
    local pressed = not locked and self.spinDash == nil and (Input.IsKeyJustDown(Key.Space) or autoJump)
    if (pressed and inBounce and not self.diving) then
        self.bouncePress = true                 -- remembered: the drop dash goes at the top
    end
    if (pressed and self.height > 0.0 and not self.diving and self.firstPressToTop == nil) then
        -- the first press of this flight: how far from its top, in seconds (either side)
        self.firstPressToTop = math.abs(self.vy) / math.max(1e-3, self.gravity or GRAVITY)
    end
    local diveNow = not locked and self.height > 0.0 and not self.diving and not rising and
                    (pressed or (inBounce and self.bouncePress ~= nil))
    if (pressed and self.height <= 0.0) or diveNow then
        if (self.height <= 0.0) then
            self:LeaveSurface(JUMP, want ~= 0.0)
            self:Sound("Jump")
        else
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
            self.diveClock, self.bounceClock, self.bouncePress = 0.0, nil, nil
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
        if (self.diving) then self.diveClock = (self.diveClock or 0.0) + dt end
        if (self.bounceClock ~= nil) then self.bounceClock = self.bounceClock + dt end
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
            local bounce = self.diving and BOUNCE and not locked
            self.height, self.diving, self.falling = 0.0, false, false
            self.bounceClock = nil
            self.bounces = bounce and (self.bounces or 0) + 1 or 0      -- in a row; a plain landing ends it
            local timed = self.firstPressToTop ~= nil and self.firstPressToTop <= PEAK_WINDOW
            self.firstPressToTop = nil                                  -- the next flight's own
            if (bounce) then
                -- THE BOUNCE: off the pipe where he hit it, his run round it going on as sideways
                -- speed (LeaveSurface), so he bounces along the pipe, not on one spot -- and straight
                -- UP the screen at once, as the drop dash came straight down: a sharp V at the pipe.
                self:LeaveSurface(0.0, true)
                self.falling, self.push = false, 0.0
                self.nx, self.ny = 0.0, 1.0
                -- one step up from the last bounce -- or, the drop dash asked for near the top of
                -- the flight, all the way
                local up = (self.bounces > 1) and (self.bounceLaunch or BOUNCE_FIRST) + BOUNCE_STEP or BOUNCE_FIRST
                if (self.testLog and self.testHold ~= nil) then timed = self.testHold end     -- (a test)
                if (timed) then up = BOUNCE_TOP end
                self.vy = math.min(BOUNCE_TOP, up)
                self.bounceLaunch = self.vy
                self.gravity = GRAVITY * BOUNCE_GRAVITY
                self.bounceClock = 0.0
                self:Sound("Jump")
                if (self.testLog) then print(string.format("BOUNCE %d angle %.1f steer %.1f up %.1f", self.bounces, self.angle, self.steer, self.vy)) end
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
        if (self.spinDash ~= nil) then
            -- skidding into the rev: to a stop, from whatever speed he had
            self.skid = math.max(0.0, (self.skid or 1.0) - dt * math.max(1.0, self.skid or 1.0) / SPIN_SKID)
            speed = speed * self.skid
        else
            speed = speed * self.boost
        end
        self.frame = math.min(self.frame + speed * dt, self.data.frames - 2.0)
    end
    -- a dash's extra speed eases away, back to his own
    self.boost = 1.0 + (self.boost - 1.0) * math.exp(-DASH_EASE * dt)
    if (self.boost < 1.005) then self.boost = 1.0 end
    if (self.dashClock ~= nil) then
        self.dashClock = self.dashClock + dt
        if (self.dashClock > DASH_STRETCH_TIME) then self.dashClock = nil end
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
    local curled = not airborne and (self.spinDash ~= nil or self.boost > DASH_BALL)
    local mesh
    if ((airborne and not self.falling) or curled) then
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
    if (curled) then
        -- the ball on the pipe: its middle a radius off the surface
        place = self:Place(self.frame, self.angle, BALL_RADIUS)
    end
    -- THE TENNIS BALL: how tall the ball is, up the screen (1 round), and how long along the track.
    -- Its width goes the other way, so it keeps its volume, and its bottom stays where it was, so a
    -- squash sits on the pipe.
    local tall, long = 1.0, 1.0
    if (curled and self.spinDash ~= nil) then
        -- revving: squashed down on the pipe, flatter still for a moment at each press
        local t = self.spinDash.pulse
        tall = SPIN_TALL - SPIN_PULSE * math.exp(-SQUASH_DAMP * t) * math.cos(TWO_PI * SQUASH_HZ * t)
    elseif (curled and self.dashClock ~= nil) then
        -- launched: stretched out along the track, easing back round
        local t = self.dashClock
        long = 1.0 + DASH_LONG * math.exp(-6.0 * t) * math.cos(TWO_PI * 2.0 * t)
    end
    if (airborne and not self.falling) then
        if (self.diving) then
            tall = 1.0 + DROP_STRETCH * math.min(1.0, (self.diveClock or 0.0) / 0.08)
        elseif (self.bounceClock ~= nil and self.bounceClock < SQUASH_TIME) then
            local t = self.bounceClock
            tall = 1.0 - SQUASH * math.exp(-SQUASH_DAMP * t) * math.cos(TWO_PI * SQUASH_HZ * t)
        end
    end
    if (tall ~= 1.0) then
        local upHere = inward
        if (not curled) then _, _, upHere = self:TrackAt(self.frame) end
        place = Add(place, Scale(upHere, BALL_RADIUS * (tall - 1.0)))
    end
    self.player:SetWorldPosition(ToVec(place))
    if (tall ~= 1.0 or long ~= 1.0) then
        -- Squashed along the screen's up (or, on the pipe, the pipe's up where he is) and stretched
        -- along the track: the ball's own axes turned to them, and no roll meanwhile (a roll would
        -- carry the squash round with it; the ball is a plain sphere, so it is not missed).
        local _, fwdHere, upHere = self:TrackAt(self.frame)
        if (curled) then fwdHere, upHere = fwd, inward end
        self.player:SetWorldRotationQuat(FacingQuat(fwdHere, upHere))
        local side = 1.0 / math.sqrt(tall * long)
        self.player:SetScale(Vec(long, tall, side))
        self.squashed = true
    elseif (self.squashed) then
        self.player:SetScale(Vec(1.0, 1.0, 1.0))
        self.squashed = false
    end
    if (tall ~= 1.0 or long ~= 1.0) then
        -- (turned above)
    elseif (curled) then
        -- rolling along the pipe, as fast as he is going
        self.dashRoll = self.dashRoll + (BALL_ROLLS and (SPEED * self.boost * (self.data.step or 1.0) / BALL_RADIUS) * dt or 0.0)
        local side = Cross(fwd, inward)
        local c, sn = math.cos(self.dashRoll), math.sin(self.dashRoll)
        local function Turn(v)
            return Add(Add(Scale(v, c), Scale(Cross(side, v), sn)), Scale(side, Dot(side, v) * (1.0 - c)))
        end
        self.player:SetWorldRotationQuat(FacingQuat(Turn(fwd), Turn(inward)))
    elseif (airborne and not self.falling) then
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
        -- measured against THIS thumbs-up's length: against the ordinary one, a marathon's longer
        -- hold came out as a negative time, and the easing threw the camera about every frame
        local t = (self.thumbsTotal or THUMBS_TIME) - self.thumbs
        if (t < ORBIT_TIME) then
            swing = t / ORBIT_TIME
        elseif (self.thumbs < ORBIT_TIME) then
            swing = self.thumbs / ORBIT_TIME
        else
            swing = 1.0
        end
        swing = math.max(0.0, math.min(1.0, swing))
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
    self.camLook = look                 -- (the spin dash's shards turn to their flight on the screen)
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
    self:SpinFx(dt, false)
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
