from services.cloud.quark_service import QuarkDriveService
from domain.cloud import CloudFile


def test_parse_share_url_with_password():
    pwd_id, passcode = QuarkDriveService.parse_share_url(
        "https://pan.quark.cn/s/abc123xyz?pwd=59hb"
    )
    assert pwd_id == "abc123xyz"
    assert passcode == "59hb"


def test_parse_share_url_without_password():
    pwd_id, passcode = QuarkDriveService.parse_share_url(
        "https://pan.quark.cn/s/abc123xyz#/list/share"
    )
    assert pwd_id == "abc123xyz"
    assert passcode == ""


def test_ensure_share_save_folder_uses_existing(monkeypatch):
    monkeypatch.setattr(
        QuarkDriveService,
        "get_file_list",
        lambda token, parent_id='0': ([CloudFile(file_id="fid_exist", parent_id='0', name="Harmony", file_type="folder")], None),
    )

    created = {"called": False}

    def _create(*args, **kwargs):
        created["called"] = True
        return "fid_new", None

    monkeypatch.setattr(QuarkDriveService, "create_folder", _create)

    fid, updated = QuarkDriveService.ensure_share_save_folder("cookie")
    assert fid == "fid_exist"
    assert updated is None
    assert created["called"] is False


def test_ensure_share_save_folder_creates_when_missing(monkeypatch):
    monkeypatch.setattr(
        QuarkDriveService,
        "get_file_list",
        lambda token, parent_id='0': ([], None),
    )
    monkeypatch.setattr(
        QuarkDriveService,
        "create_folder",
        lambda token, folder_name, parent_id='0': ("fid_new", "cookie_new"),
    )

    fid, updated = QuarkDriveService.ensure_share_save_folder("cookie_old")
    assert fid == "fid_new"
    assert updated == "cookie_new"
