-- MarathonGen.lua
-- THE MARATHON, MADE IN THE GAME: a zone built from nothing but (the run's seed, the zone's
-- number), while the zone before it is being played -- so every run is new, and no zone is ever
-- seen twice. It is gen_stage.py's marathon, ported step for step (build_part, plan, steer, fill,
-- top_up, trim), working from MarathonKit.lua (native/export_marathon_kit.py): the track pieces'
-- centre lines, every card a section can be dealt with how many rings a line can take from it,
-- and the design curves.
--
--     MarathonGen.BuildZone(seed, zone)   -> a zone table, as MarathonZone_<z>_<seed>.lua would be:
--                                            { zone, frames, pieces, path, sections }, in the
--                                            zone's own space (the engine's axes)
--
-- It can run inside a coroutine and then yields every so often, so building a zone is spread over
-- many frames instead of stopping one (SpecialStage.lua runs it a slice a frame).
--
-- THE GUARANTEE, as gen_stage.py's: a section's modules' takeable rings, added up, reach what its
-- check asks x its forgiveness, and ask / TAKEABLE_SHARE x SAFETY -- the takeable sum runs a little
-- over what one line through the whole section takes (neighbours, bombs), and SAFETY covers that.
-- The whole-section solver is too slow for a game; native/check_marathon_gen.py runs it on zones
-- the game has built and is what SAFETY was set from.

MarathonGen = {}

Script.Require("MarathonKit")
local K = MarathonKit
MarathonGen.SAFETY = 1.08

-- ------------------------------------------------------------------ randomness
-- The engine's Lua is built with 32-bit integers and 32-bit floats (LUA_32BITS), on the PC and the
-- GameCube alike, so this is all 32-bit: the seed, the zone and the attempt mixed by a 32-bit hash,
-- then xorshift32. (A 64-bit generator was tried first and, cut to 32 bits, gave every seed the
-- same zones.)
local Rng = {}
Rng.__index = Rng

local function Mix(h)
    h = h ~ (h >> 16)
    h = h * 0x7FEB352D
    h = h ~ (h >> 15)
    h = h * 0x846CA68B
    h = h ~ (h >> 16)
    return h
end

local function NewRng(a, b, c)
    local h = 0x811C9DC5
    for _, v in ipairs({ a or 0, b or 0, c or 0 }) do
        h = Mix((h ~ math.floor(v)) * 16777619)
    end
    if (h == 0) then h = 1 end
    return setmetatable({ s = h }, Rng)
end

function Rng:next()
    local x = self.s
    x = x ~ (x << 13)
    x = x ~ (x >> 17)
    x = x ~ (x << 5)
    self.s = x
    return x & 0xFFFFFF                             -- 24 bits: exact in a 32-bit float
end

