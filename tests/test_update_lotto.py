import json
import sys
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_lotto as app

def row(draw=1250, day="20261114"):
    return {
        "ltEpsd": draw, "ltRflYmd": day,
        **{f"tm{i}WnNo": n for i, n in enumerate([1,5,18,23,27,28], 1)},
        "bnsWnNo": 8,
        "rnk1WnAmt":3103164459, "rnk1WnNope":9,
        "rnk2WnAmt":46547467, "rnk2WnNope":100,
        "rnk3WnAmt":1491906, "rnk3WnNope":3000,
    }

class CollectorTest(unittest.TestCase):
    TODAY=date(2026,11,15)

    def test_verified(self):
        x=app.parse_draw(row(),self.TODAY,"fixture")
        self.assertEqual(x["ranks"]["2"]["prize_per_game"],46547467)

    def test_mismatched_draw_rejected(self):
        with self.assertRaises(ValueError):
            app.parse_draw(row(1251),self.TODAY,"fixture")

    def test_duplicate_number_rejected(self):
        x=row();x["tm6WnNo"]=x["tm5WnNo"]
        with self.assertRaises(ValueError):
            app.parse_draw(x,self.TODAY,"fixture")

    def test_html_rejected(self):
        with mock.patch.object(app.urllib.request,"urlopen") as urlopen:
            response=mock.MagicMock()
            response.__enter__.return_value=response
            response.headers.get.return_value="text/html"
            response.read.return_value=b"<html>blocked</html>"
            urlopen.return_value=response
            with self.assertRaises(ValueError):
                app.fetch_json("https://www.dhlottery.co.kr/lt645/selectPstLt645Info.do")

    def test_latest_valid_only(self):
        payload={"data":{"list":[row(),row(1251,"20261121")]}}
        self.assertEqual(app.parse_latest(payload,self.TODAY,"fixture")["draw_no"],1250)

    def test_failed_fetch_preserves_existing(self):
        with TemporaryDirectory() as temp:
            old=app.OUTPUT;app.OUTPUT=Path(temp)/"latest.json"
            fixture={"status":"seed","draw_no":1250}
            app.OUTPUT.write_text(json.dumps(fixture))
            try:
                with mock.patch.object(app,"fetch_json",side_effect=ValueError("blocked")):
                    with self.assertRaises(RuntimeError):
                        app.update()
                self.assertEqual(json.loads(app.OUTPUT.read_text()),fixture)
            finally:
                app.OUTPUT=old

    def test_verified_written_on_success(self):
        with TemporaryDirectory() as temp:
            old=app.OUTPUT;app.OUTPUT=Path(temp)/"latest.json"
            app.OUTPUT.write_text(json.dumps({"status":"seed","draw_no":1250}))
            try:
                with mock.patch.object(app,"fetch_json",return_value={"data":{"list":[row()]}}):
                    self.assertTrue(app.update())
                self.assertEqual(json.loads(app.OUTPUT.read_text())["status"],"verified")
            finally:
                app.OUTPUT=old

if __name__=="__main__":
    unittest.main()
