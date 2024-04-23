import maya.cmds as mc  # type: ignore

from .. import types
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List


class Plugin(types.StrMixin):
    """Query plugin information.

    TODO: Tests
    """

    def __init__(self, name):
        self._name = name

    @classmethod
    def ls(cls):
        # type: () -> List[Plugin]
        """Get all namespaces within the scene."""
        pluginList = mc.pluginInfo(query=True, listPlugins=True)
        return [cls(plugin) for plugin in pluginList]

    @property
    def name(self):
        # type: () -> str
        """Get the plugin name."""
        return self._name

    @property
    def path(self):
        # type: () -> str
        """Get the path to the plugin."""
        return mc.pluginInfo(self, query=True, path=True)

    @property
    def vendor(self):
        # type: () -> str
        """Get the plugin vendor."""
        return mc.pluginInfo(self, query=True, vendor=True)

    @property
    def commands(self):
        # type: () -> List[str]
        """Get all the commands provided by the plugin.
        Constraint, control, context and model editor commands are not included.
        """
        return mc.pluginInfo(self, query=True, commands=True)

    @property
    def loaded(self):
        # type: () -> bool
        """Determine if the plugin is loaded."""
        return mc.pluginInfo(self, query=True, loaded=True)

    @loaded.setter
    def loaded(self, load):
        # type: (bool) -> None
        """Load or unload a plugin.

        For safety, if the plugin is in use, then it cannot be unloaded
        via this method. Use `unload(force=True)` instead.
        """
        if load:
            self.load()
        else:
            self.unload()

    def load(self):
        # type: () -> None
        """Load the plugin.

        Warnings:
            Plug-in, "<plugin>", is already loaded. Skipped.
        """
        mc.loadPlugin(self)

    def unload(self, force=False):
        # type: (bool) -> None
        """Unload the plugin.

        Parameters:
            force (bool): Unload the plugin even if in use.

        Raises:
            RuntimeError: Plug-in, "<plugin>", cannot be unloaded because it is still in use
        """
        mc.loadPlugin(self, force=force)

    @property
    def autoLoad(self):
        # type: () -> bool
        """Get if auto loading is enabled."""
        return mc.pluginInfo(self, query=True, autoload=True)

    @autoLoad.setter
    def autoLoad(self, autoLoad):
        # type: (bool) -> None
        """Set if auto loading is enabled."""
        mc.pluginInfo(self, edit=True, autoload=autoLoad)
