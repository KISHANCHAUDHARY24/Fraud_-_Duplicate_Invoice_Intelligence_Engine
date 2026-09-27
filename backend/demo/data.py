"""
Demo data definitions for `python manage.py seed_data` (docs/user-guide.md "Demo accounts").
All companies and people are fictional. Demo records are recognisable, so --reset can remove
only them: users have an @demo.local e-mail, vendors a DEMO- registration number.
"""

from dataclasses import dataclass

DEMO_EMAIL_DOMAIN = "demo.local"
DEMO_REG_PREFIX = "DEMO-"
DEFAULT_PASSWORD = "Demo@12345"   # documented in the user guide; a DEMO password, never a real one


@dataclass(frozen=True)
class DemoUser:
    username: str
    role: str
    first_name: str
    last_name: str
    department: str = ""


USERS = [
    DemoUser("admin", "ADMIN", "Neha", "Verma"),
    DemoUser("ap_officer", "AP_OFFICER", "Asha", "Patel", "IT"),
    DemoUser("manager", "MANAGER", "Rahul", "Mehta", "IT"),
    DemoUser("auditor", "AUDITOR", "Meera", "Iyer"),
]


@dataclass(frozen=True)
class DemoVendor:
    code: str               # also the prefix of its history invoice numbers
    name: str
    typical_amount: int     # history amounts vary ±20% around this
    description: str
    category: str
    department: str
    bank: str


VENDORS = [
    DemoVendor("AC", "ACME Corp", 1500, "Office computer equipment", "HARDWARE", "IT", "HDFC Bank"),
    DemoVendor("BP", "Bluepeak Consulting", 4000, "IT consulting hours", "CONSULTING", "IT", "ICICI Bank"),
    DemoVendor("CS", "Cobalt Software Ltd", 4800, "Software licence renewal", "SOFTWARE", "IT", "Axis Bank"),
    DemoVendor("DF", "Delta Facility Services", 2600, "Facility cleaning services", "MAINTENANCE", "Operations", "HDFC Bank"),
    DemoVendor("EV", "Evergreen Stationers", 700, "Stationery supplies", "OFFICE_SUPPLIES", "Administration", "SBI"),
    DemoVendor("FL", "Falcon Logistics", 3200, "Courier services", "SERVICES", "Operations", "Kotak Bank"),
    DemoVendor("GM", "Greenline Media", 5200, "Digital advertising campaign", "MARKETING", "Marketing", "Yes Bank"),
    DemoVendor("HU", "Harbor Utilities", 1800, "Electricity and water", "UTILITIES", "Administration", "SBI"),
]

HISTORY_MONTHS = 12
HISTORY_PER_MONTH = 2
