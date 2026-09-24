-- GameOptions.lua
-- The player's settings, changed from OPTIONS on the title menu and from the marathon's and the time
-- attack's setups (all OptionsPrompt.lua), and kept with the save: letters after the seven emeralds
-- in StageSelect.lua's save text, so a save made before there were settings still reads (as the
-- defaults).
--
--     GameOptions.muteStageMusic       the stages' and the marathon's music is not played
--                                      (SpecialStageMusic.lua); the menus' is
--     GameOptions.marathon.rounds      zones in a run, 1-20; 0 is endless (SpecialStage.lua)
--     GameOptions.marathon.start       how hard its first zone is, as stage 1-7 (MarathonGen.lua)
--     GameOptions.marathon.climb       how fast it gets harder: 1 none, 2 slow, 3 normal, 4 fast
--     GameOptions.marathon.leniency    spare rings: 1 tight, 2 normal, 3 generous
--     GameOptions.timeAttack.*         the same run against the clock: rounds, start and climb as
--                                      above, and
--     GameOptions.timeAttack.lives     hits he can take with no rings before the run ends: 1, 3, 5;
--                                      0 is never (SpecialStage.lua's Collide)
--     GameOptions.timeAttack.time      the clock's start, in seconds; it counts down, each check
--                                      passed puts time back, and at 0 the run is over
--
--     GameOptions.run                  which of the two the next run is: "marathon" or "timeAttack"
--                                      (set by the menu as it starts one); GameOptions.Run() is its
--                                      settings

local DEFAULT_MARATHON = { rounds = 7, start = 2, climb = 3, leniency = 2 }
local DEFAULT_TIME_ATTACK = { rounds = 7, start = 2, climb = 3, leniency = 2, lives = 3, time = 60 }

GameOptions = GameOptions or { muteStageMusic = false, touched = false, marathon = {}, timeAttack = {} }
GameOptions.timeAttack = GameOptions.timeAttack or {}
GameOptions.run = GameOptions.run or "marathon"
for k, v in pairs(DEFAULT_MARATHON) do
    if (GameOptions.marathon[k] == nil) then GameOptions.marathon[k] = v end
end
for k, v in pairs(DEFAULT_TIME_ATTACK) do
    if (GameOptions.timeAttack[k] == nil) then GameOptions.timeAttack[k] = v end
end

-- The settings of the run being played (or about to be).
function GameOptions.Run()
    return GameOptions[GameOptions.run] or GameOptions.marathon
end

-- What each setting can be, in order, and how it reads on the screen.
GameOptions.CHOICES = {
    rounds = { values = { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 0 },
               show = function(v) return (v == 0) and "ENDLESS" or tostring(v) end },
    start = { values = { 1, 2, 3, 4, 5, 6, 7 }, show = tostring },
    climb = { values = { 1, 2, 3, 4 }, show = function(v) return ({ "NONE", "SLOW", "NORMAL", "FAST" })[v] end },
    leniency = { values = { 1, 2, 3 }, show = function(v) return ({ "TIGHT", "NORMAL", "GENEROUS" })[v] end },
    lives = { values = { 1, 3, 5, 0 }, show = function(v) return (v == 0) and "INFINITE" or tostring(v) end },
    time = { values = { 30, 60, 90, 120, 180 },
             show = function(v) return string.format("%d:%02d", v // 60, v % 60) end },
}

-- A time's place in CHOICES.time (1 if it is not one of them).
function TimeIndex(v)
    for i, t in ipairs(GameOptions.CHOICES.time.values) do
        if (t == v) then return i end
    end
    return 1
end

-- The letters after the emeralds: mute (M or -), then the marathon's rounds (a letter: A is
-- endless, B one round, ...), start, climb and leniency (a digit each), a spare digit (the
-- marathon's lives once; it has none now), then the time attack's rounds (a letter), start, climb,
-- lives and time (a digit: its place in CHOICES.time).

function GameOptions.Encode()
    local m, t = GameOptions.marathon, GameOptions.timeAttack
    return (GameOptions.muteStageMusic and "M" or "-") .. string.char(65 + m.rounds)
           .. tostring(m.start) .. tostring(m.climb) .. tostring(m.leniency) .. "0"
           .. string.char(65 + t.rounds) .. tostring(t.start) .. tostring(t.climb) .. tostring(t.lives)
           .. tostring(TimeIndex(t.time))
end

-- From a save's text. Settings changed this session and not saved yet stay as the player set them
-- (the menus read the save again every time they are built, on the GameCube); LOAD clears
-- `touched` first, so a save loaded on purpose does bring its settings.
function GameOptions.Decode(text)
    if (GameOptions.touched) then return end
    text = text or ""
    GameOptions.muteStageMusic = (text:sub(8, 8) == "M")
    local m, t = GameOptions.marathon, GameOptions.timeAttack
    for k, v in pairs(DEFAULT_MARATHON) do m[k] = v end
    for k, v in pairs(DEFAULT_TIME_ATTACK) do t[k] = v end
    local function Rounds(at, into)
        if (#text >= at) then
            local r = text:byte(at) - 65
            if (r >= 0 and r <= 20) then into.rounds = r end
        end
    end
    local function Digit(at, lo, hi, into, key)
        local n = tonumber(text:sub(at, at))
        if (n ~= nil and n >= lo and n <= hi) then into[key] = n end
    end
    Rounds(9, m)
    Digit(10, 1, 7, m, "start")
    Digit(11, 1, 4, m, "climb")
    Digit(12, 1, 3, m, "leniency")
    Rounds(14, t)
    Digit(15, 1, 7, t, "start")
    Digit(16, 1, 4, t, "climb")
    Digit(17, 0, 5, t, "lives")
    local times = GameOptions.CHOICES.time.values
    local ti = tonumber(text:sub(18, 18))
    if (ti ~= nil and times[ti] ~= nil) then t.time = times[ti] end
end
