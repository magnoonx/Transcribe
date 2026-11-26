import unittest

from translator import apply_time_offset, load_subtitles_from_bytes


class TimeOffsetTests(unittest.TestCase):
    def test_apply_time_offset_moves_each_subtitle(self):
        data = b"1\n00:00:00,000 --> 00:00:02,000\nHola\n\n2\n00:00:03,000 --> 00:00:05,000\nAdios\n"
        subs = load_subtitles_from_bytes(data)

        apply_time_offset(subs, 5)

        self.assertEqual((subs[0].start.hours, subs[0].start.minutes, subs[0].start.seconds, subs[0].start.milliseconds), (0, 0, 5, 0))
        self.assertEqual((subs[0].end.hours, subs[0].end.minutes, subs[0].end.seconds, subs[0].end.milliseconds), (0, 0, 7, 0))
        self.assertEqual((subs[1].start.hours, subs[1].start.minutes, subs[1].start.seconds, subs[1].start.milliseconds), (0, 0, 8, 0))
        self.assertEqual((subs[1].end.hours, subs[1].end.minutes, subs[1].end.seconds, subs[1].end.milliseconds), (0, 0, 10, 0))


if __name__ == "__main__":
    unittest.main()
