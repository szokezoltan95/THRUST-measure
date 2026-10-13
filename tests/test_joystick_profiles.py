from thrust.joystick_profiles import joystick_profile_key


def test_joystick_profile_key_uses_guid_when_available():
    assert joystick_profile_key("03000000ABCD", "Controller") == joystick_profile_key(
        "03000000abcd", "Different published name"
    )
    assert joystick_profile_key("03000000abcd", "Controller") != joystick_profile_key(
        "03000000efgh", "Controller"
    )


def test_joystick_profile_key_falls_back_to_published_name():
    assert joystick_profile_key(None, "  Radiomaster TX16S  ") == joystick_profile_key(
        "", "radiomaster tx16s"
    )
    assert joystick_profile_key("", "") is None
