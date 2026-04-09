class PluginError(Exception):
    pass


class PluginInstallError(PluginError):
    pass


class PluginLoadError(PluginError):
    pass