function Rng:random() return self:next() / 16777216.0 end
function Rng:randrange(n) return math.floor(self:random() * n) end            -- 0 .. n-1
function Rng:choice(t) return t[self:randrange(#t) + 1] end
function Rng:uniform(a, b) return a + (b - a) * self:random() end
function Rng:shuffle(t)
    for i = #t, 2, -1 do
        local j = self:randrange(i) + 1
        t[i], t[j] = t[j], t[i]
    end
end

-- ------------------------------------------------------------------ yielding
local ops = 0
MarathonGen.BREATH = 400            -- work between yields (a slower machine sets it lower)
local function Breathe(weight)
    ops = ops + (weight or 1)
    if (ops >= MarathonGen.BREATH) then
        ops = 0
        if (coroutine.isyieldable()) then coroutine.yield() end
    end
end

-- ------------------------------------------------------------------ small maths (Blender's space)
local function V(x, y, z) return { x, y, z } end
local function Sub(a, b) return { a[1] - b[1], a[2] - b[2], a[3] - b[3] } end
local function AddV(a, b) return { a[1] + b[1], a[2] + b[2], a[3] + b[3] } end
local function Mul(a, k) return { a[1] * k, a[2] * k, a[3] * k } end
local function Len(a) return math.sqrt(a[1] * a[1] + a[2] * a[2] + a[3] * a[3]) end
local function Norm(a)
    local l = Len(a)
    if (l < 1e-9) then return { 1, 0, 0 } end
    return { a[1] / l, a[2] / l, a[3] / l }
end
local function CrossV(a, b)
    return { a[2] * b[3] - a[3] * b[2], a[3] * b[1] - a[1] * b[3], a[1] * b[2] - a[2] * b[1] }
end

-- A rigid frame: axes x, y, z (columns) and a position p.
local function Identity() return { x = { 1, 0, 0 }, y = { 0, 1, 0 }, z = { 0, 0, 1 }, p = { 0, 0, 0 } } end
local function Rot(f, v) return AddV(AddV(Mul(f.x, v[1]), Mul(f.y, v[2])), Mul(f.z, v[3])) end
local function Apply(f, v) return AddV(f.p, Rot(f, v)) end
local function Compose(a, b) return { x = Rot(a, b.x), y = Rot(a, b.y), z = Rot(a, b.z), p = Apply(a, b.p) } end

-- (x, y, z) in Blender's space -> the engine's (x, z, -y), as export_to_octave.to_octave
local function ToOctave(v) return { v[1], v[3], -v[2] } end

local function QuatOfFrame(f)
    local m00, m01, m02 = f.x[1], f.y[1], f.z[1]
    local m10, m11, m12 = f.x[2], f.y[2], f.z[2]
    local m20, m21, m22 = f.x[3], f.y[3], f.z[3]
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
    return { qx, qz, -qy, qw }         -- in the engine's axes, as the exporter writes piece quats
end

-- ------------------------------------------------------------------ the pieces (gen_rings_on_pieces.PiecePath)
local PIECES = {}
for name, raw in pairs(K.pieces) do
    local pts = raw.pts
    local dist = { 0.0 }
    for i = 2, #pts do dist[i] = dist[i - 1] + Len(Sub(pts[i], pts[i - 1])) end
    local coarse = {}
    for i = 1, #pts, 12 do coarse[#coarse + 1] = pts[i] end
    PIECES[name] = { pts = pts, dist = dist, length = dist[#dist], coarse = coarse }
end

-- The frame at distance s along a piece: X along the track, Z up out of the floor, no bank.
local function PieceFrame(piece, s)
    local pts, dist, n = piece.pts, piece.dist, #piece.pts
    s = math.max(0.0, math.min(s, piece.length))
    local i = 1
    local lo, hi = 1, n
    while (lo <= hi) do                         -- the last point at or before s
        local mid = (lo + hi) // 2
        if (dist[mid] <= s) then i = mid; lo = mid + 1 else hi = mid - 1 end
    end
    i = math.min(i, n - 1)
    local seg = dist[i + 1] - dist[i]
    local t = (seg > 0) and (s - dist[i]) / seg or 0.0
    local pos = AddV(pts[i], Mul(Sub(pts[i + 1], pts[i]), t))
    local a, b = pts[math.max(i - 1, 1)], pts[math.min(i + 2, n)]
    local x = Norm(Sub(b, a))
    local z = Norm(Sub({ 0, 0, 1 }, Mul(x, x[3])))
    local y = CrossV(z, x)
    return { x = x, y = y, z = z, p = pos }
end

local function FramesOf(name) return PIECES[name].length / K.step end

-- ------------------------------------------------------------------ the design (gen_stage.section_design)
local function RoundHalfEven(x)                 -- Python's round
    local f = math.floor(x)
    local d = x - f
    if (d > 0.5) then return f + 1 end
    if (d < 0.5) then return f end
    return (f % 2 == 0) and f or f + 1
end

local function Between(table_, d)
    local lo = math.max(1, math.min(6, math.floor(d)))
    local t = math.max(0.0, math.min(1.0, d - lo))
    return table_[lo] * (1.0 - t) + table_[lo + 1] * t
end

local D = K.design
local THIRDS, FORGIVE, RATE = {}, {}, {}
for k = 1, 7 do
    THIRDS[k] = D.quota[k][3] / 3.0
    FORGIVE[k] = D.forgiveness[k]
    RATE[k] = D.ring_rate[k]
end

-- The marathon's setup (GameOptions.lua): how hard the first zone is, how much harder each
-- section after gets, and a scale on the forgiveness -- the rings laid out over what a check asks.
-- The guarantee does not move: a section still lays at least what its check needs (BuildZone).
local CLIMB = { 0.0, 0.25, 0.5, 0.75 }              -- difficulty a section: none, slow, normal, fast
local LENIENCY = { 0.85, 1.0, 1.2 }                 -- tight, normal, generous

local function Setup()
    local m = GameOptions ~= nil and GameOptions.marathon or nil
    if (m == nil) then return D.start, D.ramp, 1.0 end
    return m.start or D.start, CLIMB[m.climb] or D.ramp, LENIENCY[m.leniency] or 1.0
end

local function SectionDesign(s)                 -- s counts from 0 across the run
    local start, ramp, lenient = Setup()
    local d = start + ramp * s
    local zone = s // D.sections_per_zone
    local over = math.max(0.0, d - 7.0)
    local asks = Between(THIRDS, d) + D.ask_step * over
    local band = math.max(1, math.min(7, RoundHalfEven(d)))
    local flavour = (d <= 7.0) and band or D.flavours[(zone % #D.flavours) + 1]
    local forgiveness = math.floor(math.max(D.forgiveness_floor, (Between(FORGIVE, d) - 0.015 * over) * lenient) * 1000 + 0.5) / 1000
    local out = {
        difficulty = d,
        asks = RoundHalfEven(asks / 5.0) * 5,
        forgiveness = forgiveness,
        ring_rate = math.min(D.ring_rate_ceiling, Between(RATE, d) + 0.01 * over),
        flavour = flavour,
        rules = K.rules[band],
        leads_to = ((s + 1) % D.sections_per_zone == 0) and "PALETTE SHIFT" or "on",
    }
    out.target = math.ceil(out.asks * out.forgiveness)
    out.best_needed = math.ceil(out.asks / K.share)
    local fl = K.flavours[flavour]
    local bombShare = 1.0 - fl.rings / (fl.rings + fl.bombs)
    out.per_frame = out.ring_rate * (1.0 - 0.5 * bombShare)
    return out
end

-- ------------------------------------------------------------------ the track (gen_random_level.plan, gen_stage)
local function Plan(rules, n, rng)
    local hills = math.max(1, RoundHalfEven(rules.hill * n))
    local corners = RoundHalfEven(rules.turn * n)
    local events, left = {}, corners
    while (left > 0) do
        local first = rng:choice({ "CornerLeft", "CornerRight" })
        if (left >= 2 and rules.chain >= 2 and rng:random() < rules.snake) then
            local other = (first == "CornerLeft") and "CornerRight" or "CornerLeft"
            events[#events + 1] = { first, other }
            left = left - 2
        else
            events[#events + 1] = { first }
            left = left - 1
        end
    end
    for _ = 1, hills do events[#events + 1] = { (rng:random() < rules.rise) and "Rise" or "Drop" } end
    rng:shuffle(events)
    local gap = {}
    for i = 1, #events + 1 do gap[i] = 0 end
    gap[1] = 2
    local chain = 0
    for i, ev in ipairs(events) do
        local isCorner = ev[1]:sub(1, 6) == "Corner"
        if (isCorner and chain + #ev > rules.chain) then
            gap[i] = math.max(gap[i], 1)
            chain = 0
        end
        chain = isCorner and chain + #ev or 0
        if (not isCorner) then gap[i + 1] = math.max(gap[i + 1], rules.rest) end
    end
    gap[#gap] = math.max(gap[#gap], 1)
    local used = 0
    for _, ev in ipairs(events) do used = used + #ev end
    for _, g in ipairs(gap) do used = used + g end
    for _ = 1, math.max(0, n - used) do
        local i = rng:randrange(#gap) + 1
        gap[i] = gap[i] + 1
    end
    local names = {}
    for i, ev in ipairs(events) do
        for _ = 1, gap[i] do names[#names + 1] = "Straight" end
        for _, p in ipairs(ev) do names[#names + 1] = p end
    end
    for _ = 1, gap[#gap] do names[#names + 1] = "Straight" end
    return names
end

local function PlanSection(rules, rng, needFrames, extra)
    local n = rules.pieces + extra
    while (true) do
        local names = Plan(rules, n, rng)
        local frames = 0.0
        for _, p in ipairs(names) do frames = frames + FramesOf(p) end
        if (frames >= needFrames) then return names end
        n = n + 2
    end
end

local function EvenCorners(names)
    local last, count = nil, 0
    for i, n in ipairs(names) do
        if (n:sub(1, 6) == "Corner") then count = count + 1; last = i end
    end
    if (count % 2 == 1) then names[last] = "Straight" end
    return names
end

local function Steer(names, rng)
    local heading = 0
    for i, n in ipairs(names) do
        if (n:sub(1, 6) == "Corner") then
            local turns = {}
            for _, t in ipairs({ -1, 1 }) do
                if (math.abs(heading + t) <= 1) then turns[#turns + 1] = t end
            end
            local turn = rng:choice(turns)
            heading = heading + turn
            names[i] = (turn > 0) and "CornerLeft" or "CornerRight"
        end
    end
    return names
end

-- Lay the pieces end to end; a piece that would run into the track laid before its recent
-- neighbours is swapped for the nearest thing that fits (gen_random_level.generate).
local TRACK = K.track
-- The points laid so far, in a grid of CLEAR_FLAT-wide cells: a new piece need only look in the
-- cells round each of its points, not at every point of every piece laid before it.
local function Cell(p) return math.floor(p[1] / TRACK.clear_flat), math.floor(p[2] / TRACK.clear_flat) end

local function Collides(world, grid, count)
    local upto = count - TRACK.recent                -- the last few pieces are neighbours
    local r2 = TRACK.clear_flat * TRACK.clear_flat
    for _, a in ipairs(world) do
        local cx, cy = Cell(a)
        for dx = -1, 1 do
            local column = grid[cx + dx]
            if (column ~= nil) then
                for dy = -1, 1 do
                    local cell = column[cy + dy]
                    if (cell ~= nil) then
                        for _, b in ipairs(cell) do
                            if (b[4] <= upto and math.abs(a[3] - b[3]) < TRACK.clear_height) then
                                local ex, ey = a[1] - b[1], a[2] - b[2]
                                if (ex * ex + ey * ey < r2) then return true end
                            end
                        end
                    end
                end
            end
        end
    end
    Breathe(#world)
    return false
end

local function Lay(plan)
    local frame, grid, names, origins = Identity(), {}, {}, {}
    for _, want in ipairs(plan) do
        local options
        if (want:sub(1, 6) == "Corner") then
            options = { want, (want == "CornerLeft") and "CornerRight" or "CornerLeft", "Drop", "Straight" }
        elseif (want == "Straight") then
            options = { want, "Drop", "CornerLeft", "CornerRight" }
        else
            options = { want, "Drop", "Straight", "CornerLeft", "CornerRight" }
        end
        local placed = false
        local tried = {}
        for _, name in ipairs(options) do
            if (not tried[name]) then
                tried[name] = true
                local piece = PIECES[name]
                local world = {}
                for i, p in ipairs(piece.coarse) do world[i] = Apply(frame, p) end
                if (not Collides(world, grid, #names + 1)) then
                    names[#names + 1] = name
                    origins[#origins + 1] = frame
                    for _, p in ipairs(world) do
                        local cx, cy = Cell(p)
                        grid[cx] = grid[cx] or {}
                        grid[cx][cy] = grid[cx][cy] or {}
                        local cell = grid[cx][cy]
                        cell[#cell + 1] = { p[1], p[2], p[3], #names }
                    end
                    frame = Compose(frame, PieceFrame(piece, piece.length))
                    placed = true
                    break
                end
            end
        end
        if (not placed) then return names, origins, false end
    end
    return names, origins, true
end

-- ------------------------------------------------------------------ the rings and bombs (gen_stage.fill, top_up, trim)
local MODULES = K.modules

local function Expand(cards)
    local out = {}
    for _, c in ipairs(cards) do
        for _ = 1, c.n or 1 do out[#out + 1] = c end
    end
    return out
end

-- A card dealt: (module, angle it goes at, mirrored, takeable rings), the 50/50 mirror thrown here.
local function Deal(card, rng)
    if (rng:random() < 0.5) then
        return { mod = card.mod, at = -card.at, mirror = true, t = card.tm }
    end
    return { mod = card.mod, at = card.at, mirror = false, t = card.t }
end

local function TakeableIn(laid)
    local sum = 0
    for _, x in ipairs(laid) do sum = sum + x.t end
    return sum
end

local function Fill(window, piecesAt, flavour, rate, rng, decks)
    local f0, f1 = window[1], window[2]
    local fl = K.flavours[flavour]
    local everything = {}
    for _, on in ipairs({ "corner", "slope", "straight" }) do
        for _, c in ipairs(fl.decks[on] or {}) do everything[#everything + 1] = c end
    end
    local function DealFrom(on)
        local key = flavour .. "/" .. on
        local deck = decks[key]
        if (deck == nil or #deck == 0) then
            local src = fl.decks[on]
            if (src == nil or #src == 0) then src = everything end
            local cards = Expand(src)
            rng:shuffle(cards)
            local loud, quiet = {}, {}
            for _, c in ipairs(cards) do
                if (c.bomb) then loud[#loud + 1] = c else quiet[#quiet + 1] = c end
            end
            local share = (#loud > 0) and (#cards / #loud) or 0
            for i, c in ipairs(loud) do
                local at = math.min(#quiet, math.floor((i - 1) * share + rng:random() * share))
                table.insert(quiet, at + 1, c)
            end
            deck = {}
            for i = #quiet, 1, -1 do deck[#deck + 1] = quiet[i] end         -- dealt from the end
            decks[key] = deck
        end
        return table.remove(deck)
    end
    -- The frames only ever go forward here, so the piece under one, and the corners after it,
    -- are followed along the list rather than searched for from its start each time.
    local under = 1
    local function OnAt(frame)
        while (under < #piecesAt and piecesAt[under][2] <= frame) do under = under + 1 end
        local p = piecesAt[under]
        if (p ~= nil and p[1] <= frame and frame < p[2]) then return K.on[p[3]] end
        return "straight"
    end
    local function CornerAhead(frame)
        for i = under, #piecesAt do
            local p = piecesAt[i]
            local ahead = p[1] - frame
            if (ahead > TRACK.before_corner) then return false end
            if (ahead > 0 and p[3]:sub(1, 6) == "Corner") then return true end
        end
        return false
    end

    local laid, seen, put, bombs = {}, {}, {}, 0
    local bombsPerRing = fl.bombs / fl.rings
    local meanDensity, nd = 0.0, 0
    for _, v in pairs(fl.density) do meanDensity = meanDensity + v; nd = nd + 1 end
    meanDensity = meanDensity / nd
    local function PutTotal()
        local s = 0
        for _, v in pairs(put) do s = s + v end
        return s
    end
    local grid = TRACK.grid
    local f = f0
    while (f < f1) do
        Breathe(4)
        local on = OnAt(f)
        seen[on] = (seen[on] or 0) + grid
        local lean = (fl.density[on] or meanDensity) / meanDensity
        if (CornerAhead(f) or (put[on] or 0) / seen[on] >= rate * lean) then
            f = f + grid
        else
            local dealt, mod
            local ok = false
            for _ = 1, 12 do
                local card = DealFrom(on)
                dealt = Deal(card, rng)
                mod = MODULES[dealt.mod]
                if (mod.bombs == 0 or bombs + mod.bombs <= 8 + bombsPerRing * PutTotal()) then ok = true; break end
            end
            if (not ok or f + mod.len > f1) then
                f = f + grid
            else
                bombs = bombs + mod.bombs
                dealt.first = f
                laid[#laid + 1] = dealt
                put[on] = (put[on] or 0) + mod.rings
                local step = mod.len + rng:choice({ 2, 4, 4, 6 })
                seen[on] = seen[on] + step - grid
                f = f + math.ceil(step / grid) * grid
            end
        end
    end
    return laid
end

local function TopUp(laid, window, flavour, target, rng)
    local f0, f1 = window[1], window[2]
    local ringonly = Expand(K.flavours[flavour].ringonly)
    for _ = 1, 200 do
        if (TakeableIn(laid) >= target or #ringonly == 0) then break end
        local taken = {}
        for _, x in ipairs(laid) do taken[#taken + 1] = { x.first, x.first + MODULES[x.mod].len } end
        table.sort(taken, function(a, b) return a[1] < b[1] or (a[1] == b[1] and a[2] < b[2]) end)
        taken[#taken + 1] = { f1, f1 }
        local best, cursor = nil, f0
        for _, ab in ipairs(taken) do
            if (ab[1] - cursor >= 8) then
                local g = { ab[1] - cursor, cursor }
                if (best == nil or g[1] > best[1] or (g[1] == best[1] and g[2] > best[2])) then best = g end
            end
            cursor = math.max(cursor, ab[2])
        end
        if (best == nil) then break end
        local size, start = best[1], best[2]
        local dealt = Deal(rng:choice(ringonly), rng)
        if (MODULES[dealt.mod].len + 4 > size) then
            local small = K.cluster_small
            local at = rng:choice({ -48, 0, 48 })
            dealt = { mod = small.mod, at = at, mirror = false, t = small.t[at] }
            if (MODULES[dealt.mod].len + 4 > size) then break end
        end
        dealt.first = start + 2 + ((size - MODULES[dealt.mod].len - 4) // 2) // 2 * 2
        laid[#laid + 1] = dealt
    end
    return laid
end

local function Trim(laid, target, rng)
    while (true) do
        local spare = TakeableIn(laid) - target
        local loose = {}
        for i, x in ipairs(laid) do
            local mod = MODULES[x.mod]
            if (mod.bombs == 0 and x.t <= spare) then loose[#loose + 1] = i end
        end
        if (#loose == 0) then return laid end
        table.remove(laid, rng:choice(loose))
    end
end

local function Signed(a) return ((a + 128) % 256) - 128 end

-- ------------------------------------------------------------------ a zone (gen_stage.build_part)
function MarathonGen.BuildZone(seed, zone)
    local spz = D.sections_per_zone
    local first = (zone == 1)
    local part = {}
    for k = 1, spz do part[k] = SectionDesign((zone - 1) * spz + (k - 1)) end
    local extra, boost = {}, {}
    for k = 1, spz do extra[k], boost[k] = 0, 0 end
    local lead = first and TRACK.lead_in or TRACK.zone_lead_in

    for attempt = 1, 60 do
        local rng = NewRng(seed, zone, attempt)
        local names, cuts, zones = {}, {}, {}
        if (first) then
            for _ = 1, TRACK.intro_straights do names[#names + 1] = "Straight" end
        end
        for k, d in ipairs(part) do
            local room = rng:uniform(D.room[1], D.room[2])
            local goal = math.max(d.target, math.ceil(d.best_needed * MarathonGen.SAFETY)) + boost[k]
            local need = goal / d.per_frame * room + ((k == 1) and lead or 0)
            for _, p in ipairs(PlanSection(d.rules, rng, need, extra[k])) do names[#names + 1] = p end
            local runUp, plays
            if (d.leads_to == "PALETTE SHIFT") then
                runUp, plays = TRACK.emerald_run_up, TRACK.hold_plays
            else
                runUp, plays = TRACK.check_run_up, TRACK.check_plays
            end
            zones[#zones + 1] = { #names, #names + runUp }        -- (0-based piece indices, as Python's)
            for _ = 1, runUp + plays do names[#names + 1] = "Straight" end
            cuts[#cuts + 1] = #names
        end
        names = Steer(EvenCorners(names), rng)
        local laidNames, origins, ok = Lay(names)
        if (ok) then
            -- where each piece sits, in frames
            local piecesAt, f = {}, 0.0
            for i, n in ipairs(laidNames) do
                piecesAt[i] = { f, f + FramesOf(n), n }
                f = f + FramesOf(n)
            end
            local starts, ends, zoneFirst, checkAt = {}, {}, {}, {}
            for k = 1, spz do
                ends[k] = piecesAt[cuts[k]][2]
                starts[k] = (k == 1) and 0.0 or ends[k - 1]
                zoneFirst[k] = piecesAt[zones[k][1] + 1][1]
                checkAt[k] = piecesAt[zones[k][2] + 1][1] + TRACK.arch_frame
            end
            local sections, short, decks = {}, nil, {}
            for k, d in ipairs(part) do
                local window = { math.ceil(starts[k]) + ((k == 1) and lead or 0), math.floor(zoneFirst[k]) }
                local goal = math.max(d.target, math.ceil(d.best_needed * MarathonGen.SAFETY)) + boost[k]
                local laid = Fill(window, piecesAt, d.flavour, d.ring_rate, rng, decks)
                laid = Trim(TopUp(laid, window, d.flavour, goal, rng), goal, rng)
                sections[k] = laid
                if (TakeableIn(laid) < goal) then
                    short = short or k
                    boost[k] = boost[k] + 2
                    extra[k] = extra[k] + 2
                end
            end
            if (short == nil) then
                local out = MarathonGen.Write(zone, seed, part, laidNames, origins, piecesAt, sections,
                                              starts, ends, checkAt)
                out.tries = attempt
                return out
            end
        end
    end
    return nil
end

-- The zone as the stage reads it: the pieces, the centre line frame by frame, and the sections.
function MarathonGen.Write(zone, seed, part, names, origins, piecesAt, sections, starts, ends, checkAt)
    local out = { zone = zone, seed = seed, pieces = {}, path = {}, sections = {} }
    local length = 0.0
    for i, n in ipairs(names) do
        local o = origins[i]
        out.pieces[i] = { mesh = "SM_Piece_" .. n .. "_P", gloss = "SM_Piece_" .. n .. "_Gloss_P",
                          pos = ToOctave(o.p), quat = QuatOfFrame(o), first_frame = piecesAt[i][1],
                          last_frame = piecesAt[i][2] }
        length = length + PIECES[n].length
    end
    local frames = math.floor(length / K.step) + 1
    out.frames = frames
    -- the centre line, one sample a frame, walking along the pieces
    local pi, start = 1, 0.0
    for f = 0, frames do
        local s = math.min(f * K.step, length)
        while (pi < #names and s > start + PIECES[names[pi]].length) do
            start = start + PIECES[names[pi]].length
            pi = pi + 1
        end
        local fr = Compose(origins[pi], PieceFrame(PIECES[names[pi]], s - start))
        local p, x, z = ToOctave(fr.p), ToOctave(fr.x), ToOctave(fr.z)
        out.path[f + 1] = { p[1], p[2], p[3], x[1], x[2], x[3], z[1], z[2], z[3] }
        if (f % 64 == 0) then Breathe(64) end
    end
    for k, d in ipairs(part) do
        local objects, rings = {}, 0
        for _, x in ipairs(sections[k]) do
            local mod = MODULES[x.mod]
            local o = mod.objs
            for j = 1, #o, 3 do
                local a = x.mirror and -o[j + 1] or o[j + 1]
                objects[#objects + 1] = { x.first + o[j], Signed(a + x.at), o[j + 2] }
                if (o[j + 2] == 0) then rings = rings + 1 end
            end
        end
        table.sort(objects, function(a, b) return a[1] < b[1] or (a[1] == b[1] and a[2] < b[2]) end)
        out.sections[k] = { first_frame = starts[k], check_frame = checkAt[k], last_frame = ends[k],
                            asks = d.asks, rings = rings, leads_to = d.leads_to, difficulty = d.difficulty,
                            objects = objects, takeable = TakeableIn(sections[k]) }
    end
    return out
end

-- For native/check_marathon_gen.py: a zone's sections written out as JSON, to be solved.
function MarathonGen.Dump(zone, path)
    if (io == nil or io.open == nil) then return false end
    local f = io.open(path, "w")
    if (f == nil) then return false end
    local parts = {}
    for _, sec in ipairs(zone.sections) do
        local objs = {}
        for i, o in ipairs(sec.objects) do objs[i] = string.format("[%d,%d,%d]", o[1], o[2], o[3]) end
        parts[#parts + 1] = string.format(
            '{"first_frame":%.4f,"check_frame":%.4f,"last_frame":%.4f,"asks":%d,"takeable":%d,"difficulty":%.2f,"leads_to":"%s","objects":[%s]}',
            sec.first_frame, sec.check_frame, sec.last_frame, sec.asks, sec.takeable, sec.difficulty,
            sec.leads_to, table.concat(objs, ","))
    end
    f:write(string.format('{"zone":%d,"seed":%d,"frames":%d,"sections":[%s]}', zone.zone, zone.seed, zone.frames,
                          table.concat(parts, ",")))
    f:close()
    return true
end
