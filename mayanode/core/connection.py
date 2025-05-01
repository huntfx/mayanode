import maya.api.OpenMaya as om2
import maya.cmds as mc  # type: ignore

from .. import exceptions, types, utils
from ..type_hints import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from typing import Any, Iterator, SupportsIndex


class Connection(types.StrMixin):
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
        self._dstNode = None  # type: Node | None

        self._srcPlug = utils.unnetworkPlug(srcPlug)
        self._dstPlug = utils.unnetworkPlug(dstPlug)

        self._dstAttr = None  # type: Attribute | None
        self._srcAttr = None  # type: Attribute | None

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

        Equivalent:
            `mc.isConnected(self.source, self.destination)`
        """
        if self._reverse:
            return self._srcPlug.source() == self._dstPlug
        return self._srcPlug == self._dstPlug.source()

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
            ConnectToSelfError: If connecting to itself
            RuntimeError: The attribute '{}' cannot be connected to '{}'.

        Returns:
            True if successful otherwise False.
        """
        utils.logger.info('Creating connection: %s >> %s', self.source, self.destination)
        if self._srcPlug == self._dstPlug:
            raise exceptions.ConnectToSelfError(self.source.node, self.source.attr)

        if not self.exists:
            if not self.source.exists:
                raise exceptions.AttributeNotFoundError(self.source.node, self.source.attr)
            if not self.destination.exists:
                raise exceptions.AttributeNotFoundError(self.destination.node, self.destination.attr)
            mc.connectAttr(self.source, self.destination)
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
            mc.disconnectAttr(self.source, self.destination)
            return True

        utils.logger.debug('Connection does not exist')
        return False


class ConnectionList(object):
    """Hold multiple connections and provide a way to connect/disconnect all."""

    def __init__(self, connections=None):
        # type: (list[Connection] | None) -> None
        self._data = connections

    def __repr__(self):
        # type: () -> str
        return repr(list(self))

    def __str__(self):
        # type: () -> str
        return str(list(self))

    def __bool__(self):
        # type: () -> bool
        return bool(self._getData())
    __nonzero__ = __bool__

    def __contains__(self, item):
        # type: (Any) -> bool
        if isinstance(item, Connection):
            return item in self._getData()
        elif isinstance(item, Node):
            return item in self.nodes
        elif isinstance(item, Attribute):
            return item in self.attrs
        item = str(item)
        if '.' in item:
            return item in self.attrs
        return item in self.nodes

    def __len__(self):
        # type: () -> int
        return len(self._getData())

    def __eq__(self, other):
        # type: (Any) -> bool
        if isinstance(other, ConnectionList):
            return list(self) == list(other)
        if isinstance(other, list):
            return list(self) == other
        return False

    def __iter__(self):
        # type: () -> Iterator[Connection]
        """Iterate over the connections."""
        return iter(self._getData())

    @overload
    def __getitem__(self, item):
        # type: (SupportsIndex) -> Connection
        pass
    @overload
    def __getitem__(self, item):
        # type: (slice) -> list[Connection]
        pass
    def __getitem__(self, item):
        # type: (SupportsIndex | slice) -> list[Connection] | Connection
        """Get the connection at an index."""
        return self._getData()[item]

    def _getData(self):
        # type: () -> list[Connection]
        if self._data is None:
            return []
        return self._data

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
        # type: () -> list[Node]
        """Get a deduplicated list of all connected nodes.

        Equivalent:
            `mc.listConnections(self.target)`
        """
        nodes = (connection.node for connection in self)
        seen = set()
        return [node for node in nodes if node not in seen and not seen.add(node)]  # type: ignore

    @property
    def attrs(self):
        # type: () -> list[Attribute]
        """Get a deduplicated list of all connected attributes.

        Equivalent:
            `mc.listConnections(self.target, plugs=True)`
        """
        attrs = (connection.target for connection in self)
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
        self._sourceConnections = None  # type: list[Connection] | None
        self._destinationConnections = None  # type: list[Connection] | None
        super(ConnectionProxy, self).__init__()

    def __bool__(self):
        # type: () -> bool
        """Determine if any connections exist."""
        return any(plug.isConnected for plug in self.plugs)
    __nonzero__ = __bool__

    def _getData(self):
        # type: () -> list[Connection]
        if self._data is None:
            self._loadConnections()
        if TYPE_CHECKING: assert self._data is not None
        return self._data

    @property
    def source(self):
        # type: () -> ConnectionList
        """Get the input/source connections."""
        self._loadConnections(source=True, destination=False)
        return ConnectionList(self._sourceConnections)

    @property
    def destination(self):
        # type: () -> ConnectionList
        """Get the output/destination connections."""
        self._loadConnections(source=False, destination=True)
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
        # type: () -> list[Node]
        """Get all connected nodes."""
        self._loadConnections(source=True, destination=True)
        return super(ConnectionProxy, self).nodes

    @property
    def attrs(self):
        # type: () -> list[Attribute]
        """Get all connected attributes."""
        self._loadConnections(source=True, destination=True)
        return super(ConnectionProxy, self).attrs

    @property
    def plugs(self):
        # type: () -> Iterator[om2.MPlug]
        """Get the `MPlug` objects.
        Requires override.
        """
        raise NotImplementedError

    def _loadConnections(self, source=True, destination=True):
        # type: (bool, bool) -> None
        """Get the connection data from the plugs."""
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
            if not currentPlug.isConnected:
                continue
            if destination and currentPlug.isSource:
                for connectedPlug in currentPlug.destinations():
                    self._destinationConnections.append(Connection(self.node, currentPlug, connectedPlug))
            if source and currentPlug.isDestination:
                self._sourceConnections.append(Connection(self.node, currentPlug, currentPlug.source(), reverse=True))

        # Add to main list
        if self._data is None:
            self._data = []
        if destination:
            self._data.extend(self._destinationConnections)
        if source:
            self._data.extend(self._sourceConnections)

    def reload(self):
        # type: () -> None
        """Refresh all the loaded data."""
        self._destinationConnections = self._sourceConnections = None


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
        # type: () -> Iterator[om2.MPlug]
        """Get the attribute `MPlug` objects."""
        return utils.getChildPlugs(self.attr.api.plug)


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
        # type: () -> Iterator[om2.MPlug]
        """Get the node `MPlug` objects."""
        if not self.node.exists:
            return
        for plug in self.node.api.dependencyNode.getConnections():
            yield utils.unnetworkPlug(plug)


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .attribute import Attribute
from .node import Node
