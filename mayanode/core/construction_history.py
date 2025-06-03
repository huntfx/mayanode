"""Handle the node history/future.

It is an area of Maya I am not familiar with, and there are multiple
optional flags such as `allConnections`, so for now this is a very basic
implementation. Future changes may be made if I dig more into it.
"""

import maya.api.OpenMaya as om2
import maya.cmds as mc  # type: ignore

from .. import types, utils
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Type


class ConstructionHistory(types.MappedLazyList['Node', om2.MObject, str]):
    """Get nodes in the construction history."""

    __slots__ = ['_node', '_future', '_allConnections']

    @property
    def ItemType(self):  # type: () -> Type[Node]
        """Return the object this list contains."""
        return Node

    def __init__(self, node, future=False, allConnections=False):
        # type: (Node, bool, bool) -> None
        self._node = node
        self._future = future
        self._allConnections = allConnections
        super(ConstructionHistory, self).__init__()

    @property
    def node(self):
        # type: () -> Node
        """Get the associated node."""
        return self._node

    def delete(self):
        # type: () -> None
        """Delete all the construction history."""
        utils.logger.info('Deleting construction history for "%s"', self.node)
        mc.delete(self.node, constructionHistory=True)
        self.refresh()

    @property
    def history(self):
        # type: () -> ConstructionHistory
        """Get the upstream nodes.

        Equivalent:
            mc.listHistory(self)[1:]
        """
        return ConstructionHistory(self.node, future=False, allConnections=self._allConnections)

    @property
    def future(self):
        # type: () -> ConstructionHistory
        """Get the downstream nodes.

        Equivalent:
            mc.listHistory(self, future=True)[1:]
        """
        return ConstructionHistory(self.node, future=True, allConnections=self._allConnections)

    @property
    def allConnections(self):
        # type: () -> ConstructionHistory
        """Get all the connected nodes.

        Equivalent:
            mc.listHistory(self, allConnections=True)[1:]
        """
        return ConstructionHistory(self.node, future=self._future, allConnections=True)

    def _loadApiObjects(self):
        # type: () -> list[om2.MObject]
        """Load the pointers to nodes in the construction history."""
        shape = self.node.api.getShapeDagPath()
        if shape is None or not shape.isValid():
            node = self.node.api.object
        else:
            node = shape.node()
        return list(utils.iterConstructionHistory(node, future=self._future, allConnections=self._allConnections))


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .node import Node
