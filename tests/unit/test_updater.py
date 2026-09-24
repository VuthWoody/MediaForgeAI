"""Unit tests for core.updater."""

from unittest.mock import MagicMock, patch

from core.updater import YtDlpUpdater


def test_updater_get_version() -> None:
    ver = YtDlpUpdater.get_current_version()
    assert isinstance(ver, str)
    assert len(ver) > 0


def test_updater_check_online_update_available() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "info": {"version": "2099.01.01"}
    }

    with patch("requests.get", return_value=mock_resp):
        res = YtDlpUpdater.check_for_update()
        assert res["latest"] == "2099.01.01"
        assert res["update_available"] is True


def test_updater_check_offline_resilience() -> None:
    with patch("requests.get", side_effect=RuntimeError("Network is disconnected")):
        res = YtDlpUpdater.check_for_update()
        assert res["update_available"] is False
        assert "Network is disconnected" in str(res["error"])
