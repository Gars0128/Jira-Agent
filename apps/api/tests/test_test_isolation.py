import httpx
import pytest


def test_live_environment_cannot_enable_jira_in_shared_fixture(settings):
    assert settings.public_demo is True
    assert settings.jira_dry_run is True
    assert not settings.jira_api_token.get_secret_value()
    assert not settings.jira_base_url


def test_network_requires_explicit_mock_transport():
    with httpx.Client() as client:
        with pytest.raises(AssertionError, match="External HTTP is disabled"):
            client.get("https://example.com")
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"mock": True})
        )
    ) as client:
        assert client.get("https://example.com").json() == {"mock": True}
