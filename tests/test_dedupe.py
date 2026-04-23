from scrapers.models import Company
from scrapers.utils.dedupe import dedupe, FUZZY_THRESHOLD
from scrapers.utils.normalize import normalize_company_name


def test_normalize_strips_suffixes():
    assert normalize_company_name("Acme Construction Ltd.") == "acme construction"
    assert normalize_company_name("Acme Construction Limited") == "acme construction"
    assert normalize_company_name("Acme Construction Inc.") == "acme construction"


def test_dedupe_exact_match_merges_sources():
    a = Company(name="Acme Ltd", country="Jamaica", source="JMEA", email="a@acme.jm")
    b = Company(name="Acme Limited", country="Jamaica", source="PSOJ", phone="12345")
    out = dedupe([a, b])
    assert len(out) == 1
    assert out[0].email == "a@acme.jm"
    assert out[0].phone == "12345"
    assert "PSOJ" in (out[0].notes or "")


def test_dedupe_keeps_different_countries_apart():
    a = Company(name="Acme Ltd", country="Jamaica", source="JMEA")
    b = Company(name="Acme Ltd", country="Trinidad", source="TTMA")
    assert len(dedupe([a, b])) == 2


def test_fuzzy_match_catches_trading_name_variants():
    a = Company(name="Caribbean Steel Works Limited", country="Jamaica", source="JMEA")
    b = Company(name="Caribbean Steelworks Ltd", country="Jamaica", source="PSOJ")
    out = dedupe([a, b])
    assert len(out) == 1


def test_fuzzy_threshold_rejects_unrelated():
    a = Company(name="Acme Holdings", country="Jamaica", source="JMEA")
    b = Company(name="Zulu Holdings", country="Jamaica", source="PSOJ")
    assert len(dedupe([a, b])) == 2
