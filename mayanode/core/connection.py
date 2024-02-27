import maya.api.OpenMaya as om2
import maya.cmds as mc

from .. import exceptions, utils


class Connection(utils.StrMixin):
    """Handle connections.

    TODO: Tests
    """

    __slots__ = ['_reverse', '_srcNode', '_srcPlug', '_srcAttr', '_dstNode', '_dstPlug', '_dstAttr']

    def __init__(self, srcNode, srcPlug, dstPlug, reverse=False):
        """Setup the connection attributes.

        Parameters:
            srcNode: The `Node` instance where the connection originates.
            srcPlug: The `MPlug` for the source attribute.
            dstPlug: The `MPlug` for the destination attribute.
        """
        self._reverse = reverse
        self._reverse = reverse
        self._srcNode = srcNode
        self._srcPlug = utils.unnetworkPlug(srcPlug)
        self._dstPlug = utils.unnetworkPlug(dstPlug)
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
        if isinstance(other, Attribute):
            return self._dstPlug == other.api.plug
        return self._dstPlug.name() == other

    def __bool__(self):
        return self.exists
    __nonzero__ = __bool__

    @property
    def valid(self):
        """Determine if the connection is valid."""
        return self.source.exists and self.destination.exists

    @property
    def exists(self):
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
        """Load the attribute proxy for the origin attribute."""
        if self._srcAttr is None:
            self._srcAttr = Attribute(self._srcNode, self._srcPlug)
        return self._srcAttr

    @property
    def source(self):
        """Get the attribute proxy for the connection source."""
        return self.target if self._reverse else self.origin

    @property
    def target(self):
        """Load the attribute proxy for the target attribute."""
        if self._dstAttr is None:
            self._dstAttr = Attribute(self.node, self._dstPlug)
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

    def connect(self):
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


class ConnectionList(list):
    """Hold multiple connections and provide a way to connect/disconnect all."""

    def connect(self):
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
        """Delete all connections."""
        result = []
        for connection in self:
            try:
                if connection.disconnect():
                    result.append(connection)
            except (exceptions.NodeDeletedError, exceptions.AttributeNotFoundError):
                pass
        return ConnectionList(result)


class ConnectionProxy(ConnectionList):
    """Hold the connection data to lazily load connections.
    By default, both the source and destination connections will be
    loaded, but either can be requested with the respective property.

    The data contained by the class instance is not live, but in the
    case a reload is required, there is a method to handle that.
    """

    __slots__ = ['_connections', '_sourceConnections', '_destinationConnections']

    def __init__(self):
        self._sourceConnections = None
        self._destinationConnections = None
        self._connections = []

    def __repr__(self):
        self._load()
        return self._connections.__repr__()

    def __iter__(self):
        self._load()
        return self._connections.__iter__()

    def __getitem__(self, idx):
        self._load()
        return self._connections.__getitem__(idx)

    def __len__(self):
        self._load()
        return self._connections.__len__()

    def __eq__(self, other):
        self._load()
        return self._connections == other

    def __ne__(self, other):
        self._load()
        return self._connections != other

    def __contains__(self, other):
        self._load()
        return other in self._connections

    @property
    def inputs(self):
        """Get the input/source connections."""
        self._load(source=True, destination=False)
        return ConnectionList(self._sourceConnections)

    @property
    def outputs(self):
        """Get the output/destination connections."""
        self._load(source=False, destination=True)
        return ConnectionList(self._destinationConnections)

    @property
    def plugs(self):
        """Get the `MPlug` objects.
        Requires override.
        """
        raise NotImplementedError

    def _load(self, source=True, destination=True):
        """Get the connection data from the plugs."""
        # Ensure the data is only loaded once
        if destination:
            if self._destinationConnections is None:
                self._destinationConnections = []
            else:
                destination = False
        if source:
            if self._sourceConnections is None:
                self._sourceConnections = []
            else:
                source = False
        if not source and not destination:
            return

        # Get the connections for each plug
        for currentPlug in self.plugs:
            if destination:
                for connectedPlug in currentPlug.connectedTo(False, True):
                    self._destinationConnections.append(Connection(self.node, currentPlug, connectedPlug))
            if source:
                for connectedPlug in currentPlug.connectedTo(True, False):
                    self._sourceConnections.append(Connection(self.node, currentPlug, connectedPlug, reverse=True))

        # Add to main list
        if destination:
            self._connections.extend(self._destinationConnections)
        if source:
            self._connections.extend(self._sourceConnections)

    def reload(self):
        """Refresh all the loaded data."""
        self._destinationConnections = self._sourceConnections = None
        self._connections = []


class AttributeConnectionProxy(ConnectionProxy):
    """Connection proxy for Attributes."""

    __slots__ = ['_attr']

    def __init__(self, attr):
        super(AttributeConnectionProxy, self).__init__()
        self._attr = attr

    @property
    def attr(self):
        """Get the attribute."""
        return self._attr

    @property
    def node(self):
        """Get the node."""
        return self._attr.node

    @property
    def plugs(self):
        """Get the attribute `MPlug` objects."""
        return self._attr.api.plugs


class NodeConnectionProxy(ConnectionProxy):
    """Connection proxy for Nodes."""

    __slots__ = ['_node']

    def __init__(self, node):
        super(NodeConnectionProxy, self).__init__()
        self._node = node

    @property
    def node(self):
        """Get the node."""
        return self._node

    @property
    def plugs(self):
        """Get the node `MPlug` objects."""
        return self._node.api.dependencyNode.getConnections()


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .node import Node
from .node.attributes import Attribute
