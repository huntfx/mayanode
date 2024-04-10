import maya.api.OpenMaya as om2  # type: ignore
import maya.cmds as mc  # type: ignore

from .. import exceptions, types, utils
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Generator, Iterator, List, Optional


class Connection(utils.StrMixin):
    """Handle connections.

    TODO: Tests
    """

    __slots__ = ['_reverse', '_srcNode', '_srcPlug', '_srcAttr', '_dstNode', '_dstPlug', '_dstAttr']

    def __init__(self, srcNode, srcPlug, dstPlug, reverse=False):
        # type: (Node, om2.MPlug, om2.MPlug, bool) -> None
        """Setup the connection attributes.

        Parameters:
            srcNode: The `Node` instance where the connection originates.
            srcPlug: The `MPlug` for the source attribute.
            dstPlug: The `MPlug` for the destination attribute.
        """
        self._reverse = reverse
        self._srcNode = srcNode
        self._dstNode = None  # type: Optional[Node]

        self._srcPlug = utils.unnetworkPlug(srcPlug)
        self._dstPlug = utils.unnetworkPlug(dstPlug)

        self._dstAttr = None  # type: Optional[Attribute]
        self._srcAttr = None  # type: Optional[Attribute]

    def __repr__(self):
        # type: () -> str
        return "<{}(source='{}', destination='{}')>".format(type(self).__name__, self.source, self.destination)

    def __eq__(self, other):
        # type: (Any) -> bool
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
        if isinstance(other, Attribute):
            return self._dstPlug == other.api.plug
        return self._dstPlug.name() == other

    def __bool__(self):
        return self.exists
    __nonzero__ = __bool__

    @property
    def valid(self):
        # type: () -> bool
        """Determine if the connection is valid."""
        return self.source.exists and self.destination.exists

    @property
    def exists(self):
        # type: () -> bool
        """Determine if the connection exists.

        The equivalent command is `mc.isConnected`, which from a quick
        benchmark appears to be around 20x slower than `connectedTo`.
        Under some circumstances it seems `connectedTo` returns an
        empty list on one side, so for safety both sides are checked.
        """
        return (self.target.api.plug in self.origin.api.plug.connectedTo(True, True)
                or self.origin.api.plug in self.target.api.plug.connectedTo(True, True))

    @property
    def origin(self):
        # type: () -> Attribute
        """Load the attribute proxy for the origin attribute."""
        if self._srcAttr is None:
            self._srcAttr = Attribute(self._srcNode, self._srcPlug)
        return self._srcAttr

    @property
    def source(self):
        # type: () -> Attribute
        """Get the attribute proxy for the connection source."""
        return self.target if self._reverse else self.origin

    @property
    def target(self):
        # type: () -> Attribute
        """Load the attribute proxy for the target attribute."""
        if self._dstAttr is None:
            self._dstAttr = Attribute(self.node, self._dstPlug)
        return self._dstAttr

    @property
    def attr(self):
        # type: () -> Attribute
        """Alias to get the target attribute."""
        return self.target

    @property
    def destination(self):
        # type: () -> Attribute
        """Get the attribute proxy for the connection destination."""
        return self.origin if self._reverse else self.target

    @property
    def node(self):
        # type: () -> Node
        """Load the destination node without an attribute."""
        if self._dstNode is None:
            self._dstNode = Node(self._dstPlug.node())
        return self._dstNode

    def __iter__(self):
        # type: () -> Iterator[Attribute]
        yield self.source
        yield self.destination

    @property
    def name(self):
        # type: () -> str
        """Get the destination attribute name."""
        return self.target.name

    def connect(self):
        # type: () -> bool
        """Create a connection.

        Raises:
            AttributeNotFoundError: If either attribute doesn't exist
            RuntimeError: The attribute '{}' cannot be connected to '{}'.

        Returns:
            True if successful otherwise False.
        """
        utils.logger.info('Creating connection: %s >> %s', self.source, self.destination)
        if not self.exists:
            if not self.source.exists:
                raise exceptions.AttributeNotFoundError(self.source.node, self.source.attr)
            if not self.destination.exists:
                raise exceptions.AttributeNotFoundError(self.destination.node, self.destination.attr)
            utils.runAndLog(mc.connectAttr, self.source, self.destination)
            return True

        utils.logger.debug('Connection already exists')
        return False

    def disconnect(self):
        # type: () -> bool
        """Break a connection.

        Raises:
            AttributeNotFoundError: If either attribute doesn't exist

        Returns:
            True if successful otherwise False.
        """
        utils.logger.info('Breaking connection: %s // %s', self.source, self.destination)
        if self.exists:
            if not self.source.exists:
                raise exceptions.AttributeNotFoundError(self.source.node, self.source.attr)
            if not self.destination.exists:
                raise exceptions.AttributeNotFoundError(self.destination.node, self.destination.attr)
            utils.runAndLog(mc.disconnectAttr, self.source, self.destination)
            return True

        utils.logger.debug('Connection does not exist')
        return False


