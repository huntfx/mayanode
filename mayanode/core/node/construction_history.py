"""Handle the node history/future.

It is an area of Maya I am not familiar with, and there are multiple
optional flags such as `allConnections`, so for now this is a very basic
implementation. Future changes may be made if I dig more into it.
"""

import maya.api.OpenMaya as om2  # type: ignore
import maya.cmds as mc  # type: ignore

from ... import utils
from ...type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List, Optional
    from ...type_hints import StrLike


class ConstructionHistory(list):
    """Get all upstream nodes in the construction history."""

    __slots__ = ['_node']

    def __init__(self, node, history=None):
        # type: (Node, Optional[List[StrLike]]) -> None
        self._node = node
        if history is None:
            history = utils.runAndLog(mc.listHistory, node)[1:]
        super(ConstructionHistory, self).__init__(map(Node, history))

    @property
    def node(self):
        # type: () -> Node
        """Get the associated node."""
        return self._node

    def delete(self):
        # type: () -> Node
        """Delete all the construction history."""
        utils.logger.info('Deleting construction history for "%s"', self.node)
        utils.runAndLog(mc.delete, self.node, constructionHistory=True)

    @property
    def history(self):
        """Get the upstream nodes."""
        # type: () -> ConstructionHistory
        future = utils.runAndLog(mc.listHistory, self.node)[1:]
        return ConstructionHistory(self.node, future)

    @property
    def future(self):
        """Get the downstream nodes."""
        # type: () -> ConstructionHistory
        future = utils.runAndLog(mc.listHistory, self.node, future=True)[1:]
        return ConstructionHistory(self.node, future)


# Handle circular dependencies
# pylint: disable=wrong-import-position
from . import Node
