-- MenuMusic.lua
-- The menus' music: menuintro once, then menuloop for ever, while the title menu or the stage
-- select is up and no loading screen is over them. It stops as a stage is chosen (the loading
-- screen goes up), and starts from the intro again when the menus come back.
--
-- Not a node script: Sky.lua ticks it (MenuMusic.Tick), and on the GameCube Screens.lua does too
-- while its loading screen holds the sky still. It watches TheMenu, TheStageSelect and TheLoading
-- for itself, so nothing that opens or closes a menu has to remember it.

MenuMusic = {}

local INTRO, LOOP = "SW_SpecialStage_MenuIntro", "SW_SpecialStage_MenuLoop"
local VOLUME = 0.9

local function MenusUp()
    local menu = TheMenu ~= nil and TheMenu.open
    local select = TheStageSelect ~= nil and TheStageSelect.open
    local loading = TheLoading ~= nil and TheLoading.shown
    return (menu or select) and not loading
end

function MenuMusic.Start()
    local m = MenuMusic
    if (m.intro == nil) then m.intro = LoadAsset(INTRO) or false end
    if (m.loop == nil) then m.loop = LoadAsset(LOOP) or false end
    m.playing, m.looping, m.elapsed = true, false, 0.0
    if (m.intro) then
        m.introLength = m.intro:GetDuration()
        Audio.PlaySound2D(m.intro, VOLUME, 1.0, 0.0, false, 100)       -- (above every effect: see SpecialStage.lua)
    else
        m.StartLoop()
    end
end

function MenuMusic.StartLoop()
    local m = MenuMusic
    m.looping = true
    if (m.loop) then Audio.PlaySound2D(m.loop, VOLUME, 1.0, 0.0, true, 100) end
end

function MenuMusic.Stop()
    local m = MenuMusic
    if (m.intro) then Audio.StopSounds(m.intro) end
    if (m.loop) then Audio.StopSounds(m.loop) end
    m.playing = false
end

function MenuMusic.Tick(deltaTime)
    local m = MenuMusic
    if (not MenusUp()) then
        if (m.playing) then m.Stop() end
        return
    end
    if (not m.playing) then
        m.Start()
    elseif (not m.looping) then
        -- on the clock, as SpecialStageMusic does: the loop starts on the tick that carries the
        -- intro past its end, so there is no frame of silence in the join
        m.elapsed = m.elapsed + deltaTime
        if (m.elapsed + deltaTime * 0.5 >= m.introLength) then m.StartLoop() end
    end
end
