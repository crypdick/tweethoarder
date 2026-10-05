"""Verify pytest cannot inherit a user's Twitter account or archive paths."""

from pathlib import Path

import pytest

pytest_plugins = ("pytester",)


def test_suite_ignores_host_credentials_and_paths(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh pytest process must discard host auth and use temporary paths."""
    host_config = pytester.path / "host-config" / "tweethoarder"
    host_config.mkdir(parents=True)
    host_config.joinpath("config.toml").write_text(
        '[auth]\nauth_token = "example-secret"\nct0 = "example-csrf"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(host_config.parent))
    monkeypatch.setenv("XDG_DATA_HOME", str(pytester.path / "host-data"))
    monkeypatch.setenv("TWITTER_AUTH_TOKEN", "example-secret")
    monkeypatch.setenv("TWITTER_CT0", "example-csrf")
    monkeypatch.setenv("TWITTER_TWID", "example-user")
    pytester.makeconftest(Path(__file__).with_name("conftest.py").read_text())
    pytester.makepyfile(
        """
        import os
        from pathlib import Path
        import pytest
        from tweethoarder.auth.cookies import CookieError, resolve_cookies
        from tweethoarder.config import get_config_dir, get_data_dir

        def test_default_account_is_unavailable(tmp_path):
            assert not any(name in os.environ for name in (
                "TWITTER_AUTH_TOKEN", "TWITTER_CT0", "TWITTER_TWID"
            ))
            assert get_config_dir().is_relative_to(tmp_path)
            assert get_data_dir().is_relative_to(tmp_path)
            assert Path.home().is_relative_to(tmp_path)
            with pytest.raises(CookieError, match="No Twitter cookies found"):
                resolve_cookies()
        """
    )
    result = pytester.runpytest_subprocess("-q", "-o", "addopts=")
    result.assert_outcomes(passed=1)
