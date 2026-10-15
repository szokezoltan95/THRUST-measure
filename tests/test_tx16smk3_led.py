"""The USB payload must stay compatible with the custom EdgeTX fork."""
from thrust.tx16smk3_led import LedStyle, brightness, color_at, report, is_tx16smk3_product


def test_feature_report_wire_layout() -> None:
    # HIDAPI's first byte is the unnumbered report ID; EdgeTX sees eight bytes.
    assert report(1, (0x12, 0x34, 0x56)) == bytes((0, 1, 1, 0, 0x12, 0x34, 0x56, 0, 0))
    assert report(2) == bytes((0, 1, 2, 0, 0, 0, 0, 0, 0))


def test_brightness_animations_only_change_rgb_intensity() -> None:
    assert color_at(LedStyle("#123456", "solid"), 20) == (18, 52, 86)
    assert color_at(LedStyle("#123456", "blink"), 0.4) == (0, 0, 0)
    assert color_at(LedStyle("#123456", "blink"), 0.1) == (18, 52, 86)
    assert 0 < brightness("pulse", 0) < brightness("pulse", 0.9) == 1



def test_tx16smk3_product_name_allows_separators() -> None:
    assert is_tx16smk3_product("RadioMaster TX16S MK3 Joystick")
    assert is_tx16smk3_product("RadioMaster-TX16SMK3-Joystick")
    assert not is_tx16smk3_product("RadioMaster TX16S Joystick")
    assert not is_tx16smk3_product(None)
