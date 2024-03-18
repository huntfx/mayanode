import maya.cmds as mc

from .. import types, utils


class Plugin(types.StrMixin):
    """Query plugin information.

    TODO: Tests
    """

    def __init__(self, name):
        self._name = name

    @classmethod
    def ls(cls):
        """Get all namespaces within the scene."""
        pluginList = utils.runAndLog(mc.pluginInfo, query=True, listPlugins=True)
        return [cls(plugin) for plugin in pluginList]

    @property
    def name(self):
        """Get the plugin name."""
        return self._name

    @property
    def path(self):
        """Get the path to the plugin."""
        return utils.runAndLog(mc.pluginInfo, self, query=True, path=True)

    @property
    def vendor(self):
        """Get the plugin vendor."""
        return utils.runAndLog(mc.pluginInfo, self, query=True, vendor=True)

    @property
    def commands(self):
        """Get all the commands provided by the plugin.
        Constraint, control, context and model editor commands are not included.
        """
        return utils.runAndLog(mc.pluginInfo, self, query=True, vendor=True)

    @property
    def loaded(self):
        """Determine if the plugin is loaded."""
        return utils.runAndLog(mc.pluginInfo, self, query=True, loaded=True)

    @loaded.setter
    def loaded(self, load):
        """Load or unload a plugin.

        For safety, if the plugin is in use, then it cannot be unloaded
        via this method. Use `unload(force=True)` instead.
        """
        if load:
            self.load()
        else:
            self.unload()

    def load(self):
        """Load the plugin.

        Warnings:
            Plug-in, "<plugin>", is already loaded. Skipped.
        """
        utils.runAndLog(mc.loadPlugin, self)

    def unload(self, force=False):
        """Unload the plugin.

        Parameters:
            force (bool): Unload the plugin even if in use.

        Raises:
            RuntimeError: Plug-in, "<plugin>", cannot be unloaded because it is still in use
        """
        utils.runAndLog(mc.loadPlugin, self, force=force)

    @property
    def autoLoad(self):
        """Get if auto loading is enabled."""
        return utils.runAndLog(mc.pluginInfo, self, query=True, autoload=True)

    @autoLoad.setter
    def autoLoad(self, autoLoad):
        """Set if auto loading is enabled."""
        utils.runAndLog(mc.pluginInfo, self, edit=True, autoload=autoLoad)
