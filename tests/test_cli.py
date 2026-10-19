import contextlib
from io import StringIO
from pathlib import Path
import json
import tempfile
import unittest

from cortesbylrm.cli import main


SRT = """1
00:00:00,000 --> 00:00:10,000
Como organizar uma boa ideia em cinco minutos.

2
00:00:10,000 --> 00:00:20,000
Primeiro reunimos as informações corretas e conferimos a origem.

3
00:00:20,000 --> 00:00:30,000
Depois escolhemos os pontos principais e construímos um exemplo.

4
00:00:30,000 --> 00:00:40,000
Finalmente concluímos a explicação com clareza.
"""


class CliTests(unittest.TestCase):
    def test_plan_render_dry_run_and_record(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            video = d / "exemplo.mp4"
            video.write_bytes(b"video-de-exemplo-sem-decodificar")
            srt = d / "exemplo.srt"
            srt.write_text(SRT, encoding="utf-8")
            manifest = d / "plano.json"
            output = StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([
                    "plan", "--video", str(video), "--srt", str(srt),
                    "--basis", "proprio", "--proof", "Criação original para teste",
                    "--output", str(manifest),
                ]), 0)
            plan = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertTrue(plan["review_required"])
            self.assertFalse(plan["publish_automatically"])
            self.assertGreater(len(plan["clips"]), 0)
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([
                    "render", "--manifest", str(manifest), "--clip", "1", "--dry-run"
                ]), 0)
            self.assertIn("ffmpeg", output.getvalue())

            ledger = d / "financial.json"
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([
                    "record", "--ledger", str(ledger),
                    "--platform", "youtube", "--url", "https://example.org/video",
                    "--views", "100", "--eligible-views", "60",
                    "--status", "paid", "--amount", "1.50",
                ]), 0)
                self.assertEqual(main(["report", "--ledger", str(ledger)]), 0)
            self.assertIn("paid: R$ 1.50", output.getvalue())


if __name__ == "__main__":
    unittest.main()
