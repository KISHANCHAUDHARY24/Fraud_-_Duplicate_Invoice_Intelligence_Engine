from django.test import TestCase

from .defaults import DEFAULT_SETTINGS
from .models import SystemSetting
from .services import get_all_settings, get_setting


class SystemSettingTests(TestCase):
    def test_every_default_is_seeded_by_migration(self):
        self.assertEqual(set(SystemSetting.objects.values_list("key", flat=True)), set(DEFAULT_SETTINGS))

    def test_duplicate_weights_add_up_to_one(self):
        self.assertAlmostEqual(sum(get_setting("duplicate_weights").values()), 1.0)

    def test_risk_level_thresholds_are_increasing(self):
        levels = get_setting("risk_level_thresholds")
        self.assertLess(levels["medium"], levels["high"])
        self.assertLess(levels["high"], levels["critical"])

    def test_changed_value_is_returned(self):
        SystemSetting.objects.filter(key="approval_threshold").update(value=25000)
        self.assertEqual(get_setting("approval_threshold"), 25000)
        self.assertEqual(get_all_settings()["approval_threshold"], 25000)

    def test_missing_row_falls_back_to_default(self):
        SystemSetting.objects.filter(key="split_window_days").delete()
        self.assertEqual(get_setting("split_window_days"), 7)

    def test_unknown_key_is_an_error(self):
        with self.assertRaises(KeyError):
            get_setting("does_not_exist")
