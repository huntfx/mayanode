from __future__ import absolute_import

import maya.api.OpenMaya as om2  # type: ignore
import maya.cmds as mc  # type: ignore

from ..types import Coordinate
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List, Union
    from ..type_hints import StrLike


class BoundingBox(tuple):
    """Get the bounding box of a group of nodes and perform calculations.

    Equivalent:
        `mc.exactWorldBoundingBox`
    """

    def __new__(cls, *nodes):
        # type: (*StrLike) -> BoundingBox
        boundingBox = om2.MBoundingBox()
        for node in nodes:
            if not isinstance(node, Node):
                node = Node(node)

            apiObj = None
            if node.isDagNode:
                # If a mesh, use the bounding box from MFnMesh
                if node.isMesh:
                    apiObj = node.api.mesh

                # If a camera, use the bounding box from MFnCamera
                elif node.isCamera:
                    apiObj = node.api.camera

                # Anything then use the bounding box from MFnDagNode
                else:
                    # Flag types that don't require a shape
                    noShapeRequired = node.isLocator or node.isCurve

                    # Get the shape from any other type
                    # Known: light, sketchPlane
                    if noShapeRequired and node.type == 'transform':
                        shape = node.shape
                        if shape is not None:
                            node = shape
                    apiObj = node.api.dagNode

            if apiObj is None:
                continue

            dagPath = node.api.dagPath
            # Not sure if possible that a DAG node can be missing a
            # path, so raise an error if it happens
            if dagPath is None:
                raise NotImplementedError('DAG node without a DAG path')

            worldMatrix = dagPath.inclusiveMatrix()
            boundingBox.expand(apiObj.boundingBox.transformUsing(worldMatrix))

        return tuple.__new__(cls, (boundingBox.min.x, boundingBox.min.y, boundingBox.min.z,
                                   boundingBox.max.x, boundingBox.max.y, boundingBox.max.z))

    @property
    def x(self):
        # type: () -> float
        """Get the X coordinate."""
        return (self.xMax + self.xMin) / 2

    @property
    def y(self):
        # type: () -> float
        """Get the Y coordinate."""
        return (self.yMax + self.yMin) / 2

    @property
    def z(self):
        # type: () -> float
        """Get the Z coordinate."""
        return (self.zMax + self.zMin) / 2

    @property
    def origin(self):
        # type: () -> Coordinate
        """Get the origin coordinate."""
        return Coordinate(self.x, self.y, self.z)

    @property
    def xMin(self):
        # type: () -> float
        """Get the minimum X limit."""
        return self.__getitem__(0)

    @property
    def yMin(self):
        # type: () -> float
        """Get the minimum Y limit."""
        return self.__getitem__(1)

    @property
    def zMin(self):
        # type: () -> float
        """Get the minimum Z limit."""
        return self.__getitem__(2)

    @property
    def xMax(self):
        # type: () -> float
        """Get the maximum X limit."""
        return self.__getitem__(3)

    @property
    def yMax(self):
        # type: () -> float
        """Get the maximum Y limit."""
        return self.__getitem__(4)

    @property
    def zMax(self):
        # type: () -> float
        """Get the maximum Z limit."""
        return self.__getitem__(5)

    @property
    def width(self):
        # type: () -> float
        """Get the width."""
        return abs(self.xMax - self.xMin)

    @property
    def height(self):
        # type: () -> float
        """Get the height."""
        return abs(self.yMax - self.yMin)

    @property
    def depth(self):
        # type: () -> float
        """Get the depth."""
        return abs(self.zMax - self.zMin)

    def drawCube(self, name='BoundingBox'):
        # type: (str) -> Node
        """Draw a cube representation of the bounding box."""
        transform, shape = mc.polyCube(width=self.width, height=self.height, depth=self.depth, name=name)
        cube = Node(transform)
        cube.translation = self.origin
        return cube


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .node import Node
