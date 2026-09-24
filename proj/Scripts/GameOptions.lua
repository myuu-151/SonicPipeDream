-- GameOptions.lua
-- The player's settings, changed from OPTIONS on the title menu and from the marathon's setup
-- (both OptionsPrompt.lua), and kept with the save: letters after the seven emeralds in
-- StageSelect.lua's save text, so a save made before there were settings still reads (as the
-- defaults).
--
--     GameOptions.muteStageMusic       the stages' and the marathon's music is not played
--                                      (SpecialStageMusic.lua); the menus' is
--     GameOptions.marathon.rounds      zones in a run, 1-20; 0 is endless (SpecialStage.lua)
--     GameOptions.marathon.start       how hard its first zone is, as stage 1-7 (MarathonGen.lua)
--     GameOptions.marathon.climb       how fast it gets harder: 1 none, 2 slow, 3 normal, 4 fast
--     GameOptions.marathon.leniency    spare rings: 1 tight, 2 normal, 3 generous
--     GameOptions.marathon.lives       checks that can be missed before the run ends: 1, 3, 5;
--                                      0 is never (a missed check costs a life, and the run goes on)

local DEFAULT_MARATHON = { rounds = 7, start = 2, climb = 3, leniency = 2, lives = 1 }

GameOptions = GameOptions or { muteStageMusic = false, touched = false, marathon = {} }
for k, v in pairs(DEFAULT_MARATHON) do
    if (GameOptions.marathon[k] == nil) then GameOptions.marathon[k] = v end
end

-- What each setting can be, in order, and how it reads on the screen.
GameOptions.CHOICES = {
    rounds = { values = { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 0 },
               show = function(v) return (v == 0) and "ENDLESS" or tostring(v) end },
    start = { values = { 1, 2, 3, 4, 5, 6, 7 }, show = tostring },
    climb = { values = { 1, 2, 3, 4 }, show = function(v) return ({ "NONE", "SLOW", "NORMAL", "FAST" })[v] end },
    leniency = { values = { 1, 2, 3 }, show = function(v) return ({ "TIGHT", "NORMAL", "GENEROUS" })[v] end },
    lives = { values = { 1, 3, 5, 0 }, show = function(v) return (v == 0) and "INFINITE" or tostring(v) end },
}

-- The letters after the emeralds: mute (M or -), then the marathon's rounds (a letter: A is
-- endless, B one round, ...), start, climb, leniency and lives (a digit each).
function GameOptions.Encode()
    local m = GameOptions.marathon
    return (GameOptions.muteStageMusic and "M" or "-") .. string.char(65 + m.rounds)
           .. tostring(m.start) .. tostring(m.climb) .. tostring(m.leniency) .. tostring(m.lives)
end

-- From a save's text. Settings changed this session and not saved yet stay as the player set them
-- (the menus read the save again every time they are built, on the GameCube); LOAD clears
-- `touched` first, so a save loaded on purpose does bring its settings.
function GameOptions.Decode(text)
    if (GameOptions.touched) then return end
    text = text or ""
    GameOptions.muteStageMusic = (text:sub(8, 8) == "M")
    local m = GameOptions.marathon
    for k, v in pairs(DEFAULT_MARATHON) do m[k] = v end
    local function Digit(at, lo, hi, into)
        local n = tonumber(text:sub(at, at))
        if (n ~= nil and n >= lo and n <= hi) then m[into] = n end
    end
    if (#text >= 9) then
        local r = text:byte(9) - 65
        if (r >= 0 and r <= 20) then m.rounds = r end
    end
    Digit(10, 1, 7, "start")
    Digit(11, 1, 4, "climb")
    Digit(12, 1, 3, "leniency")
    Digit(13, 0, 5, "lives")
end
