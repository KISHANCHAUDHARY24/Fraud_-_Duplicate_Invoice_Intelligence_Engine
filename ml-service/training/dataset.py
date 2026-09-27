"""
Synthetic invoice data for ACADEMIC DEMONSTRATION (docs/machine-learning.md §3).

This data is generated, not collected. It does not represent real corporate
fraud data. Its patterns reflect the assumptions written in this file.

Output (three tables, shaped like the Django database):
    vendors.csv         vendor_id, vendor_name, category, created_date
    bank_accounts.csv   vendor_id, account_id, valid_from
    invoices.csv        one row per invoice + is_injected_anomaly / anomaly_type labels

Normal behaviour deliberately contains realistic noise (late submissions,
legitimate bank changes, vendors that bill round retainers). Without noise the
anomalies would be trivially separable and evaluation metrics would be meaningless.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

import numpy as np
import pandas as pd

COMPANY_TZ = timezone(timedelta(hours=5, minutes=30))  # Asia/Kolkata (no DST)
APPROVAL_THRESHOLD = 10_000
CURRENCY = "USD"

CATEGORY_PHRASES = {
    "SOFTWARE": ["Software licence renewal", "Cloud hosting subscription", "SaaS user seats", "Database support contract"],
    "HARDWARE": ["Office computer equipment", "Laptop purchase", "Network switches", "Monitors and docking stations"],
    "SERVICES": ["Facility cleaning services", "Security guard services", "Courier services", "Pest control service"],
    "CONSULTING": ["IT consulting hours", "Audit advisory fees", "Legal consultation", "Tax advisory services"],
    "TRAVEL": ["Flight tickets", "Hotel accommodation", "Airport transfers", "Conference travel package"],
    "OFFICE_SUPPLIES": ["Stationery supplies", "Pantry supplies", "Office furniture", "Printing paper"],
    "MAINTENANCE": ["Air conditioning maintenance", "Elevator maintenance", "Electrical repairs", "Plumbing repairs"],
    "UTILITIES": ["Electricity charges", "Internet connectivity", "Water supply charges", "Telephone charges"],
    "MARKETING": ["Digital advertising campaign", "Event sponsorship", "Brochure printing", "Social media management"],
}
DEPARTMENTS = ["IT", "Finance", "Operations", "HR", "Sales", "Marketing", "Facilities"]
NAME_FIRST = ["Acme", "Global", "Apex", "Blue", "Crest", "Delta", "Everest", "Futura", "Granite", "Horizon", "Indigo",
              "Juniper", "Keystone", "Lotus", "Meridian", "Nimbus", "Orion", "Pinnacle", "Quantum", "Radiant",
              "Sterling", "Titan", "Unity", "Vertex", "Willow", "Zenith"]
NAME_SECOND = ["Tech", "Supplies", "Systems", "Logistics", "Consulting", "Traders", "Networks", "Facilities",
               "Digital", "Industries", "Partners", "Works"]
NAME_SUFFIX = ["Ltd", "Pvt Ltd", "Corp", "Inc", "LLC", "Solutions", "Services"]

# Share of rows per anomaly type, relative to the number of normal invoices (~5% in total).
ANOMALY_MIX = {
    "duplicate": 0.012,
    "split_purchase": 0.004,      # groups of 3 invoices -> ~1.2% of rows
    "off_hours": 0.008,
    "amount_spike": 0.008,
    "bank_change": 0.004,
    "threshold_hugging": 0.006,
}


@dataclass
class Vendor:
    vendor_id: int
    name: str
    prefix: str
    category: str
    median_amount: float
    sigma: float
    monthly_rate: float
    departments: list
    phrases: list
    round_billing: bool
    created: date
    accounts: list = field(default_factory=list)   # [(account_id, valid_from)]


class Generator:
    def __init__(self, n_vendors=60, start=date(2025, 3, 1), months=18, seed=42):
        self.rng = np.random.default_rng(seed)
        self.start = start
        self.end = start + timedelta(days=int(months * 30.4))
        self.n_vendors = n_vendors
        self.vendors: list[Vendor] = []
        self.rows: list[dict] = []
        self._next_account = 50_000_001

    # ------------------------------------------------------------------ helpers
    def _account(self, vendor: Vendor, valid_from: date):
        vendor.accounts.append((self._next_account, valid_from))
        self._next_account += 7_919  # spread the ids so last-4 digits differ
        vendor.accounts.sort(key=lambda acc: acc[1])

    def _random_date(self, low: date, high: date) -> date:
        return low + timedelta(days=int(self.rng.integers(0, max(1, (high - low).days))))

    def _normal_amount(self, vendor: Vendor) -> float:
        amount = float(np.exp(self.rng.normal(np.log(vendor.median_amount), vendor.sigma)))
        if vendor.round_billing:
            base = 1000 if amount >= 1000 else 100
            return float(max(base, round(amount / base) * base))
        return round(amount, 2)

    def _working_submission(self, invoice_date: date) -> datetime:
        """Entered 0-3 days after the invoice date, on a working day, during office hours."""
        day = invoice_date + timedelta(days=int(self.rng.integers(0, 4)))
        while day.weekday() >= 5:
            day += timedelta(days=1)
        hour = float(np.clip(self.rng.normal(13.0, 2.3), 8.1, 18.9))
        if self.rng.random() < 0.015:          # realistic noise: some legitimate late or Saturday work
            if self.rng.random() < 0.6:
                hour = float(self.rng.uniform(19.0, 21.5))
            else:
                day += timedelta(days=5 - day.weekday())   # the Saturday of that week
        return self._at(day, hour)

    def _odd_submission(self, invoice_date: date) -> datetime:
        """Night and/or weekend submission (injected anomaly)."""
        day = invoice_date + timedelta(days=int(self.rng.integers(0, 3)))
        kind = self.rng.random()
        if kind < 0.5:                                      # weekend night
            day += timedelta(days=(6 - day.weekday()) % 7)
            hour = float(self.rng.uniform(0.5, 5.0))
        elif kind < 0.75:                                   # weekday night
            while day.weekday() >= 5:
                day += timedelta(days=1)
            hour = float(self.rng.uniform(0.5, 5.0))
        else:                                               # weekend daytime
            day += timedelta(days=(6 - day.weekday()) % 7)
            hour = float(self.rng.uniform(10, 17))
        return self._at(day, hour)

    @staticmethod
    def _at(day: date, hour: float) -> datetime:
        minutes = int(round(hour * 60))
        return datetime.combine(day, time(min(23, minutes // 60), minutes % 60), tzinfo=COMPANY_TZ)

    def _row(self, vendor: Vendor, invoice_date: date, submitted: datetime, amount: float, description: str,
             department: str, label: str = "", number: str | None = None, group: int | None = None) -> dict:
        return {
            "vendor_id": vendor.vendor_id, "vendor_name": vendor.name, "invoice_date": invoice_date,
            "submission_datetime": submitted, "amount": round(float(amount), 2), "currency": CURRENCY,
            "description": description, "department": department, "purchase_category": vendor.category,
            "invoice_number": number, "is_injected_anomaly": int(bool(label)), "anomaly_type": label,
            "anomaly_group": group,
        }

    # ------------------------------------------------------------------ vendors
    def make_vendors(self):
        names = set()
        while len(names) < self.n_vendors:
            names.add(f"{self.rng.choice(NAME_FIRST)} {self.rng.choice(NAME_SECOND)} {self.rng.choice(NAME_SUFFIX)}")
        for vendor_id, name in enumerate(sorted(names), start=1):
            category = str(self.rng.choice(list(CATEGORY_PHRASES)))
            vendor = Vendor(
                vendor_id=vendor_id, name=name, prefix="".join(w[0] for w in name.split()[:2]).upper() + str(vendor_id),
                category=category,
                median_amount=float(np.clip(np.exp(self.rng.normal(7.5, 0.9)), 150, 25_000)),
                sigma=float(self.rng.uniform(0.15, 0.4)),
                monthly_rate=float(self.rng.uniform(1.0, 8.0)),
                departments=list(self.rng.choice(DEPARTMENTS, size=int(self.rng.integers(1, 3)), replace=False)),
                phrases=list(self.rng.choice(CATEGORY_PHRASES[category], size=2, replace=False)),
                round_billing=bool(self.rng.random() < 0.15),
                created=self.start - timedelta(days=int(self.rng.integers(30, 900))),
            )
            self._account(vendor, vendor.created)
            if self.rng.random() < 0.10:  # legitimate bank change (a normal business event)
                self._account(vendor, self._random_date(self.start + timedelta(days=60), self.end - timedelta(days=60)))
            self.vendors.append(vendor)

    # ------------------------------------------------------------------ normal invoices
    def make_normal_invoices(self):
        for vendor in self.vendors:
            day = self.start + timedelta(days=float(self.rng.exponential(30 / vendor.monthly_rate)))
            while day < self.end:
                self.rows.append(self._row(
                    vendor, day, self._working_submission(day), self._normal_amount(vendor),
                    str(self.rng.choice(vendor.phrases)), str(self.rng.choice(vendor.departments)),
                ))
                day += timedelta(days=max(1.0, float(self.rng.exponential(30 / vendor.monthly_rate))))

    # ------------------------------------------------------------------ anomalies
    def _count(self, kind: str, n_normal: int) -> int:
        return max(1, int(round(ANOMALY_MIX[kind] * n_normal)))

    def inject_duplicates(self, n):
        originals = [self.rows[i] for i in self.rng.choice(len(self.rows), size=n, replace=False)]
        for original in originals:
            vendor = self.vendors[original["vendor_id"] - 1]
            day = original["invoice_date"] + timedelta(days=int(self.rng.integers(0, 7)))
            description = original["description"]
            if self.rng.random() < 0.5:
                description = description + "s" if not description.endswith("s") else description.lower()
            row = self._row(vendor, day, self._working_submission(day), original["amount"], description,
                            original["department"], label="duplicate")
            row["duplicate_of"] = id(original)   # resolved to an invoice number after numbering
            self.rows.append(row)

    def inject_split_purchases(self, n_groups):
        for group in range(n_groups):
            vendor = self.vendors[int(self.rng.integers(len(self.vendors)))]
            first_day = self._random_date(self.start + timedelta(days=30), self.end - timedelta(days=10))
            department, phrase = str(self.rng.choice(vendor.departments)), str(self.rng.choice(vendor.phrases))
            for offset in sorted(self.rng.choice(6, size=3, replace=False)):
                day = first_day + timedelta(days=int(offset))
                self.rows.append(self._row(vendor, day, self._working_submission(day),
                                           float(self.rng.uniform(9_000, 9_990)), phrase, department,
                                           label="split_purchase", group=group))

    def inject_off_hours(self, n):
        for _ in range(n):
            vendor = self.vendors[int(self.rng.integers(len(self.vendors)))]
            day = self._random_date(self.start, self.end)
            self.rows.append(self._row(vendor, day, self._odd_submission(day), self._normal_amount(vendor),
                                       str(self.rng.choice(vendor.phrases)), str(self.rng.choice(vendor.departments)),
                                       label="off_hours"))

    def inject_amount_spikes(self, n):
        for _ in range(n):
            vendor = self.vendors[int(self.rng.integers(len(self.vendors)))]
            day = self._random_date(self.start + timedelta(days=60), self.end)
            self.rows.append(self._row(vendor, day, self._working_submission(day),
                                       vendor.median_amount * float(self.rng.uniform(5, 12)),
                                       str(self.rng.choice(vendor.phrases)), str(self.rng.choice(vendor.departments)),
                                       label="amount_spike"))

    def inject_bank_changes(self, n):
        """Payment redirection: the bank account changes, then a larger-than-usual invoice follows."""
        for _ in range(n):
            vendor = self.vendors[int(self.rng.integers(len(self.vendors)))]
            change_day = self._random_date(self.start + timedelta(days=60), self.end - timedelta(days=10))
            self._account(vendor, change_day)
            day = change_day + timedelta(days=int(self.rng.integers(1, 9)))
            self.rows.append(self._row(vendor, day, self._working_submission(day),
                                       vendor.median_amount * float(self.rng.uniform(1.5, 3.0)),
                                       str(self.rng.choice(vendor.phrases)), str(self.rng.choice(vendor.departments)),
                                       label="bank_change"))

    def inject_threshold_hugging(self, n):
        small_vendors = [v for v in self.vendors if v.median_amount < 3_000] or self.vendors
        for _ in range(n):
            vendor = small_vendors[int(self.rng.integers(len(small_vendors)))]
            day = self._random_date(self.start, self.end)
            self.rows.append(self._row(vendor, day, self._working_submission(day),
                                       float(self.rng.uniform(9_500, 9_999)), str(self.rng.choice(vendor.phrases)),
                                       str(self.rng.choice(vendor.departments)), label="threshold_hugging"))

    # ------------------------------------------------------------------ numbering
    def assign_invoice_numbers(self):
        """Sequential numbers per vendor; duplicates get a disguised copy of the original's number."""
        by_identity = {id(row): row for row in self.rows}
        normal_rows = [row for row in self.rows if row["anomaly_type"] != "duplicate"]
        normal_rows.sort(key=lambda row: (row["vendor_id"], row["invoice_date"], row["submission_datetime"]))
        counters = {}
        for row in normal_rows:
            counters[row["vendor_id"]] = counters.get(row["vendor_id"], 1000) + 1
            row["invoice_number"] = f"{self.vendors[row['vendor_id'] - 1].prefix}-{counters[row['vendor_id']]}"
        for row in self.rows:
            if row["anomaly_type"] == "duplicate":
                row["invoice_number"] = self._disguise(by_identity[row.pop("duplicate_of")]["invoice_number"])

    def _disguise(self, number: str) -> str:
        variants = [
            number.replace("-", ""),                              # AT5-1034 -> AT51034
            number.replace("-", " "),
            number[:-1] + {"1": "I", "0": "O", "5": "S"}.get(number[-1], number[-1] + "A"),
            number.lower(),
            number + "-A",
        ]
        return str(self.rng.choice(variants))

    # ------------------------------------------------------------------ run
    def generate(self):
        self.make_vendors()
        self.make_normal_invoices()
        n_normal = len(self.rows)
        self.inject_duplicates(self._count("duplicate", n_normal))
        self.inject_split_purchases(self._count("split_purchase", n_normal))
        self.inject_off_hours(self._count("off_hours", n_normal))
        self.inject_amount_spikes(self._count("amount_spike", n_normal))
        self.inject_bank_changes(self._count("bank_change", n_normal))
        self.inject_threshold_hugging(self._count("threshold_hugging", n_normal))
        self.assign_invoice_numbers()
        return self.tables()

    def _dirty_rows(self, invoices: pd.DataFrame) -> pd.DataFrame:
        """A few data-quality problems for the cleaning step to handle (NOT fraud labels)."""
        normal = invoices[invoices["anomaly_type"] == ""]
        copies = normal.sample(n=5, random_state=int(self.rng.integers(1_000_000))).copy()   # export glitch
        broken = normal.sample(n=3, random_state=int(self.rng.integers(1_000_000))).copy()
        broken["invoice_number"] = broken["invoice_number"] + "-X"
        broken.iloc[0, broken.columns.get_loc("amount")] = np.nan                    # missing amount
        broken.iloc[1, broken.columns.get_loc("amount")] = -50.0                     # impossible amount
        broken.iloc[2, broken.columns.get_loc("submission_datetime")] = "not-a-date"  # unreadable timestamp
        for frame in (copies, broken):
            frame["is_injected_anomaly"], frame["anomaly_type"], frame["anomaly_group"] = 0, "", pd.NA
        return pd.concat([copies, broken])

    def tables(self):
        invoices = pd.DataFrame(self.rows)
        invoices = invoices[invoices["invoice_date"] < self.end]
        invoices["submission_datetime"] = invoices["submission_datetime"].map(lambda d: d.isoformat())
        invoices = pd.concat([invoices, self._dirty_rows(invoices)])
        invoices = invoices.sort_values(["submission_datetime", "vendor_id"], kind="stable").reset_index(drop=True)
        invoices.insert(0, "invoice_id", range(1, len(invoices) + 1))
        invoices["anomaly_group"] = invoices["anomaly_group"].astype("Int64")
        vendors = pd.DataFrame([{"vendor_id": v.vendor_id, "vendor_name": v.name, "category": v.category,
                                 "created_date": v.created} for v in self.vendors])
        accounts = pd.DataFrame([{"vendor_id": v.vendor_id, "account_id": acc, "valid_from": since}
                                 for v in self.vendors for acc, since in v.accounts])
        return {"vendors": vendors, "bank_accounts": accounts, "invoices": invoices}


def generate(n_vendors=60, start=date(2025, 3, 1), months=18, seed=42):
    return Generator(n_vendors=n_vendors, start=start, months=months, seed=seed).generate()


def save(tables, directory):
    directory.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(directory / f"synthetic_{name}.csv", index=False)


def load(directory):
    return {
        "vendors": pd.read_csv(directory / "synthetic_vendors.csv", parse_dates=["created_date"]),
        "bank_accounts": pd.read_csv(directory / "synthetic_bank_accounts.csv", parse_dates=["valid_from"]),
        "invoices": pd.read_csv(directory / "synthetic_invoices.csv", keep_default_na=False,
                                dtype={"invoice_number": str, "anomaly_type": str}),
    }