class ConnectionList(types.LazyList):
    """Hold multiple connections and provide a way to connect/disconnect all."""

    def connect(self):
        # type: () -> ConnectionList
        """Create all connections."""
        result = []
        for connection in self:
            try:
                if connection.connect():
                    result.append(connection)
            except (exceptions.NodeDeletedError, exceptions.AttributeNotFoundError):
                pass
        return ConnectionList(result)

    def disconnect(self):
        # type: () -> ConnectionList
        """Delete all connections."""
        result = []
        for connection in self:
            try:
                if connection.disconnect():
                    result.append(connection)
            except (exceptions.NodeDeletedError, exceptions.AttributeNotFoundError):
                pass
        return ConnectionList(result)

    @property
    def nodes(self):
        # type: () -> List[Node]
        """Get a deduplicated list of all connected nodes.

        Equivalent:
            `mc.listConnections(self.target)`
        """
        nodes = (connection.node for connection in self._data)
        seen = set()
        return [node for node in nodes if node not in seen and not seen.add(node)]  # type: ignore

    @property
    def attrs(self):
        # type: () -> List[Attribute]
        """Get a deduplicated list of all connected attributes.

        Equivalent:
            `mc.listConnections(self.target, plugs=True)`
        """
        attrs = (connection.target for connection in self._data)
        seen = set()
        return [attr for attr in attrs if attr not in seen and not seen.add(attr)]  # type: ignore


class ConnectionProxy(ConnectionList):
    """Hold the connection data to lazily load connections.
    By default, both the source and destination connections will be
    loaded, but either can be requested with the respective property.

    The data contained by the class instance is not live, but in the
    case a reload is required, there is a method to handle that.
    """

    __slots__ = ['_connections', '_sourceConnections', '_destinationConnections']

    def __init__(self):
        # type: () -> None
        self._sourceConnections = None  # type: Optional[List[Connection]]
        self._destinationConnections = None  # type: Optional[List[Connection]]
        super(ConnectionProxy, self).__init__()

    @property
    def inputs(self):
        # type: () -> ConnectionList
        """Get the input/source connections."""
        self._loadData(source=True, destination=False)
        return ConnectionList(self._sourceConnections)

    @property
    def outputs(self):
        # type: () -> ConnectionList
        """Get the output/destination connections."""
        self._loadData(source=False, destination=True)
        return ConnectionList(self._destinationConnections)

    @property
    def node(self):
        # type: () -> Node
        """Get the node.
        Requires an override.
        """
        raise NotImplementedError

    @property
    def nodes(self):
        # type: () -> List[Node]
        """Get all connected nodes."""
        self._loadData(source=True, destination=True)
        return super(ConnectionProxy, self).nodes

    @property
    def attrs(self):
        # type: () -> List[Attribute]
        """Get all connected attributes."""
        self._loadData(source=True, destination=True)
        return super(ConnectionProxy, self).attrs

    @property
    def plugs(self):
        # type: () -> List[om2.MPlug]
        """Get the `MPlug` objects.
        Requires override.
        """
        raise NotImplementedError

    def _loadRecursive(self, plug, source=True, destination=True):
        # type: (om2.MPlug, bool, bool) -> Generator[Connection, None, None]
        """Recursively load connections from the plug and any children."""
        if source:
            for connectedPlug in plug.connectedTo(True, False):
                yield Connection(self.node, plug, connectedPlug, reverse=True)
        if destination:
            for connectedPlug in plug.connectedTo(False, True):
                yield Connection(self.node, plug, connectedPlug)

        plugs = []  # type: List[om2.MPlug]
        if plug.isArray:
            plugs.extend(map(plug.elementByPhysicalIndex, range(plug.numElements())))
        elif plug.isCompound:
            plugs.extend(map(plug.child, range(plug.numChildren())))

        for childPlug in plugs:
            for connection in self._loadRecursive(childPlug, source=source, destination=destination):
                yield connection

    def _loadData(self, index=None, source=True, destination=True):
        # type: (Optional[int], bool, bool) -> None
        """Get the connection data from the plugs.

        TODO:
            Split into a different method
        """
        # Ensure the data is only loaded once
        if TYPE_CHECKING or destination:
            if self._destinationConnections is None:
                self._destinationConnections = []
            else:
                destination = False
        if TYPE_CHECKING or source:
            if self._sourceConnections is None:
                self._sourceConnections = []
            else:
                source = False
        if not source and not destination:
            return

        # Get the connections for each plug
        for currentPlug in self.plugs:
            if destination:
                self._destinationConnections.extend(self._loadRecursive(currentPlug, False, True))
            if source:
                self._sourceConnections.extend(self._loadRecursive(currentPlug, True, False))

        # Add to main list
        if destination:
            self._data.extend(self._destinationConnections)
        if source:
            self._data.extend(self._sourceConnections)

    def reload(self):
        # type: () -> None
        """Refresh all the loaded data."""
        self._destinationConnections = self._sourceConnections = None
        super(ConnectionProxy, self).reload()


class AttributeConnectionProxy(ConnectionProxy):
    """Connection proxy for Attributes."""

    __slots__ = ['_attr']

    def __init__(self, attr):
        # type: (Attribute) -> None
        super(AttributeConnectionProxy, self).__init__()
        self._attr = attr

    @property
    def attr(self):
        # type: () -> Attribute
        """Get the attribute."""
        return self._attr

    @property
    def node(self):
        # type: () -> Node
        """Get the node."""
        return self.attr.node

    @property
    def plugs(self):
        # type: () -> List[om2.MPlug]
        """Get the attribute `MPlug` objects."""
        attrApi = self.attr.api
        if attrApi.plug.isNull:
            return []
        return attrApi.plugs


class NodeConnectionProxy(ConnectionProxy):
    """Connection proxy for Nodes."""

    __slots__ = ['_node']

    def __init__(self, node):
        # type: (Node) -> None
        super(NodeConnectionProxy, self).__init__()
        self._node = node

    @property
    def node(self):
        # type: () -> Node
        """Get the node."""
        return self._node

    @property
    def plugs(self):
        # type: () -> List[om2.MPlug]
        """Get the node `MPlug` objects."""
        if not self.node.exists:
            return []
        return [utils.unnetworkPlug(plug) for plug in self.node.api.dependencyNode.getConnections()]


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .node import Node
from .node.attributes import Attribute
