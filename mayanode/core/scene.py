import os

import maya.cmds as mc  # type: ignore
import maya.mel as mel  # type: ignore

from .. import types, utils
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, Optional, Union


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
        path = mc.file(query=True, sceneName=True)
        if path:
            return os.path.normpath(path)
        return None

    @path.setter
    def path(self, path):
        # type: (str) -> None
        """Set a new scene path.
        This does not save the scene.
        """
        mc.file(rename=path)

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
        return mc.file(query=True, anyModified=True)

    def new(self, force=False):
        # type: (bool) -> None
        """Create a new scene.

        Parameters:
            force (bool): Force create even if the current scene is modified.
        """
        mc.file(new=True, force=force)

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
                selectivePreload = mc.optionVar(query='fileSelPreload')

        # Load the scene
        try:
            mc.file(path, open=True, force=True, buildLoadSettings=selectivePreload)
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
            mc.optionVar(stringValue=('preloadRefEdTopLevelFile', path))
            mel.eval('PreloadReferenceEditor;')

    def save(self, force=True):
        # type: (bool) -> None
        """Save the scene."""
        if force or not mc.about(batch=True):
            mc.file(force=True, save=True)
        else:
            mel.eval('saveChanges("")')

    @property
    def root(self):
        """Get the root "world" node."""
        return Node(utils.getWorldHandle())

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
        return mc.currentTime(query=True)

    @currentFrame.setter
    def currentFrame(self, frame):
        # type: (float) -> None
        """Set the current frame of the scene."""
        mc.currentTime(frame)

    @property
    def autoKeyframe(self):
        # type: () -> bool
        """Get if autoKeyframe is enabled."""
        return mc.autoKeyframe(query=True, state=True)

    @autoKeyframe.setter
    def autoKeyframe(self, enabled):
        # type: (bool) -> None
        """Enable or disable autoKeyframe."""
        mc.autoKeyframe(edit=True, state=enabled)

    @property
    def framerate(self):
        """Get the scene framerate.
        If the framerate has a relative override, then the correct offset
        can be calculated with "offset *= framerate/6000".
        """
        currentTime = mc.currentUnit(query=True, time=True)
        return float(utils.TIME_UNITS.get(currentTime, currentTime)[:-3])


class SceneNodes(types.MappedLazyList):
    """Hold a dict of all nodes currently in the scene."""

    def loadData(self, key=None):
        # type: (Optional[Union[int, str]]) -> bool
        """Get the node objects."""
        if key is None or isinstance(key, int):
            self._extend(Node.ls())
            return True

        if self._mapping is not None and key in self._mapping:
            return False

        if self._mapping is None or key not in self._mapping:
            node = Node(key)
            self._append(node)
            if self._mapping is not None:
                self._mapping[key] = node

        return False


Scene = _Scene()


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .node import Node
from .plugin import Plugin
