import unittest

from ednna.sync_timings import SyncTimings


class SyncTimingTests(unittest.TestCase):
    def test_stage_timings_are_monotonic_and_aggregated(self):
        values = iter([10.0, 11.5, 13.0, 15.0])
        timing = SyncTimings(clock=lambda: next(values))
        timing.mark("redmine")
        timing.mark("mysql")
        report = timing.report()
        self.assertEqual(report["duracao_total_s"], 5.0)
        self.assertEqual(report["etapas_s"], {"redmine": 1.5, "mysql": 1.5})

    def test_unknown_stage_rejected(self):
        timing = SyncTimings(clock=lambda: 1.0)
        with self.assertRaises(ValueError):
            timing.mark("password")


if __name__ == "__main__":
    unittest.main()
