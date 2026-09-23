-- Written by native/export_to_octave.py -- zones <seed ...>. Do not edit by hand.
-- zones[z] = the seeds whose zone z there is a MarathonZone_<z>_<seed>.lua of. A run takes one of
-- each, at random, in order: zone 1 is always the first and easiest.
MarathonPool = {
  step = 5.0201,
  pipe_radius = 10,
  hover = 1.9,
  angle_00_side = -1,
  arch = {
    rings = 9,
    reach = 11.6,
    from_deg = 12,
    ring_scale = 1.03,
    toward_player = 0.72,
    steps_per_second = 8,
  },
  palette_skies = {0,4,6,2,5,3,1},
  zones = {
    {1,101,102,103,104},
    {1,101,102,103,104},
    {1,101,102,103,104},
    {1,101,102,103,104},
    {1,101,102,103,104},
    {1,101,102,103,104},
    {101,102,103,104},
    {101,102,103,104},
  },
}
