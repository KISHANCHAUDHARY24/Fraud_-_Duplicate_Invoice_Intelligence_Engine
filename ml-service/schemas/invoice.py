from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class InvoiceSnapshot(BaseModel):
    """
    The invoice fields the ML service needs. Django sends one for the invoice being
    analysed and one per candidate invoice. Extra fields are ignored so Django can
    add information later without breaking this service.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    id: int | None = Field(default=None, description="Django invoice id")
    invoice_number: str = Field(min_length=1, max_length=50, examples=["INV-1001"])
    vendor_id: int | None = Field(default=None, examples=[4])
    vendor_name: str = Field(min_length=1, max_length=200, examples=["ACME Corp"])
    amount: float = Field(gt=0, le=1_000_000_000_000, examples=[5000.0])
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    invoice_date: date = Field(examples=["2026-09-01"])
    description: str = Field(default="", max_length=2000, examples=["Software licence"])
