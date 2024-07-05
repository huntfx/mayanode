import os

import maya.api.OpenMaya as om2  # type: ignore
import maya.api.OpenMayaUI as om2ui  # type: ignore
import maya.cmds as mc  # type: ignore

from .. import exceptions, types
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, List, Optional
    from ..type_hints import StrLike


class _CameraAPI(object):
    """Hold the OpenMaya objects for the `Camera` class."""

    __slots__ = ['_parent', '_dagPath', '_camera']

    def __init__(self, parent):
        # type: (Camera) -> None
        self._parent = parent
        self._dagPath = None  # type: Optional[om2.MDagPath]
        self._camera = None  # type: Optional[om2.MFnCamera]

    def __bool__(self):
        # type: () -> bool
        """Determine if the node is valid."""
        return self.handle.isValid()
    __nonzero__ = __bool__

    def __eq__(self, other):
        # type: (Any) -> bool
        if isinstance(other, _CameraAPI):
            return self.dagPath == other.dagPath
        return False

    def __hash__(self):
        # type: () -> int
        return self.handle.hashCode()

    @property
    def handle(self):
        # type: () -> om2.MObjectHandle
        """Get the `MObjectHandle`."""
        return self._parent.node.api.handle

    @property
    def object(self):
        # type: () -> om2.MObject
        """Get the `MObject`."""
        return self._parent.node.api.object

    @property
    def dagPath(self):
        # type: () -> om2.MDagPath
        """Get the `MDagPath`

        Raises:
            NullMObjectError
            NotACameraError
        """
        if self._dagPath is None:
            mobj = self.object
            if mobj.isNull():
                raise exceptions.NullMObjectError

            if not mobj.hasFn(om2.MFn.kDagNode):
                raise exceptions.NotACameraError(self._parent.node)

            dagPath = om2.MDagPath.getAPathTo(mobj)
            if dagPath is None:
                raise exceptions.NotACameraError(self._parent.node)

            dagPath = dagPath.extendToShape()
            if not dagPath.hasFn(om2.MFn.kCamera):
                raise exceptions.NotACameraError(self._parent.node)

            self._dagPath = dagPath
        return self._dagPath

    @property
    def camera(self):
        # type: () -> om2.MFnCamera
        """Get the `MFnCamera`"""
        if self._camera is None:
            self._camera = om2.MFnCamera(self.dagPath)
        return self._camera


class Camera(types.StrMixin):
    """Contain special methods for cameras.
    Works with both camera transforms and shapes.
    There are no safety checks for non-cameras.
    """

    __slots__ = ['_api', '_node']

    def __init__(self, node):
        # type: (StrLike) -> None
        self._node = Node(node)
        self._api = _CameraAPI(self)

    @classmethod
    def ls(cls, *args, **kwargs):
        # type: (*Any, **Any) -> List[Camera]
        """Get all cameras in the scene."""
        kwargs['cameras'] = True
        return [Camera(node) for node in Node.ls(*args, **kwargs)]

    @property
    def api(self):
        # type: () -> _CameraAPI
        """Get the API data."""
        return self._api

    @property
    def node(self):
        # type: () -> Node
        """Get the camera node."""
        return self._node

    def lookThru(self, refreshViewport=True):
        # type: (bool) -> None
        """Set the camera to the current active view.

        Equivelant:
            `mc.lookThru(self); mc.refresh(currentView=True)`
        """
        view = om2ui.M3dView.active3dView()
        view.setCamera(self.api.dagPath)
        if refreshViewport:
            view.refresh()


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .node import Node
