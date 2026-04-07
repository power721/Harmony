from __future__ import annotations


class PluginThemeBridgeImpl:
    def register_widget(self, widget) -> None:
        from system.theme import ThemeManager

        ThemeManager.instance().register_widget(widget)

    def get_qss(self, template: str) -> str:
        from system.theme import ThemeManager

        return ThemeManager.instance().get_qss(template)

    def current_theme(self):
        from system.theme import ThemeManager

        return ThemeManager.instance().current_theme

    def get_popup_surface_style(self) -> str:
        from system.theme import ThemeManager

        return ThemeManager.instance().get_themed_popup_surface_style()

    def get_completer_popup_style(self) -> str:
        from system.theme import ThemeManager

        return ThemeManager.instance().get_themed_completer_popup_style()


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


def setup_title_bar(dialog, container_layout, title: str, **kwargs):
    return PluginDialogBridgeImpl().setup_title_bar(dialog, container_layout, title, **kwargs)


def get_host_icon(name, color, size: int = 16):
    from ui.icons import get_icon as _get_icon

    return _get_icon(name, color, size)
