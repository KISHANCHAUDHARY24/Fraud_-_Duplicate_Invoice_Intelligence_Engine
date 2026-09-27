import math
from datetime import date, datetime, timezone

import pytest

from schemas.fraud import BankContext, RuleConfig, VendorContext
from services.feature_engineering import FEATURE_NAMES, build_features, is_round_amount, submission_time, z_score

from .factories import IST, SUNDAY_0217_IST, TUESDAY_11AM_IST, history, invoice

CONFIG = RuleConfig()


def features(inv=None, vendor=None, bank=None, recent=(), duplicate_score=0.0, config=CONFIG):
    return build_features(inv or invoice(), vendor or VendorContext(), bank or BankContext(), list(recent),
                          config, duplicate_score)


def test_feature_names_and_order_are_stable():
    # The trained model (Phase 7) depends on this exact order.
    assert list(features()) == FEATURE_NAMES
    assert all(isinstance(value, float) for value in features().values())


def test_working_time_features():
    normal = features(invoice(submission_datetime=TUESDAY_11AM_IST))
    assert (normal["submission_hour"], normal["day_of_week"], normal["is_weekend"], normal["is_outside_hours"]) == (11, 1, 0, 0)
    odd = features(invoice(submission_datetime=SUNDAY_0217_IST))
    assert odd["day_of_week"] == 6 and odd["is_weekend"] == 1 and odd["is_outside_hours"] == 1
    assert odd["submission_hour"] == pytest.approx(2 + 17 / 60, abs=0.001)


def test_submission_time_is_converted_to_company_timezone():
    # 20:47 UTC on Saturday is 02:17 on Sunday in India.
    utc = datetime(2026, 9, 19, 20, 47, tzinfo=timezone.utc)
    when = submission_time(invoice(submission_datetime=utc), CONFIG)
    assert when.label == "Sunday 02:17" and not when.is_working_day
    london = submission_time(invoice(submission_datetime=utc), RuleConfig(timezone="Europe/London"))
    assert london.label == "Saturday 21:47"


def test_working_days_are_configurable():
    saturday_noon = invoice(submission_datetime=datetime(2026, 9, 19, 12, 0, tzinfo=IST))
    assert features(saturday_noon)["is_weekend"] == 1
    six_day_week = RuleConfig(working_days=[0, 1, 2, 3, 4, 5])
    assert features(saturday_noon, config=six_day_week)["is_weekend"] == 0


def test_cyclical_encoding_keeps_midnight_close():
    def hour_point(hour, minute):
        f = features(invoice(submission_datetime=datetime(2026, 9, 15, hour, minute, tzinfo=IST)))
        return f["hour_sin"], f["hour_cos"]

    def distance(a, b):
        return math.dist(a, b)

    # 23:30 and 00:30 are one hour apart in real life, so they must be close as features,
    # much closer than 11:30 and 12:30 are to 23:30.
    assert distance(hour_point(23, 30), hour_point(0, 30)) == pytest.approx(distance(hour_point(11, 30), hour_point(12, 30)))
    assert distance(hour_point(23, 30), hour_point(0, 30)) < distance(hour_point(23, 30), hour_point(11, 30))


def test_amount_features():
    f = features(invoice(amount=9900), VendorContext(vendor_avg_amount=5000, vendor_std_amount=1000,
                                                     company_avg_amount=4000, company_std_amount=2000))
    assert f["log_amount"] == pytest.approx(math.log1p(9900))
    assert f["amount_dev_vendor"] == pytest.approx(4.9)
    assert f["amount_dev_company"] == pytest.approx(2.95)
    assert f["threshold_distance"] == pytest.approx(0.01)


def test_z_score_edge_cases():
    assert z_score(100, None, None) == 0.0
    assert z_score(100, 50, 0) == 0.0
    assert z_score(10_000, 100, 1) == 10.0   # capped


@pytest.mark.parametrize("amount, expected", [(5000, True), (10000, True), (5000.5, False), (999, False), (1000, True)])
def test_round_amount(amount, expected):
    assert is_round_amount(amount, 1000) is expected


def test_history_features():
    recent = [history(1, 500, date(2026, 9, 15)), history(2, 700, date(2026, 9, 15)), history(3, 900, date(2026, 9, 1))]
    f = features(vendor=VendorContext(invoices_last_30_days=4, days_since_previous_invoice=None), recent=recent)
    assert f["same_day_invoice_count"] == 2
    assert f["vendor_invoice_frequency"] == 4
    assert f["days_since_previous_invoice"] == 365  # "no previous invoice" is encoded as the cap


def test_bank_and_duplicate_features():
    changed = BankContext(current_account_masked="****4821", current_account_age_days=12, previous_account_masked="****1111")
    old_change = BankContext(current_account_masked="****4821", current_account_age_days=200, previous_account_masked="****1111")
    assert features(bank=changed)["bank_account_changed"] == 1
    assert features(bank=old_change)["bank_account_changed"] == 0
    assert features(duplicate_score=94)["duplicate_similarity"] == pytest.approx(0.94)
