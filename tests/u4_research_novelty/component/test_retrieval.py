import pytest

from backend.modules.research.errors import ResearchError
from backend.modules.research.retrieval import extract, validate_target


@pytest.mark.parametrize("address", ["127.0.0.1", "::1", "10.0.0.1", "169.254.169.254"])
def test_private_dns_targets_refused(address):
    with pytest.raises(ResearchError, match="SOURCE_INELIGIBLE"):
        validate_target(
            "https://arxiv.org/paper", allowed_hosts={"arxiv.org"}, resolved_addresses=[address]
        )


def test_approved_target_and_redirect_refusal():
    args = {"allowed_hosts": {"arxiv.org"}, "resolved_addresses": ["8.8.8.8"]}
    assert validate_target("https://arxiv.org/paper", **args)["addresses"] == ("8.8.8.8",)
    for url in [
        "http://arxiv.org/paper",
        "https://other.example/paper",
        "https://user@arxiv.org/paper",
        "https://arxiv.org:8443/paper",
    ]:
        with pytest.raises(ResearchError):
            validate_target(url, **args)
    with pytest.raises(ResearchError):
        validate_target("https://arxiv.org/paper", redirected=True, **args)


def test_extraction_refusals_and_truncation():
    assert extract(b"%PDF", "application/pdf")["disposition"] == "unsupported"
    assert extract(b"\xff", "text/plain")["disposition"] == "malformed"
    assert extract(b"abcde", "text/plain", limit=3) == {"disposition": "truncated", "text": "abc"}
    assert extract("한글".encode(), "text/plain")["disposition"] == "extracted"
