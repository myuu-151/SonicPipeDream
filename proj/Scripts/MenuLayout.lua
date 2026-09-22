-- Written by native/gen_menu_assets.py. Do not edit: run that instead.
-- Where every piece of the menu goes, on the mockup's own 522 x 386 screen.
--
--     x, y, w, h   where the piece belongs on that screen
--     aw, ah       the art's own size in its texture (the panel is one 8 px column,
--                  stretched across the window, so this is not always w and h)
--     cw, ch       the texture, padded up to a power of two with the art top left
--
-- A piece is drawn by putting the WHOLE texture in a rectangle of
--     (w * k * cw / aw)  x  (h * k * ch / ah)
-- at (x * k, y * k): the art then lands on (x, y, w, h) and the padding falls
-- outside it.
MenuLayout = {
    screen = { w = 522, h = 386 },
    panel_top = 47,
    parts = {
        T_Menu_Panel = { x = 0, y = 47, w = 522, h = 339, aw = 8, ah = 339, cw = 8, ch = 512 },
        T_Menu_Circles = { x = -128, y = -176, w = 292, h = 292, aw = 292, ah = 292, cw = 512, ch = 512 },
        T_Menu_TitleBanner = { x = 0, y = 12, w = 323, h = 35, aw = 323, ah = 35, cw = 512, ch = 64 },
        T_Menu_TitleText = { x = 29, y = 18, w = 246, h = 24, aw = 246, ah = 24, cw = 256, ch = 32 },
        T_Menu_Watermark = { x = -17, y = 344, w = 549, h = 47, aw = 549, ah = 47, cw = 1024, ch = 64 },
        T_Menu_SelectBar = { x = 28, y = 98, w = 288, h = 45, aw = 288, ah = 45, cw = 512, ch = 64 },
        T_Menu_Cursor = { x = 10, y = 108, w = 15, h = 24, aw = 15, ah = 24, cw = 16, ch = 32 },
        T_Menu_PreviewFrame = { x = 330, y = 118, w = 173, h = 151, aw = 173, ah = 151, cw = 256, ch = 256 },
        T_Menu_Preview = { x = 334, y = 122, w = 165, h = 143, aw = 165, ah = 143, cw = 256, ch = 256 },
        T_Menu_Emerald = { x = 402, y = 93, w = 30, h = 24, aw = 30, ah = 24, cw = 32, ch = 32 },
        T_Menu_LabelStage = { x = 363, y = 273, w = 107, h = 10, aw = 107, ah = 10, cw = 128, ch = 16 },
        T_Menu_ButtonA = { x = 370, y = 314, w = 26, h = 27, aw = 26, ah = 27, cw = 32, ch = 32 },
        T_Menu_ButtonB = { x = 453, y = 314, w = 25, h = 27, aw = 25, ah = 27, cw = 32, ch = 32 },
        T_Menu_LabelSelect = { x = 400, y = 321, w = 38, h = 12, aw = 38, ah = 12, cw = 64, ch = 16 },
        T_Menu_LabelBack = { x = 481, y = 321, w = 30, h = 12, aw = 30, ah = 12, cw = 32, ch = 16 },
        T_Menu_Item1 = { x = 41, y = 105, w = 198, h = 30, aw = 198, ah = 30, cw = 256, ch = 32 },
        T_Menu_Item2 = { x = 38, y = 161, w = 167, h = 29, aw = 167, ah = 29, cw = 256, ch = 32 },
        T_Menu_Item3 = { x = 39, y = 213, w = 139, h = 29, aw = 139, ah = 29, cw = 256, ch = 32 },
        T_Menu_Item4 = { x = 39, y = 266, w = 135, h = 34, aw = 135, ah = 34, cw = 256, ch = 64 },
    },
    items = { "main_game", "marathon", "records", "options" },
}
