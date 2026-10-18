"""Targeted tests for cached neural narration and subtitle synchronization."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

import render_beta_install_video as video


class NarrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.clips = []
        for index, phrase in enumerate(phrase for scene in video.SCENES for phrase in scene[4]):
            data = f"audio-{index}".encode()
            filename = f"phrase-{index}.mp3"
            (self.folder / filename).write_bytes(data)
            self.clips.append({
                "complete": True, "file": filename, "text": phrase,
                "sha256": hashlib.sha256(data).hexdigest(),
                "alignment": {
                    "characters": list(phrase),
                    "character_start_times_seconds": [i * .02 for i in range(len(phrase))],
                    "character_end_times_seconds": [(i+1) * .02 for i in range(len(phrase))],
                },
            })
        self.manifest = {
            "provider": "ElevenLabs", "voice": {"id": "test-voice"},
            "model": "eleven_multilingual_v2", "clips": self.clips,
        }
        self.audio = SimpleNamespace(stdout=np.full(video.RATE*4, .1, dtype="<f4").tobytes())

    def write(self):
        (self.folder / "narration.json").write_text(json.dumps(self.manifest))

    def test_exact_script_hashes_and_alignment_are_loaded_without_api_calls(self):
        self.write()
        with patch.object(video.subprocess, "run", return_value=self.audio):
            _, decoded = video.load_narration(self.folder)
            scenes, captions, duration = video.prepare_audio(self.folder, decoded)
        self.assertEqual(len(scenes), 6)
        self.assertEqual(len(captions), 12)
        self.assertAlmostEqual(sum(scene["duration"] for scene in scenes), duration)
        for scene in scenes:
            self.assertAlmostEqual(scene["frames"] / video.FPS, scene["duration"])
        self.assertTrue(all(0 <= start < end <= duration for start, end, _ in captions))
        self.assertTrue(all(a[1] <= b[0] for a, b in zip(captions, captions[1:])))

    def test_incomplete_narration_is_not_replaced_by_robotic_speech(self):
        self.manifest["clips"] = self.clips[:-1]
        self.write()
        with self.assertRaises(ValueError):
            video.load_narration(self.folder)

    def test_mismatched_script_hash_and_path_are_rejected(self):
        for field, value in [("text", "wrong"), ("sha256", "wrong"), ("file", "../outside.mp3")]:
            original = self.clips[0][field]
            self.clips[0][field] = value
            self.write()
            with self.assertRaises(ValueError):
                video.load_narration(self.folder)
            self.clips[0][field] = original

    def test_invalid_alignment_is_rejected(self):
        self.clips[0]["alignment"]["character_start_times_seconds"][0] = -1
        self.write()
        with self.assertRaises(ValueError):
            video.load_narration(self.folder)

    def test_captions_fit_and_timestamps_have_srt_format(self):
        self.assertEqual(video.stamp(3661.234), "01:01:01,234")
        for scene in video.SCENES:
            for phrase in scene[4]:
                self.assertLessEqual(len(video.lines(phrase, 35, 860)), 3)


if __name__ == "__main__":
    unittest.main()
