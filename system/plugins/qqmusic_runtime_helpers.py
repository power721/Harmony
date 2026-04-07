from __future__ import annotations


def create_qqmusic_service(credential):
    from plugins.builtin.qqmusic.lib.legacy.qqmusic_service import QQMusicService

    return QQMusicService(credential)


def create_qqmusic_login_dialog(parent=None):
    from plugins.builtin.qqmusic.lib.login_dialog import QQMusicLoginDialog

    return QQMusicLoginDialog(parent)
