import unittest

import numpy as np
from PIL import Image

import render_gameplay_preview as preview


class GameplayPreviewTests(unittest.TestCase):
    def test_private_match_regions_are_completely_replaced(self):
        first = Image.new("RGB", (480, 832), "red")
        second = Image.new("RGB", (480, 832), "blue")
        a = np.asarray(preview.sanitize(first, "match", "Comentario"))
        b = np.asarray(preview.sanitize(second, "match", "Comentario"))
        for top, bottom in [(170, 253), (307, 340), (660, 774)]:
            np.testing.assert_array_equal(a[top:bottom], b[top:bottom])
        self.assertFalse(np.array_equal(a[400:600], b[400:600]))

    def test_league_title_and_player_name_are_completely_replaced(self):
        a = np.asarray(preview.sanitize(Image.new("RGB", (464, 816), "red"), "league"))
        b = np.asarray(preview.sanitize(Image.new("RGB", (464, 816), "blue"), "league"))
        for x1, y1, x2, y2 in [(15, 94, 451, 251), (106, 770, 306, 816)]:
            np.testing.assert_array_equal(a[y1:y2, x1:x2], b[y1:y2, x1:x2])

    def test_rejects_unreviewed_source_geometry_and_unknown_profile(self):
        with self.assertRaises(ValueError):
            preview.sanitize(Image.new("RGB", (1080, 1920)), "match")
        with self.assertRaises(ValueError):
            preview.sanitize(Image.new("RGB", (480, 832)), "unknown")

    def test_generated_titles_aliases_and_domain_do_not_contain_old_identifiers(self):
        text = str(preview.TITLES) + str(preview.ALIASES) + preview.DOMAIN
        self.assertIsNone(preview.FORBIDDEN.search(text))
        self.assertEqual(preview.DOMAIN, "clockpenalty.com")


if __name__ == "__main__":
    unittest.main()
