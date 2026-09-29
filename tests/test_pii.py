from app.pii import scrub_text
from app.logging_config import scrub_event


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
        "(090) 123 4567",
        "+84 (90) 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd_and_payment_cards() -> None:
    samples = (
        ("CCCD 001201234567", "001201234567", "REDACTED_CCCD"),
        ("Card 4111 1111 1111 1111", "4111 1111 1111 1111", "REDACTED_CREDIT_CARD"),
        ("Card 5555-5555-5555-4444", "5555-5555-5555-4444", "REDACTED_CREDIT_CARD"),
    )

    for text, raw_value, marker in samples:
        out = scrub_text(text)
        assert raw_value not in out
        assert marker in out


def test_scrub_event_handles_nested_payload_values() -> None:
    event = {
        "event": "request_received",
        "payload": {
            "contacts": [
                {"email": "student@example.test"},
                {"phones": ("090 123 4567", "+84 (90) 765 4321")},
            ],
            "identity": {"cccd": "001201234567"},
        },
    }

    scrubbed = scrub_event(None, "info", event)
    rendered = repr(scrubbed)

    assert "student@example.test" not in rendered
    assert "090 123 4567" not in rendered
    assert "+84 (90) 765 4321" not in rendered
    assert "001201234567" not in rendered
    assert "REDACTED_EMAIL" in rendered
    assert "REDACTED_PHONE_VN" in rendered
    assert "REDACTED_CCCD" in rendered
