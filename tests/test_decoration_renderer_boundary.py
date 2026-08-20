import decoration_renderer

from petpet.ui import decorations


def test_root_decoration_renderer_is_a_compatibility_facade():
    assert decoration_renderer.draw_decoration is decorations.draw_decoration
    assert decoration_renderer.load_decoration_pixmaps is decorations.load_decoration_pixmaps
    assert decoration_renderer.draw_equipped_idle is decorations.draw_equipped_idle
