import unittest
from strategy.technical import analyze


class TechnicalTests(unittest.TestCase):
    def test_bullish_trend_and_volume(self):
        candles = [
            {"open": 10, "high": 11, "low": 9, "close": 10, "volume": 100},
            {"open": 10, "high": 11, "low": 9.8, "close": 10.8, "volume": 110},
            {"open": 10.7, "high": 12, "low": 10.6, "close": 11.8, "volume": 200},
        ]
        signal = analyze(candles)
        self.assertEqual(signal.trend, "bullish")
        self.assertTrue(signal.volume_confirmed)

    def test_requires_minimum_candles(self):
        with self.assertRaises(ValueError):
            analyze([])


if __name__ == "__main__":
    unittest.main()
