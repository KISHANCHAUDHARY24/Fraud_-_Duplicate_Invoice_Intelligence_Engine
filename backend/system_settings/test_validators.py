"""Every validation rule for Admin-editable settings (a bad value would silently break fraud detection)."""

from django.test import SimpleTestCase
from rest_framework.serializers import ValidationError

from .defaults import DEFAULT_SETTINGS
from .validators import VALIDATORS, validate_setting

WEIGHTS = {"invoice_number": 0.3, "vendor": 0.25, "amount": 0.2, "date": 0.15, "description": 0.1}

# key -> [(invalid value, part of the expected message), ...]
INVALID = {
    "approval_threshold": [("10000", "Must be a number"), (True, "Must be a number"), (0, "greater than 0"), (-5, "greater than 0")],
    "near_threshold_percent": [(0, "greater than 0"), (51, "at most 50")],
    "auto_approve_low_risk": [("yes", "true or false"), (1, "true or false")],
    "duplicate_threshold": [(80.5, "whole number"), (0, "at least 1"), (101, "at most 100")],
    "duplicate_weights": [
        ({"vendor": 1.0}, "exactly these keys"),
        ({**WEIGHTS, "vendor": 0.3}, "add up to 1.0 (currently 1.050)"),
        ({**WEIGHTS, "vendor": -0.25, "amount": 0.7}, "at least 0"),
        ([0.3, 0.25], "exactly these keys"),
    ],
    "duplicate_lookback_days": [(0, "at least 1"), (3651, "at most 3650")],
    "working_hours": [
        ({"start": "08:00"}, "Must look like"),
        ({"start": "8:00", "end": "19:00"}, "HH:MM"),
        ({"start": "08:00", "end": "24:00"}, "HH:MM"),
        ({"start": "19:00", "end": "08:00"}, "before end time"),
        ("08:00-19:00", "Must look like"),
    ],
    "working_days": [([], "non-empty list"), ("0,1,2", "non-empty list"), ([0, 7], "at most 6"), ([1, 1], "must not repeat"),
                     ([0.5], "whole number")],
    "timezone": [(5, "timezone name"), ("Mars/Olympus", "Unknown timezone")],
    "split_window_days": [(0, "at least 1"), (91, "at most 90")],
    "split_min_invoices": [(0, "at least 1"), (21, "at most 20")],
    "round_amount_base": [(0, "at least 1"), (2.5, "whole number")],
    "bank_change_window_days": [(0, "at least 1"), (366, "at most 365")],
    "ml_anomaly_threshold": [(-0.1, "at least 0"), (1.5, "at most 1")],
    "risk_level_thresholds": [
        ({"medium": 30, "high": 60}, "Must look like"),
        ({"medium": 60, "high": 30, "critical": 80}, "must increase"),
        ({"medium": 30, "high": 60, "critical": 101}, "at most 100"),
    ],
    "signal_weights": [
        ({"DUPLICATE": 30}, "exactly these signal types"),
        ({**DEFAULT_SETTINGS["signal_weights"][0], "DUPLICATE": 150}, "at most 100"),
    ],
    "signal_floors": [
        ({"NOT_A_SIGNAL": {"min_strength": 0.9, "min_score": 60}}, "Keys must be signal types"),
        ({"DUPLICATE": {"min_score": 60}}, "must look like"),
        ({"DUPLICATE": {"min_strength": 1.5, "min_score": 60}}, "at most 1"),
        ({"DUPLICATE": {"min_strength": 0.9, "min_score": 60.5}}, "whole number"),
    ],
}


class SettingValidatorTests(SimpleTestCase):
    def test_every_setting_has_a_validator_and_rejection_cases(self):
        self.assertEqual(set(VALIDATORS), set(DEFAULT_SETTINGS))
        self.assertEqual(set(INVALID), set(DEFAULT_SETTINGS))

    def test_every_default_passes_its_own_validator(self):
        for key, (default, _, _) in DEFAULT_SETTINGS.items():
            with self.subTest(key=key):
                validate_setting(key, default)

    def test_invalid_values_are_rejected_with_a_readable_reason(self):
        for key, cases in INVALID.items():
            for value, message in cases:
                with self.subTest(key=key, value=value):
                    with self.assertRaises(ValidationError) as caught:
                        validate_setting(key, value)
                    self.assertIn(message, str(caught.exception.detail))

    def test_values_are_cleaned(self):
        self.assertEqual(validate_setting("working_days", [4, 0, 2]), [0, 2, 4])          # sorted
        self.assertEqual(validate_setting("timezone", "  Europe/London "), "Europe/London")
        self.assertEqual(validate_setting("duplicate_threshold", 85.0), 85)                 # whole number kept as int
        self.assertIsInstance(validate_setting("duplicate_threshold", 85.0), int)
