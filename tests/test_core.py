import unittest
from pathlib import Path

from cortesbylrm.core import (
    check_rights, clip_srt, ffmpeg_command, parse_srt, suggest_cuts,
)

SRT = """1
00:00:00,000 --> 00:00:05,000
Por que isso acontece?

2
00:00:05,000 --> 00:00:10,000
Primeiro precisamos entender o problema.

3
00:00:10,000 --> 00:00:15,000
Uma ideia bem construída tem contexto.

4
00:00:15,000 --> 00:00:20,000
O melhor exemplo ajuda a explicar.

5
00:00:20,000 --> 00:00:25,000
Depois mostramos um resultado concreto.

6
00:00:25,000 --> 00:00:30,000
O fechamento conclui o raciocínio.

7
00:00:30,000 --> 00:00:35,000
Mas esta é outra história.

8
00:00:35,000 --> 00:00:40,000
Uma sequência com começo meio e fim.
"""


class CoreTests(unittest.TestCase):
    def test_rights_require_both_basis_and_evidence(self):
        with self.assertRaises(ValueError):
            check_rights("campanha", "")
        with self.assertRaises(ValueError):
            check_rights("indefinido", "https://example.org")
        check_rights("proprio", "Arquivo criado por mim")

    def test_parse_srt(self):
        cues = parse_srt(SRT.replace("\n", "\r\n"))
        self.assertEqual(len(cues), 8)
        self.assertAlmostEqual(cues[0].start, 0.0)
        self.assertEqual(cues[-1].end, 40.0)

    def test_invalid_cues_ignored(self):
        self.assertEqual(parse_srt("1\n00:00:XX,000 --> 00:00:10,000\nTexto"), [])

    def test_suggest(self):
        proposals = suggest_cuts(parse_srt(SRT), limit=2)
        self.assertGreaterEqual(len(proposals), 1)
        self.assertLessEqual(len(proposals), 2)
        self.assertGreater(proposals[0].end, proposals[0].start)

    def test_clip_srt_reset_and_trim(self):
        captions = clip_srt(parse_srt(SRT), 4, 12)
        self.assertIn("00:00:00,000 --> 00:00:01,000", captions)
        self.assertIn("00:00:06,000 --> 00:00:08,000", captions)

    def test_ffmpeg_safe_arg_list(self):
        args = ffmpeg_command(Path("input.mp4"), Path("out.mp4"), 5, 35)
        self.assertEqual(args[0], "ffmpeg")
        self.assertIn("pad=1080:1920", " ".join(args))
        self.assertEqual(args[-1], "out.mp4")
        with self.assertRaises(ValueError):
            ffmpeg_command(Path("x"), Path("y"), 50, 30)


if __name__ == "__main__":
    unittest.main()
