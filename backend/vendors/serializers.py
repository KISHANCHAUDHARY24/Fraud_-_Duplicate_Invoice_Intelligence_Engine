from rest_framework import serializers

from .models import Vendor, VendorBankAccount


class BankAccountSerializer(serializers.ModelSerializer):
    """Masked view only. The hash and the full number are never returned."""

    masked_account = serializers.CharField(read_only=True)
    added_by_name = serializers.SerializerMethodField()

    class Meta:
        model = VendorBankAccount
        fields = ("id", "bank_name", "masked_account", "is_active", "valid_from", "valid_to",
                  "added_by_name", "created_at")
        read_only_fields = fields

    def get_added_by_name(self, account):
        return str(account.added_by) if account.added_by_id else None


class BankAccountCreateSerializer(serializers.Serializer):
    bank_name = serializers.CharField(max_length=100)
    account_number = serializers.CharField(max_length=50, write_only=True)


class VendorSerializer(serializers.ModelSerializer):
    """Read representation. invoice_count / total_spending are annotated by the list queryset."""

    active_bank_account = serializers.SerializerMethodField()
    invoice_count = serializers.IntegerField(read_only=True, required=False)
    total_spending = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True, required=False)

    class Meta:
        model = Vendor
        fields = ("id", "vendor_name", "registration_number", "address", "email", "phone", "status",
                  "active_bank_account", "invoice_count", "total_spending", "created_at", "updated_at")
        read_only_fields = fields

    def get_active_bank_account(self, vendor):
        # Use the prefetched list when available (list view) to avoid one query per vendor.
        accounts = getattr(vendor, "active_accounts", None)
        account = accounts[0] if accounts else (None if accounts is not None else vendor.active_bank_account)
        return {"bank_name": account.bank_name, "masked_account": account.masked_account} if account else None


class VendorWriteSerializer(serializers.ModelSerializer):
    # Optional first bank account, only on create.
    bank_name = serializers.CharField(max_length=100, required=False, write_only=True)
    account_number = serializers.CharField(max_length=50, required=False, write_only=True)

    class Meta:
        model = Vendor
        fields = ("vendor_name", "registration_number", "address", "email", "phone", "status",
                  "bank_name", "account_number")
        extra_kwargs = {"registration_number": {"required": False, "allow_null": True, "allow_blank": True}}

    def validate_vendor_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Vendor name must be at least 2 characters.")
        return value

    def validate(self, attrs):
        if self.instance is not None and ("bank_name" in attrs or "account_number" in attrs):
            raise serializers.ValidationError(
                {"account_number": "Use POST /api/vendors/{id}/bank-accounts/ to change bank details."}
            )
        if bool(attrs.get("bank_name")) != bool(attrs.get("account_number")):
            raise serializers.ValidationError({"account_number": "Provide both bank_name and account_number, or neither."})
        return attrs
