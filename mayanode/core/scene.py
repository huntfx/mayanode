import os

import maya.cmds as mc
import maya.mel as mel

from .. import types, utils


class _Scene(object):
    """Singleton for accessing data related to the scene.

    TODO: Tests
    """
    @property
    def path(self):
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
        """Set a new scene path.
        This does not save the scene.
        """
        utils.runAndLog(mc.file, rename=path)

    @property
    def name(self):
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
        """Get if the scene has been modified."""
        return utils.runAndLog(mc.file, query=True, anyModified=True)

    def new(self, force=False):
        """Create a new scene.

        Parameters:
            force (bool): Force create even if the current scene is modified.
        """
        utils.runAndLog(mc.file, new=True, force=force)

    def open(self, path, force=False, selectivePreload=None):
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
            scene = scene.replace('\\', '\\\\')  # There is no escape
            utils.runAndLog(mc.optionVar, stringValue=('preloadRefEdTopLevelFile', scene))
            mel.eval('PreloadReferenceEditor;')

    def save(self, force=True):
        """Save the scene."""
        if force or not mc.about(batch=True):
            mc.file(force=True, save=True)
        else:
            mel.eval('saveChanges("")')

    @property
    def nodes(self):
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
        """Get all the currently loaded plugins.

        Returns:
            Dict of plugin names mapped to nodes.
        """
        return {plugin.name: plugin for plugin in Plugin.ls()}

    @property
    def currentFrame(self):
        """Get the current frame of the scene."""
        return utils.runAndLog(mc.currentTime, query=True)

    @currentFrame.setter
    def currentFrame(self, frame):
        """Set the current frame of the scene."""
        utils.runAndLog(mc.currentTime, frame)

    @property
    def autoKeyframe(self):
        """Get if autoKeyframe is enabled."""
        return utils.runAndLog(mc.autoKeyframe, query=True, state=True)

    @autoKeyframe.setter
    def autoKeyframe(self, enabled):
        """Enable or disable autoKeyframe."""
        utils.runAndLog(mc.autoKeyframe, edit=True, state=enabled)


class SceneNodes(types.LazyDict):
    """Hold a dict of all nodes currently in the scene."""

    __slots__ = ['_loaded']

    def __init__(self):
        self._loaded = False
        super(SceneNodes, self).__init__()

    def _loadData(self, key=None):
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
        """Refresh all the loaded data."""
        self._data.clear()
        self._loaded = False


Scene = _Scene()


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .node import Node
from .plugin import Plugin
