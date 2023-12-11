from __future__ import absolute_import

import maya.cmds as mc

from .. import utils


class BoundingBox(tuple):
    """Get the bounding box of a group of nodes and perform calculations."""

    def __new__(cls, nodes):
        boundingBox = utils.runAndLog(mc.exactWorldBoundingBox, nodes)
        return tuple.__new__(cls, boundingBox)

    @property
    def x(self):
        """Get the X coordinate."""
        return (self.xMax + self.xMin) / 2

    @property
    def y(self):
        """Get the Y coordinate."""
        return (self.yMax + self.yMin) / 2

    @property
    def z(self):
        """Get the Z coordinate."""
        return (self.zMax + self.zMin) / 2

    @property
    def origin(self):
        """Get the origin coordinate."""
        return (self.x, self.y, self.z)

    @property
    def xMin(self):
        """Get the minimum X limit."""
        return self.__getitem__(0)

    @property
    def yMin(self):
        """Get the minimum Y limit."""
        return self.__getitem__(1)

    @property
    def zMin(self):
        """Get the minimum Z limit."""
        return self.__getitem__(2)

    @property
    def xMax(self):
        """Get the maximum X limit."""
        return self.__getitem__(3)

    @property
    def yMax(self):
        """Get the maximum Y limit."""
        return self.__getitem__(4)

    @property
    def zMax(self):
        """Get the maximum Z limit."""
        return self.__getitem__(5)

    @property
    def width(self):
        """Get the width."""
        return abs(self.xMax - self.xMin)

    @property
    def height(self):
        """Get the height."""
        return abs(self.yMax - self.yMin)

    @property
    def depth(self):
        """Get the depth."""
        return abs(self.zMax - self.zMin)

    def drawCube(self, name='BoundingBox'):
        """Draw a cube representation of the bounding box."""
        from .node import Node
        transform, shape = utils.runAndLog(mc.polyCube, width=self.width, height=self.height, depth=self.depth, name=name)
        cube = Node(transform)
        cube.translation = self.origin
        return cube
