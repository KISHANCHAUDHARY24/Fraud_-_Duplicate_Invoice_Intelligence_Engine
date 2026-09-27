"""
python manage.py seed_data [--password P] [--reset] [--no-scenarios] [--noinput]

Creates the demo accounts, 8 fictional vendors, a year of normal invoice history and the five demo
scenarios (docs/testing.md §5). Start the ML service first so the scenarios are analysed by the real model.
Safe to run again: it only adds what is missing.
"""

import argparse
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from demo import seed
from demo.data import DEFAULT_PASSWORD, USERS
from fraud import ml_client


class Command(BaseCommand):
    help = "Load demo accounts, vendors, invoice history and the five demo scenarios (development only)."

    def add_arguments(self, parser):
        parser.add_argument("--password", help="Password for the demo accounts (default: $DEMO_PASSWORD or the documented demo password).")
        parser.add_argument("--reset", action="store_true", help="First delete existing demo invoices and vendors (demo data only).")
        parser.add_argument("--no-scenarios", action="store_true", help="Only accounts, vendors and history.")
        parser.add_argument("--noinput", "--no-input", action="store_false", dest="interactive",
                            help="Do not ask for confirmation (for --reset).")
        parser.add_argument("--allow-without-debug", action="store_true", help=argparse.SUPPRESS)  # tests only

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["allow_without_debug"]:
            raise CommandError("seed_data creates accounts with a known password. Run it only in development (DEBUG=True).")
        password = options["password"] or os.environ.get("DEMO_PASSWORD") or DEFAULT_PASSWORD

        if options["reset"]:
            counts = seed.demo_counts()
            if options["interactive"] and counts["invoices"] + counts["vendors"]:
                answer = input(f"Delete {counts['invoices']} demo invoices and {counts['vendors']} demo vendors? "
                               "Other data is not touched. Type 'yes' to continue: ")
                if answer.strip().lower() != "yes":
                    raise CommandError("Cancelled.")
            removed = seed.reset_demo()
            self.stdout.write(f"Removed {removed['invoices']} demo invoices and {removed['vendors']} demo vendors.")

        zone = seed.business_zone()
        today = seed.business_today(zone)
        try:
            users = seed.ensure_users(password)
        except seed.DemoConflict as error:
            raise CommandError(str(error))
        vendors = seed.ensure_vendors(users["ADMIN"], today)
        history = seed.seed_history(users, vendors, today, zone, seed.make_rng())
        self.stdout.write(f"Accounts: {len(users)} | vendors: {len(vendors)} | history invoices added: {history}")

        if not options["no_scenarios"]:
            health = ml_client.health()
            analyse = bool(health and health.get("model_loaded"))
            if not analyse:
                self.stdout.write(self.style.WARNING(
                    "The ML service is not reachable (or has no model): scenario invoices are created as DRAFTS.\n"
                    "Start it (ml-service: python -m uvicorn main:app --port 8001) and run seed_data again to analyse them."))
            results = seed.run_scenarios(users, vendors, today, zone, analyse=analyse)
            self._report(results)

        self.stdout.write("")
        self.stdout.write("Demo accounts (password: " + ("as given" if options["password"] or os.environ.get("DEMO_PASSWORD")
                                                          else DEFAULT_PASSWORD) + "):")
        for demo in USERS:
            self.stdout.write(f"  {demo.username:<11} {demo.role}")
        self.stdout.write(self.style.SUCCESS("Demo data ready. Risk scores are indicators for review, not findings of fraud."))

    def _report(self, results):
        self.stdout.write("")
        self.stdout.write("Demo scenarios")
        for result in results:
            mark = {True: "OK   ", False: "CHECK", None: "-    "}[result.ok]
            number = result.invoice.invoice_number if result.invoice else "-"
            self.stdout.write(f"  {mark} {result.number}. {result.title:<20} {number:<9} {result.outcome}")
            if result.ok is False:
                self.stdout.write(f"          expected: {result.expected}")
        if any(result.ok is False for result in results):
            self.stdout.write(self.style.WARNING(
                "Some scenarios did not give the expected result. Check that the settings are at their defaults "
                "and the trained model is loaded (see docs/testing.md section 5)."))

