from unittest import TestCase

from hifiberrydsp.lg.soundsync import SoundSync

class TestSoundSync(TestCase):
    def test_parse_volume_with_missing_sound_sync_signature(self):
        assert SoundSync.parse_volume_from_status(b'\xff\xff\xff\xff\xff\xff') is None

    def test_parse_out_of_range_volume(self):
        # The maximum value is 100, but we don't enforce that in the parser itself,
        # but rather in later validation.
        assert SoundSync.parse_volume_from_status(b'\x00\x1f\xff\x04\x8a\x62') == 255

    def test_parse_volume_of_0(self):
        assert SoundSync.parse_volume_from_status(b'\x00\x10\x0f\x04\x8a\x62') == 0

    def test_parse_volume_of_50(self):
        assert SoundSync.parse_volume_from_status(b'\x00\x13\x2f\x04\x8a\x62') == 50

    def test_parse_volume_of_100(self):
        assert SoundSync.parse_volume_from_status(b'\x00\x16\x4f\x04\x8a\x62') == 100

    def test_parse_volume_of_100_on_another_tv(self):
        # Data observed on a LG OLED55C9
        assert SoundSync.parse_volume_from_status(b'\x00\x06\x4f\x04\x8a\x60') == 100