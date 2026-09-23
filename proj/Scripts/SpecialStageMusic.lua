-- SpecialStageMusic.lua
-- Plays the special stage music: the intro once, then the loop for ever -- or, for a stage with a
-- track of its own (STAGE_TRACKS), that track, looped whole from the top.
-- Attach to any node in the scene.
--
-- Only while the game is running. There is deliberately no EditorTick here, or
-- the music would start every time the scene was opened for editing.

SpecialStageMusic = {}

-- stage -> its own track (native/gen_music_assets.py makes them from external/audio)
local STAGE_TRACKS = {
    [1] = "SW_SpecialStage_Stage1",
}

-- The track of the stage being played, or nil for the special stage theme.
function SpecialStageMusic:PickTrack()
    local stage = (TheSpecialStage ~= nil) and TheSpecialStage.stage or 1
    local name = STAGE_TRACKS[stage]
    self.track = (name ~= nil) and LoadAsset(name) or nil
    if (name ~= nil and self.track == nil) then Log.Error("SpecialStageMusic: " .. name .. " not found") end
end

-- The stage's own track, looped; true if there is one.
function SpecialStageMusic:PlayTrack()
    self:PickTrack()
    if (self.track == nil) then return false end
    Audio.PlaySound2D(self.track, self.volume, 1.0, 0.0, true)
    self.looping = true
    return true
end

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

function SpecialStageMusic:StartLoop()
    self.looping = true
    if (self.loop ~= nil) then
        -- volume, pitch, start time, loop
        Audio.PlaySound2D(self.loop, self.volume, 1.0, 0.0, true)
    end
end

function SpecialStageMusic:Tick(deltaTime)
    if (not self.started) then
        self.started = true
        if (self:PlayTrack()) then return end
        self.intro = LoadAsset("SW_SpecialStage_Intro")
        self.loop = LoadAsset("SW_SpecialStage_Loop")
        if (self.loop == nil) then
            Log.Error("SpecialStageMusic: SW_SpecialStage_Loop not found")
        end

        if (self.playIntro and self.intro ~= nil) then
            self.introLength = self.intro:GetDuration()
            Audio.PlaySound2D(self.intro, self.volume, 1.0, 0.0, false)
        else
            self:StartLoop()
        end
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
    if (self.track ~= nil) then Audio.StopSounds(self.track) end
    self.looping = false
    self.stopped = true
end

-- Played again from the top: the stage was left and another one has been chosen.
function SpecialStageMusic:Restart()
    self:Stop()
    self.stopped = false
    self.elapsed = 0.0
    if (self:PlayTrack()) then return end
    -- (a stage's own track may have been all that was loaded so far)
    self.intro = self.intro or LoadAsset("SW_SpecialStage_Intro")
    self.loop = self.loop or LoadAsset("SW_SpecialStage_Loop")
    if (self.intro ~= nil) then self.introLength = self.intro:GetDuration() end
    if (self.playIntro and self.intro ~= nil) then
        Audio.PlaySound2D(self.intro, self.volume)
    else
        self:StartLoop()
    end
end
