import pytest
from receipt_parser import ReceiptParser


@pytest.fixture
def parser():
    return ReceiptParser()


SAMPLES = [
    ("Netflix subscription renewed for ₹499. Next billing date: 25/01/2024", "Netflix", 499.0),
    ("Your Spotify Premium invoice: Rs 199 paid on 10-01-2024", "Spotify Premium", 199.0),
    ("Electricity Bill from MSEB amount: ₹1200 due on 25/01/2024", "MSEB", 1200.0),
    ("Assignment due: 15/02/2024 for CS101 project", "CS101 project", None),
    ("Invoice: AMAZON PAY amount $12.99 date 2024-01-05", "AMAZON PAY", 12.99),
    ("Payment receipt from YOUTUBE PREMIUM price: INR 139.00", "YOUTUBE PREMIUM", 139.0),
    ("Your plan renewal receipt — Disney+ Hotstar Rs. 149", "Disney+ Hotstar", 149.0),
    ("Pay by 02/02/2024 to avoid late fees — Water Board", "Water Board", None),
    ("Job application deadline is 05-02-2024 — ACME Corp", "ACME Corp", None),
    ("Statement: Credit Card bill amount: 3500 rupees", "Statement", 3500.0),
]


def test_parse_text_receipt(parser: ReceiptParser):
    for text, expected_merchant, expected_amount in SAMPLES:
        result = parser.parse_text_receipt(text)
        assert result["merchant"]
        if expected_amount is not None:
            assert abs(result["amount"] - expected_amount) < 0.01


