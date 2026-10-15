"""The USB payload must stay compatible with the custom EdgeTX fork."""
from thrust.tx16smk3_led import (
    BUTTON_LEDS, LEFT_RING, RIGHT_RING, TARGET_ALL, LedStyle, _is_tx16smk3,
    brightness, color_at, frame_report, proximity_color, report,
    target_tracking_frame,
)


def test_feature_report_wire_layout() -> None:
    # HIDAPI prepends report ID 0; the current descriptor expects an 80-byte payload.
    assert report(1, (0x12, 0x34, 0x56)) == bytes(
        (0, 1, 1, 0, 0x12, 0x34, 0x56, 0, 0) + (0,) * 72
    )
    assert report(2) == bytes((0, 1, 2, 0, 0, 0, 0, 0, 0) + (0,) * 72)
    assert report(2, target=TARGET_ALL)[:4] == bytes((0, 1, 2, TARGET_ALL))
    assert len(report(1)) == 81


def test_radio_name_matches_radio_master_usb_product_string() -> None:
    assert _is_tx16smk3({"product_string": "OpenTX RadioMaster TX16S MK3 Joystick"})
    assert not _is_tx16smk3({"product_string": "RadioMaster TX16S"})


def test_full_frame_report_contains_all_leds() -> None:
    colors = {index: (index, index, index) for index in range(26)}
    packet = frame_report(colors)
    assert len(packet) == 81
    assert packet[:5] == bytes((0, 1, 4, 0, 0))
    assert packet[-3:] == bytes((25, 25, 25))


def test_brightness_animations_only_change_rgb_intensity() -> None:
    assert color_at(LedStyle("#123456", "solid"), 20) == (18, 52, 86)
    assert color_at(LedStyle("#123456", "blink"), 0.4) == (0, 0, 0)
    assert color_at(LedStyle("#123456", "blink"), 0.1) == (18, 52, 86)
    assert 0 < brightness("pulse", 0) < brightness("pulse", 0.9) == 1


def test_target_tracking_color_blends_red_yellow_green() -> None:
    assert proximity_color(0) == (255, 0, 0)
    assert proximity_color(0.5) == (255, 255, 0)
    assert proximity_color(1) == (0, 255, 0)


def test_target_tracking_shows_direction_and_green_inside_deadzone() -> None:
    frame = target_tracking_frame(
        (1000, 0), (0, 1000), max_range=1000,
        left_deadzone=(50, 50), right_deadzone=(50, 50),
    )
    # The left vector points halfway between LEDs; both adjacent LEDs show it.
    assert sum(frame[index] != (0, 0, 0) for index in LEFT_RING) == 2
    assert sum(frame[index] != (0, 0, 0) for index in RIGHT_RING) == 1
    assert all(frame[index] == (0, 0, 0) for index in BUTTON_LEDS)

    centered = target_tracking_frame(
        (0, 0), (0, 0), max_range=1000,
        left_deadzone=(50, 50), right_deadzone=(50, 50),
    )
    assert all(centered[index] == (0, 255, 0) for index in LEFT_RING + RIGHT_RING)
    assert all(centered[index] == (0, 0, 0) for index in BUTTON_LEDS)
