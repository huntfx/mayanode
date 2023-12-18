import maya.api.OpenMaya as om2
import maya.cmds as mc

from .node import Node
from .node.attributes import AttributeProxy
from .. import utils


class Connection(utils.StrMixin):
    """Handle connections.

    TODO: Tests
    """

    __slots__ = ['_reverse', '_srcNode', '_srcPlug', '_srcAttr', '_dstNode', '_dstPlug', '_dstAttr']

    def __init__(self, srcNode, srcPlug, dstPlug, reverse=False):
        """Setup the connection attributes without loading anything.

        Parameters:
            srcNode: The `Node` instance where the connection originates.
            srcPlug: The `MPlug` for the source attribute.
            dstPlug: The `MPlug` for the destination attribute.
        """
        self._reverse = reverse
        self._srcNode = srcNode
        self._srcPlug = srcPlug
        self._dstPlug = dstPlug
        self._srcAttr = self._dstNode = self._dstAttr = None

    def __repr__(self):
        return "<{}(source='{}', destination='{}')>".format(type(self).__name__, self.source, self.destination)

    def __eq__(self, other):
        """Check for equality.
        This takes into account the direction of the connection. For
        example, with `pCube1.tx >> pCube2.tx`, then it will equal
        `pCube2.tx` only.
        """
        if isinstance(other, Connection):
            current = [self._srcPlug, self._dstPlug]
            if self._reverse != other._reverse:
                current = current[::-1]
            return current == [other._srcPlug, other._dstPlug]
        if isinstance(other, AttributeProxy):
            return self._dstPlug == other.api.plug
        return self._dstPlug.name() == other

    @property
    def origin(self):
        """Load the attribute proxy for the origin attribute."""
        if self._srcAttr is None:
            self._srcAttr = AttributeProxy(self._srcNode, self._srcPlug)
        return self._srcAttr

    @property
    def source(self):
        """Get the attribute proxy for the connection source."""
        return self.target if self._reverse else self.origin

    @property
    def target(self):
        """Load the attribute proxy for the target attribute."""
        if self._dstAttr is None:
            self._dstAttr = AttributeProxy(self.node, self._dstPlug)
        return self._dstAttr

    @property
    def destination(self):
        """Get the attribute proxy for the connection destination."""
        return self.origin if self._reverse else self.target

    @property
    def node(self):
        """Load the destination node without an attribute."""
        if self._dstNode is None:
            self._dstNode = Node(self._dstPlug.node())
        return self._dstNode

    def __iter__(self):
        yield self.source
        yield self.destination

    @property
    def name(self):
        """Get the destination attribute name."""
        return self.target.name

    def connect(self, reverse=False):
        """Create a connection.
        Set `reverse` to connect the other direction.

        TODO: Raise if connection exists
        TODO: Test connection between wrong types

        Returns:
            True if successful otherwise False.
        """
        direction = [self.origin, self.target]
        if reverse:
            direction.reverse()
        utils.logger.info('Creating connection: %s >> %s', *direction)

        if not self.origin.api or not self.target.api:
            utils.runAndLog(mc.connectAttr, *direction)
        else:
            om2.MDGModifier().connect(direction[0].api.plug, direction[1].api.plug).doIt()
        return True

    def disconnect(self, reverse=False):
        """Break a connection.
        Set `reverse` to disconnect the other direction.

        TODO: Raise if connection doesn't exist
        TODO: Test connection between wrong types

        Returns:
            True if successful otherwise False.
        """
        direction = [self.origin, self.target]
        if reverse:
            direction.reverse()
        utils.logger.info('Breaking connection: %s >> %s', *direction)

        if not self.origin.api or not self.target.api:
            utils.runAndLog(mc.disconnectAttr, *direction)
        else:
            om2.MDGModifier().disconnect(direction[0].api.plug, direction[1].api.plug).doIt()
        return True
