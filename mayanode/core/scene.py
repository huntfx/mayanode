import os

import maya.cmds as mc  # type: ignore
import maya.mel as mel  # type: ignore

from .. import types, utils
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, Optional


class _Scene(object):
    """Singleton for accessing data related to the scene.

    TODO: Tests
    """

    @property
    def path(self):
        # type: () -> Optional[str]
        """Get the full scene path.

        Returns:
            Scene path as a string or None.
        """
        path = utils.runAndLog(mc.file, query=True, sceneName=True)
        if path:
            return os.path.normpath(path)
        return None

    @path.setter
    def path(self, path):
        # type: (str) -> None
        """Set a new scene path.
        This does not save the scene.
        """
        utils.runAndLog(mc.file, rename=path)

    @property
    def name(self):
        # type: () -> Optional[str]
        """Get the scene name without its extension.

        Returns:
            Name as a string or None.
        """
        path = self.path
        if path is None:
            return None
        return os.path.splitext(os.path.basename(path))[0]

    @property
    def modified(self):
        # type: () -> bool
        """Get if the scene has been modified."""
        return utils.runAndLog(mc.file, query=True, anyModified=True)

    def new(self, force=False):
        # type: (bool) -> None
        """Create a new scene.

        Parameters:
            force (bool): Force create even if the current scene is modified.
        """
        utils.runAndLog(mc.file, new=True, force=force)

    def open(self, path, force=False, selectivePreload=None):
        # type: (str, bool, Optional[bool]) -> None
        """Open a scene.

        Parameters:
            path (str): Path to the scene.
            force (bool): Force load even if the current scene is modified.
            selectedPreload (bool, optional): Enable selective preloading.
                If None, then the current settings will be used.

        Raises:
            IOError: File not found: <path>
        """
        # Determine the current selective preload setting
        if selectivePreload is None:
            if force:
                selectivePreload = False
            else:
                selectivePreload = utils.runAndLog(mc.optionVar, query='fileSelPreload')

        # Load the scene
        try:
            utils.runAndLog(mc.file, path, open=True, force=True, buildLoadSettings=selectivePreload)
        except RuntimeError as e:
            if str(e).startswith('File not found'):
                raise IOError(str(e))
            raise

        # Add to recent file list
        ext = os.path.splitext(path)[1].lower()
        exts = {'.ma': 'mayaAscii', '.mb': 'mayaBinary'}
        if ext in exts:
            mel.eval('addRecentFile("{}", "{}")'.format(path.replace('\\', '/'), exts[ext]))

        # Selective reference preload
        if selectivePreload:
            path = path.replace('\\', '\\\\')  # There is no escape
            utils.runAndLog(mc.optionVar, stringValue=('preloadRefEdTopLevelFile', path))
            mel.eval('PreloadReferenceEditor;')

    def save(self, force=True):
        # type: (bool) -> None
        """Save the scene."""
        if force or not mc.about(batch=True):
            mc.file(force=True, save=True)
        else:
            mel.eval('saveChanges("")')

    @property
    def nodes(self):
        # type: () -> SceneNodes
        """Get all the nodes currently in the scene.

        Example:
            >>> Scene.nodes['persp']
            Node('persp')

        Raises:
            NodeNotFoundError

        Returns:
            Dict of node names mapped to nodes.
        """
        return SceneNodes()

    @property
    def plugins(self):
        # type: () -> Dict[str, Plugin]
        """Get all the currently loaded plugins.

        Returns:
            Dict of plugin names mapped to nodes.
        """
        return {plugin.name: plugin for plugin in Plugin.ls()}

    @property
    def currentFrame(self):
        # type: () -> float
        """Get the current frame of the scene."""
        return utils.runAndLog(mc.currentTime, query=True)

    @currentFrame.setter
    def currentFrame(self, frame):
        # type: (float) -> None
        """Set the current frame of the scene."""
        utils.runAndLog(mc.currentTime, frame)

    @property
    def autoKeyframe(self):
        # type: () -> bool
        """Get if autoKeyframe is enabled."""
        return utils.runAndLog(mc.autoKeyframe, query=True, state=True)

    @autoKeyframe.setter
    def autoKeyframe(self, enabled):
        # type: (bool) -> None
        """Enable or disable autoKeyframe."""
        utils.runAndLog(mc.autoKeyframe, edit=True, state=enabled)


class SceneNodes(types.LazyDict):
    """Hold a dict of all nodes currently in the scene."""

    __slots__ = ['_loaded']

    def __init__(self):
        # type: () -> None
        self._loaded = False
        super(SceneNodes, self).__init__()

    def _loadData(self, key=None):
        # type: (str) -> None
        """Get the node objects."""
        if self._loaded:
            return None

        if key is None:
            if not self._loaded:
                allNodes = {node.name: node for node in Node.ls()}
                self._data.update(allNodes)
                self._loaded = True

        elif key not in self._data:
            node = Node(key)
            self._data.__setitem__(key, node)

    def reload(self):
        # type: () -> None
        """Refresh all the loaded data."""
        self._data.clear()
        self._loaded = False


Scene = _Scene()


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .node import Node
from .plugin import Plugin
