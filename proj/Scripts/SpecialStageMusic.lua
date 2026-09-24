-- SpecialStageMusic.lua
-- Plays the stage's music: its intro once, then its loop for ever. Each stage can have its own
-- (STAGE_MUSIC); the rest play the special stage theme. A stage with a loop and no intro plays
-- the loop from the top.
-- Attach to any node in the scene.
--
-- Only while the game is running. There is deliberately no EditorTick here, or
-- the music would start every time the scene was opened for editing.

Script.Require("GameOptions")   -- OPTIONS > AUDIO can mute it

SpecialStageMusic = {}

-- The special stage theme, and stage -> its own music. native/gen_music_assets.py makes the
-- assets from external/audio (and the GameCube's export_assets_gc.py, streamed from the disc).
-- An intro that runs into its loop ends where the loop ends: it is the lead-in and then one whole
-- pass of the loop, so the loop picks up exactly where it finishes.
local THEME = { intro = "SW_SpecialStage_Intro", loop = "SW_SpecialStage_Loop" }
-- The tracks are named for the stage they were made for; the owner's order (2026-09-24) has stage 3
-- play the SSR track, stage 4 share stage 1's, and stages 5 and 6 play the tracks of 4 and 5 (Cream
-- moved from 4 to 5).
local STAGE_MUSIC = {
    [1] = { loop = "SW_SpecialStage_Stage1" },
    [2] = { intro = "SW_SpecialStage_Stage2Intro", loop = "SW_SpecialStage_Stage2Loop" },
    [3] = { intro = "SW_SpecialStage_SSRIntro", loop = "SW_SpecialStage_SSRLoop" },
    [4] = { loop = "SW_SpecialStage_Stage1" },
    [5] = { intro = "SW_SpecialStage_Stage4Intro", loop = "SW_SpecialStage_Stage4Loop" },
    [6] = { loop = "SW_SpecialStage_Stage5" },        -- one whole track that loops on itself
    [7] = { intro = "SW_SpecialStage_Stage7Intro", loop = "SW_SpecialStage_Stage7Loop" },
    Marathon = { loop = "SW_SpecialStage_Marathon" },   -- one whole track that loops on itself
}

function SpecialStageMusic:Create()
    self.volume = 1.0
    -- Turn off to go straight to the loop.
    self.playIntro = true

    self.started = false
    self.looping = false
    self.stopped = false    -- set by Stop: the stage was left, so Tick must not start the loop
    self.elapsed = 0.0
    TheSpecialStageMusic = self     -- so the stage can stop it when it hands back to the menu
end

function SpecialStageMusic:GatherProperties()
    return
    {
        { name = "volume", type = DatumType.Float },
        { name = "playIntro", type = DatumType.Bool },
    }
end

local function Load(name)
    if (name == nil) then return nil end
    local asset = LoadAsset(name)
    if (asset == nil) then Log.Error("SpecialStageMusic: " .. name .. " not found") end
    return asset
end

-- The music of the stage being played, from the top: its intro, or straight into its loop.
function SpecialStageMusic:Begin()
    local stage = (TheSpecialStage ~= nil) and TheSpecialStage.stage or 1
    local music = STAGE_MUSIC[stage] or THEME
    if (GameOptions.muteStageMusic) then
        -- muted in OPTIONS > AUDIO: nothing loaded, nothing played (the menus' music is not this)
        self.intro, self.loop = nil, nil
        self.stopped, self.looping, self.elapsed = true, false, 0.0
        return
    end
    self.intro, self.loop = Load(music.intro), Load(music.loop)
    self.stopped, self.looping, self.elapsed = false, false, 0.0
    if (self.playIntro and self.intro ~= nil) then
        self.introLength = self.intro:GetDuration()
        -- volume, pitch, start time, loop
        Audio.PlaySound2D(self.intro, self.volume, 1.0, 0.0, false)
    else
        self:StartLoop()
    end
end

function SpecialStageMusic:StartLoop()
    self.looping = true
    if (self.loop ~= nil) then
        Audio.PlaySound2D(self.loop, self.volume, 1.0, 0.0, true)
    end
end

function SpecialStageMusic:Tick(deltaTime)
    if (not self.started) then
        self.started = true
        self:Begin()
        return
    end

    if (self.looping or self.stopped) then
        return
    end

    -- Hand over on the clock, not by asking whether the intro is still playing.
    -- That question is only answered once a frame, after the sound has already
    -- stopped, which leaves a frame of silence in the join. Starting the loop on
    -- the tick that will carry the intro past its end closes most of that gap.
    self.elapsed = self.elapsed + deltaTime
    if (self.elapsed + deltaTime * 0.5 >= self.introLength) then
        self:StartLoop()
    end
end

function SpecialStageMusic:Stop()
    if (self.intro ~= nil) then Audio.StopSounds(self.intro) end
    if (self.loop ~= nil) then Audio.StopSounds(self.loop) end
    self.looping = false
    self.stopped = true
end

-- Played again from the top: the stage was left and another one (or the same) has been chosen.
function SpecialStageMusic:Restart()
    self:Stop()
    self:Begin()
end
