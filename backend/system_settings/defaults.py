"""
Default business-rule configuration (docs/database.md §2.14, docs/risk-scoring.md).

Each entry: key -> (default value, value type, description).
The values are copied into the SystemSetting table by migration 0002 and can
then be changed by an Admin. Code reads them with system_settings.services.get_setting().
"""

INT, DECIMAL, BOOL, STRING, JSON = "INT", "DECIMAL", "BOOL", "STRING", "JSON"

DEFAULT_SETTINGS = {
    # Approval rules
    "approval_threshold": (10000, DECIMAL, "Invoices above this amount require manager approval."),
    "near_threshold_percent": (10, DECIMAL, "An amount within this % below the approval threshold is 'close to threshold'."),
    "auto_approve_low_risk": (True, BOOL, "Automatically approve LOW-risk invoices at or below the approval threshold."),
    # Duplicate detection
    "duplicate_threshold": (80, INT, "Combined similarity (0-100) at or above which an invoice is a possible duplicate."),
    "duplicate_weights": (
        {"invoice_number": 0.30, "vendor": 0.25, "amount": 0.20, "date": 0.15, "description": 0.10},
        JSON, "Weights of each similarity component. Must add up to 1.0.",
    ),
    "duplicate_lookback_days": (180, INT, "How many days back to look for duplicate candidates."),
    # Working time
    "working_hours": ({"start": "08:00", "end": "19:00"}, JSON, "Normal submission hours (24h clock)."),
    "working_days": ([0, 1, 2, 3, 4], JSON, "Normal working days, Monday=0 ... Sunday=6."),
    "timezone": ("Asia/Kolkata", STRING, "Timezone used to judge working hours (IANA name)."),
    # Pattern rules
    "split_window_days": (7, INT, "Look-back window (days) for split-purchase detection."),
    "split_min_invoices": (2, INT, "Other qualifying invoices (besides the current one) needed to flag a split purchase."),
    "round_amount_base": (1000, INT, "Amounts that are exact multiples of this value count as round."),
    "bank_change_window_days": (30, INT, "A vendor bank account added within this many days counts as a recent change."),
    "ml_anomaly_threshold": (0.6, DECIMAL, "Isolation Forest anomaly score (0-1) at or above which the ML signal fires."),
    # Risk scoring
    "risk_level_thresholds": (
        {"medium": 30, "high": 60, "critical": 80}, JSON,
        "Minimum score for each risk level. Below 'medium' is LOW.",
    ),
    "signal_weights": (
        {
            "DUPLICATE": 30, "BANK_ACCOUNT_CHANGE": 20, "SPLIT_PURCHASE": 20,
            "AMOUNT_ANOMALY": 15, "THRESHOLD_PROXIMITY": 15, "ML_ANOMALY": 15,
            "TIME_ANOMALY": 10, "VENDOR_ANOMALY": 10, "ROUND_AMOUNT": 5,
        },
        JSON, "Maximum points each signal can add to the risk score.",
    ),
    "signal_floors": (
        {
            "DUPLICATE": {"min_strength": 0.9, "min_score": 60},
            "BANK_ACCOUNT_CHANGE": {"min_strength": 0.0, "min_score": 60},
            "SPLIT_PURCHASE": {"min_strength": 0.0, "min_score": 30},
            # Phase 16: a single strong ML or amount signal must reach review (scripts/evaluate_hybrid.py).
            "ML_ANOMALY": {"min_strength": 0.8, "min_score": 30},
            "AMOUNT_ANOMALY": {"min_strength": 1.0, "min_score": 30},
        },
        JSON, "Minimum risk score when a serious signal is present (escalation floors).",
    ),
}
