from functools import partial

import maya.api.OpenMaya as om2  # type: ignore
import maya.api.OpenMayaUI as omui2  # type: ignore
import maya.OpenMayaUI as omui  # type: ignore
import maya.cmds as mc  # type: ignore

from .. import exceptions, utils
from ..ext import classutilities
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List, Optional, Union
    from ..type_hints import StrLike


class Viewport(object):
    """Functions related to the viewport.

    Some methods copied from https://github.com/danbradham/mvp/blob/main/mvp/viewport.py.

    TODO:
        Tests
    """

    __slots__ = ['_view']

    def __init__(self, vp):
        # type: (Union[int, str, omui2.M3dView, Viewport]) -> None
        """Get the M3dView object.

        If an integer, then the index will be looked up.
        If a string, then the modelPanel will be looked up.
        """
        if isinstance(vp, Viewport):
            self._view = vp._view  # type: omui2.M3dView
        elif isinstance(vp, omui2.M3dView):
            self._view = vp

        else:
            try:
                if isinstance(vp, int):
                    self._view = omui2.M3dView.get3dView(vp)
                else:
                    self._view = omui2.M3dView.getM3dViewFromModelPanel(str(vp))
            except RuntimeError:
                raise exceptions.InvalidViewportError

    @classutilities.classproperty
    @classmethod
    def active(cls):
        # type: () -> Viewport
        """Get the active 3D viewport."""
        return cls(omui2.M3dView.active3dView())

    @active.setter
    @classmethod
    def _activeSet(cls, viewport):
        # type: (Viewport) -> None
        """Set the active viewport."""
        mc.modelEditor(Viewport(viewport).panel, edit=True, activeView=True)

    @classutilities.classproperty
    @classmethod
    def persp(cls):
        # type: () -> Viewport
        """Get the persp viewport."""
        return cls(mc.getPanel(withLabel='Persp View'))

    @classutilities.classproperty
    @classmethod
    def front(cls):
        # type: () -> Viewport
        """Get the front viewport."""
        return cls(mc.getPanel(withLabel='Front View'))

    @classutilities.classproperty
    @classmethod
    def side(cls):
        # type: () -> Viewport
        """Get the side viewport."""
        return cls(mc.getPanel(withLabel='Side View'))

    @classutilities.classproperty
    @classmethod
    def top(cls):
        # type: () -> Viewport
        """Get the top viewport."""
        return cls(mc.getPanel(withLabel='Top View'))

    @classmethod
    def ls(cls, visible=None):
        # type: (Optional[bool]) -> List[Viewport]
        """Get all the viewports.

        Parameters:
            visible: Filter by visible or invisible viewports.
        """
        result = []
        for view in map(omui2.M3dView.get3dView, range(omui2.M3dView.numberOf3dViews())):
            if visible is not None and view.isVisible() != visible:
                continue
            result.append(cls(view))
        return result

    @property
    def panel(self):
        # type: () -> str
        """Get the viewport panel name."""
        if not self.exists:
            raise exceptions.ViewportDeletedError
        panel = omui.MQtUtil.fullName(self._view.widget())
        return panel.split('|')[-2]

    @property
    def exists(self):
        # type: () -> bool
        """Determine if the panel exists."""
        return self._view.widget() != 0

    @property
    def visible(self):
        # type: () -> bool
        """Determine if the viewport is visible."""
        if not self.exists:
            return False
        return self._view.isVisible()

    @property
    def width(self):
        # type: () -> int
        """Get the width of the viewport."""
        return self._view.portWidth()

    @property
    def height(self):
        # type: () -> int
        """Get the height of the viewport."""
        return self._view.portHeight()

    @property
    def focused(self):
        # type: () -> bool
        """Check if the current viewport is the active viewport."""
        return mc.modelEditor(self.panel, query=True, activeView=True)

    @focused.setter
    def focused(self, focus):
        # type: (bool) -> None
        """Set the viewport focus.

        Raises:
            ViewportDeletedError
        """
        mc.modelEditor(self.panel, edit=True, activeView=focus)

    def focus(self):
        # type: () -> None
        """Set the viewport focus.

        Raises:
            ViewportDeletedError
        """
        mc.modelEditor(self.panel, edit=True, activeView=True)

    @property
    def camera(self):
        # type: () -> Node
        """Get the value of camera."""
        return Node(self._view.getCamera())

    @camera.setter
    def camera(self, camera):
        # type: (StrLike) -> None
        """Set a new value of camera.

        Raises:
            NodeNotFoundError
            NotACameraError
        """
        camera = Node(camera)
        if not camera.api.object.hasFn(om2.MFn.kDagNode):
            raise exceptions.NotACameraError(camera)
        if not camera.api.getShapeDagPath().hasFn(om2.MFn.kCamera):
            raise exceptions.NotACameraError(camera)
        mc.modelEditor(self.panel, edit=True, camera=camera)

    def snapshot(self, filepath, size=(None, None)):
        # type: (StrLike, tuple[Optional[int], Optional[int]]) -> None
        """Take a snapshot of the viewport and save it to disk.

        Parameters:
            filepath: Path with filename to save the image to.
            size: Tuple containing the width and height.
                Set either width or height to None to keep the aspect
                ratio intact.
        """
        utils.logger.info('Saving viewport snapshot: %s', filepath)
        view = omui2.M3dView.active3dView()
        image = om2.MImage()
        view.readColorBuffer(image, True)

        # Resize
        width = size[0] or self.width
        height = size[1] or self.height
        imageSize = image.getSize()
        if (width, height) != imageSize:
            utils.logger.debug('Resizing snapshot from "%dx%d" to "%dx%d"', imageSize[0], imageSize[1], width, height)
            image.resize(width, height, None in size)

        # Save
        image.writeToFile(str(filepath))

    @classmethod
    def new(cls):
        # type: () -> Viewport
        """Create a new viewport."""
        panel = mc.modelPanel()
        view = cls(panel)
        view.float()
        view.focus()
        return view

    def copy(self):
        # type: () -> Viewport
        """Create a copy of the viewport."""
        panel = mc.modelPanel(tearOffCopy=self.panel)
        viewport = Viewport(panel)
        viewport.focus()
        return viewport

    def float(self):
        # type: () -> None
        """Detatch the viewport."""
        new = self.copy()
        self.close()
        self._view = new._view

    def close(self):
        # type: () -> None
        """Close the viewport.

        If closing a default viewport then various MEL errors may occur.
        """
        try:
            panel = self.panel
        except exceptions.ViewportDeletedError:
            utils.logger.info('Deleting viewport...')
        else:
            utils.logger.info('Deleting viewport with panel "%s"...', panel)
            mc.evalDeferred(partial(mc.deleteUI, panel, panel=True))

    @property
    def default(self):
        # type: () -> bool
        """Return if a default viewport.

        Raises:
            ViewportDeletedError
        """
        label = mc.modelPanel(self.panel, query=True, label=True)
        return label in ('Persp View', 'Side View', 'Front View', 'Top View')

    def select(self):
        """Select all objects in the viewport."""
        # Set focus on the viewport
        if self.focused:
            active = self
        else:
            active = Viewport.active
            self.focus()

        # Select the ojbects
        om2.MGlobal.selectFromScreen(0, 0, self.width, self.height,
                                     om2.MGlobal.kReplaceList, om2.MGlobal.selectionMethod())

        # Set focus back on the original viewport
        if active is not self:
            active.focus()


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .node import Node
