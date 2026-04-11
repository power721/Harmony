from __future__ import annotations


def _get_theme_manager():
    from system.theme import ThemeManager

    try:
        return ThemeManager.instance()
    except ValueError:
        return None


class PluginThemeBridgeImpl:
    def register_widget(self, widget) -> None:
        manager = _get_theme_manager()
        if manager is not None:
            manager.register_widget(widget)

    def get_qss(self, template: str) -> str:
        manager = _get_theme_manager()
        if manager is None:
            return template
        return manager.get_qss(template)

    def current_theme(self):
        from system.theme import PRESET_THEMES

        manager = _get_theme_manager()
        if manager is None:
            return PRESET_THEMES["dark"]
        return manager.current_theme

    def get_popup_surface_style(self) -> str:
        manager = _get_theme_manager()
        if manager is None:
            return ""
        return manager.get_themed_popup_surface_style()

    def get_completer_popup_style(self) -> str:
        manager = _get_theme_manager()
        if manager is None:
            return ""
        return manager.get_themed_completer_popup_style()


class PluginDialogBridgeImpl:
    def information(self, parent, title: str, message: str, buttons=None, default_button=None):
        from ui.dialogs.message_dialog import MessageDialog

        if buttons is None:
            return MessageDialog.information(parent, title, message)
        return MessageDialog.information(parent, title, message, buttons, default_button)

    def warning(self, parent, title: str, message: str, buttons=None, default_button=None):
        from ui.dialogs.message_dialog import MessageDialog

        if buttons is None:
            return MessageDialog.warning(parent, title, message)
        return MessageDialog.warning(parent, title, message, buttons, default_button)

    def question(self, parent, title: str, message: str, buttons, default_button):
        from ui.dialogs.message_dialog import MessageDialog

        return MessageDialog.question(parent, title, message, buttons, default_button)

    def critical(self, parent, title: str, message: str, buttons=None, default_button=None):
        from ui.dialogs.message_dialog import MessageDialog

        if buttons is None:
            return MessageDialog.critical(parent, title, message)
        return MessageDialog.critical(parent, title, message, buttons, default_button)

    def show_cover_preview(
        self,
        parent,
        image_source: str,
        title: str = "",
        request_headers: dict | None = None,
    ):
        from ui.dialogs.cover_preview_dialog import show_cover_preview

        return show_cover_preview(
            parent,
            image_source,
            title=title,
            request_headers=request_headers,
        )

    def setup_title_bar(self, dialog, container_layout, title: str, **kwargs):
        from ui.dialogs.dialog_title_bar import setup_equalizer_title_layout

        return setup_equalizer_title_layout(dialog, container_layout, title, **kwargs)


def register_themed_widget(widget) -> None:
    PluginThemeBridgeImpl().register_widget(widget)


def get_qss(template: str) -> str:
    return PluginThemeBridgeImpl().get_qss(template)


def current_theme():
    return PluginThemeBridgeImpl().current_theme()


def get_popup_surface_style() -> str:
    return PluginThemeBridgeImpl().get_popup_surface_style()


def get_completer_popup_style() -> str:
    return PluginThemeBridgeImpl().get_completer_popup_style()


def information(parent, title: str, message: str, buttons=None, default_button=None):
    return PluginDialogBridgeImpl().information(parent, title, message, buttons, default_button)


def warning(parent, title: str, message: str, buttons=None, default_button=None):
    return PluginDialogBridgeImpl().warning(parent, title, message, buttons, default_button)


def question(parent, title: str, message: str, buttons, default_button):
    return PluginDialogBridgeImpl().question(parent, title, message, buttons, default_button)


def critical(parent, title: str, message: str, buttons=None, default_button=None):
    return PluginDialogBridgeImpl().critical(parent, title, message, buttons, default_button)


def show_cover_preview(parent, image_source: str, title: str = "", request_headers: dict | None = None):
    return PluginDialogBridgeImpl().show_cover_preview(
        parent,
        image_source,
        title=title,
        request_headers=request_headers,
    )


def setup_title_bar(dialog, container_layout, title: str, **kwargs):
    return PluginDialogBridgeImpl().setup_title_bar(dialog, container_layout, title, **kwargs)


def get_host_icon(name, color, size: int = 16):
    from ui.icons import get_icon as _get_icon

    return _get_icon(name, color, size)
