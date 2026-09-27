from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase

from audit.models import AuditLog
from common.test_utils import make_user, make_vendor
from common.text import normalize_vendor_name

from .models import VendorBankAccount
from .services import add_bank_account, hash_account_number


class NormalizeVendorNameTests(SimpleTestCase):
    def test_variants_of_the_same_vendor_normalise_equally(self):
        for name in ["ACME Corp", "ACME Corp.", "ACME Corporation", "ACME CORP", "acme, inc."]:
            with self.subTest(name=name):
                self.assertEqual(normalize_vendor_name(name), "acme")

    def test_multi_word_names_keep_their_words(self):
        self.assertEqual(normalize_vendor_name("Global Tech Solutions Pvt. Ltd."), "global tech solutions")

    def test_name_made_only_of_suffixes_is_not_emptied(self):
        self.assertEqual(normalize_vendor_name("Company Limited"), "company limited")


class VendorModelTests(TestCase):
    def test_normalized_name_is_set_on_save(self):
        self.assertEqual(make_vendor(vendor_name="ACME Corporation").normalized_name, "acme")

    def test_many_vendors_may_have_no_registration_number(self):
        make_vendor(registration_number="")
        make_vendor(registration_number="   ")  # both stored as NULL, so no unique clash

    def test_registration_number_is_unique(self):
        make_vendor(registration_number="REG-1")
        with self.assertRaises(IntegrityError):
            make_vendor(registration_number="REG-1")


class BankAccountTests(TestCase):
    def setUp(self):
        self.vendor = make_vendor(vendor_name="ACME Corp")
        self.admin = make_user("ADMIN")

    def test_full_account_number_is_never_stored(self):
        account = add_bank_account(self.vendor, "HDFC Bank", "1234 5678 9012", self.admin)
        self.assertEqual(account.account_last4, "9012")
        self.assertEqual(account.masked_account, "****9012")
        self.assertEqual(len(account.account_hash), 64)
        stored = " ".join(str(value) for value in VendorBankAccount.objects.values().first().values())
        self.assertNotIn("123456789012", stored)

    def test_same_number_gives_same_hash_regardless_of_formatting(self):
        self.assertEqual(hash_account_number("1234-5678-9012"), hash_account_number("123456789012"))
        self.assertNotEqual(hash_account_number("123456789012"), hash_account_number("123456789013"))

    def test_new_account_closes_previous_one_and_is_audited(self):
        first = add_bank_account(self.vendor, "HDFC Bank", "111122223333", self.admin)
        second = add_bank_account(self.vendor, "ICICI Bank", "444455556666", self.admin)
        first.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertIsNotNone(first.valid_to)
        self.assertEqual(self.vendor.active_bank_account, second)

        entry = AuditLog.objects.get(action=AuditLog.Action.VENDOR_BANK_ACCOUNT_CHANGED)
        self.assertEqual(entry.old_value, {"bank_account": "HDFC Bank ****3333"})
        self.assertNotIn("444455556666", str(entry.new_value))

    def test_re_adding_the_active_account_is_rejected(self):
        add_bank_account(self.vendor, "HDFC Bank", "111122223333")
        with self.assertRaises(ValidationError):
            add_bank_account(self.vendor, "HDFC Bank", "1111-2222-3333")

    def test_invalid_account_number_is_rejected(self):
        for bad in ["", "12ab!", "123"]:
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                add_bank_account(self.vendor, "HDFC Bank", bad)

    def test_database_allows_only_one_active_account(self):
        VendorBankAccount.objects.create(vendor=self.vendor, bank_name="A", account_last4="1111", account_hash="a" * 64)
        with self.assertRaises(IntegrityError):
            VendorBankAccount.objects.create(vendor=self.vendor, bank_name="B", account_last4="2222", account_hash="b" * 64)
