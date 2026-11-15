from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from .management.commands.performance_check import percentile, summarize


class PerformanceStatisticsTests(SimpleTestCase):
    def test_percentile_uses_nearest_rank(self):
        self.assertEqual(percentile(list(range(1, 11)), 90), 9)

    def test_percentile_handles_empty_samples_and_boundaries(self):
        self.assertIsNone(percentile([], 90))
        self.assertEqual(percentile([3, 1, 2], 0), 1)
        self.assertEqual(percentile([3, 1, 2], 100), 3)

    def test_percentile_rejects_out_of_range_percent(self):
        with self.assertRaises(ValueError):
            percentile([1, 2, 3], 101)

    def test_summarize_reports_latency_distribution(self):
        result = summarize([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])

        self.assertEqual(result["count"], 10)
        self.assertEqual(result["median_ms"], 55)
        self.assertEqual(result["p90_ms"], 90)
        self.assertEqual(result["p95_ms"], 100)

    def test_command_rejects_unrepresentative_request_counts(self):
        with self.assertRaises(CommandError):
            call_command(
                "performance_check",
                requests=5,
                stdout=StringIO(),
            )
