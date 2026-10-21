import unittest

from PIL import Image

import render_commentated_reto00 as video


class CommentatedChallengeTests(unittest.TestCase):
    def setUp(self):
        self.starts = [0, 2.4, 4.9, 6.1, 8.9, 10.3, 12.1, 13.5, 14.7, 16.8, 19.2, 20.6]

    def test_goal_visual_is_synchronized_to_sixteen_exactly(self):
        self.assertEqual(video.source_time(self.starts[6], self.starts), video.SOURCE_GOAL)
        self.assertLess(video.source_time(self.starts[6] - .1, self.starts), video.SOURCE_GOAL)
        self.assertGreater(video.source_time(self.starts[6] + .1, self.starts), video.SOURCE_GOAL)

    def test_all_sampled_source_positions_stay_inside_reviewed_footage(self):
        for frame in range(round(24.3 * video.FPS)):
            position = video.source_time(frame / video.FPS, self.starts)
            self.assertGreaterEqual(position, video.SOURCE_START)
            self.assertLess(position, video.SOURCE_START + video.SOURCE_DURATION)

    def test_every_phase_renders_in_vertical_format_and_text_safe_area(self):
        art = Image.new("RGB", (480, 832), video.BG)
        cues = [(0, 24.3, "en clockpenalty.com.")]
        for elapsed in [0, 5, 7, 9, 12.1, 14, 17, 20.7, 24.2]:
            image = video.compose_frame(art, elapsed, 24.3, cues, self.starts)
            self.assertEqual(image.size, (1080, 1920))

    def test_exact_cta_and_current_domain(self):
        self.assertEqual(video.CTA, "Invita a tu amigo a jugar ahora en clockpenalty.com")
        self.assertIsNone(video.FORBIDDEN.search(video.CTA))


if __name__ == "__main__":
    unittest.main()
