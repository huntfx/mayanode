"""A WIP implementation of an object orientated way of dealing with nodes.

Examples:
    # Create a node
    >>> Node.create('lambert')
    Node('lambert2')

    # Get an existing node
    >>> lambert = Node('lambert2')

    # Attribute values
    >>> lambert.attrs['diffuse'] = 1
    >>> lambert.attrs['diffuse']
    NodeAttribute('pCube1.diffuse')
    >>> lambert.attrs['diffuse'].value
    1.0
    >>> float(lambert.attrs['diffuse'])
    1.0
    >>> mc.getAttr(lambert + '.diffuse')
    1.0

    # Attribute states
    >>> lambert.attrs['diffuse'].lock = True
    >>> lambert.attrs['diffuse'] = 0
    RuntimeError: setAttr: The attribute 'lambert2.diffuse' is locked or connected and cannot be modified.
    >>> lambert.attrs['diffuse'].keyable
    True

    # Outgoing attribute connections
    >>> lambert.attrs['diffuse'] >> 'lambert1.diffuse'

    # Incoming connections
    >>> 'lambert1.refractions' >> lambert.attrs['refractions']

    # Rename node
    >>> attr = lambert.attrs['diffuse']
    >>> lambert.name = 'lambert3'
    >>> attr
    NodeAttribute('lambert3.diffuse')
"""

from __future__ import absolute_import

import logging

import maya.cmds as mc


logger = logging.getLogger(__name__)

if str is not bytes:
    unicode = str


class StrMixin(object):  # pylint: disable=useless-object-inheritance
    """Add methods to make the classes behave like strings."""

    def __str__(self):
        return self.name

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self.name)

    def __contains__(self, value):
        return self.name.__contains__(value)

    def split(self, *args, **kwargs):
        return self.name.split(*args, **kwargs)


class AttributeProxy(StrMixin):
    """Easy way of handling attribute values and connections.

    A value is read and set using `.value`.
    A connection is made by using the >> operator between two attributes.
    """

    __slots__ = ['node', 'attr']

    def __init__(self, node, attr):
        self.node = node
        self.attr = attr

    def __bool__(self):
        return self.exists
    __nonzero__ = __bool__

    def __float__(self):
        return float(self.value)

    def __int__(self):
        return int(self.value)

    def __add__(self, value):
        """Allow attribute names to be added to.

        >>> AttributeProxy('node.val') + 'ue'
        AttributeProxy('node.value')
        """
        return type(self)(self.node, self.attr + value)

    def connect(self, connection, reverse=False):
        """Create a connection.
        Set `reverse` to reverse the connection direction.

        >>> AttributeProxy('node.attr').connect('othernode.attr1')
        >>> AttributeProxy('node.attr').connect('othernode.attr2', reverse=True)
        """
        if isinstance(connection, type(self)):
            connection = connection.name

        if reverse:
            logger.debug('Creating connection: %s >> %s', connection, self.name)
            mc.connectAttr(connection, self.name, force=True)
        else:
            logger.debug('Creating connection: %s >> %s', self.name, connection)
            mc.connectAttr(self.name, connection, force=True)

    def __rshift__(self, connection):
        """Create an outgoing connection.

        >>> AttributeProxy('node.attr') >> 'othernode.attr'
        """
        self.connect(connection)

    def __rrshift__(self, connection):
        """Create an incoming connection.

        >>> 'othernode.attr' >> AttributeProxy('node.attr')
        """
        self.connect(connection, reverse=True)

    def split(self, *args, **kwargs):
        """Add the ability to split for backwards compatibility."""
        return self.name.split(*args, **kwargs)

    @property
    def exists(self):
        """Determine if the attribute already exists."""
        return mc.attributeQuery(self.attr, node=self.node, exists=True)

    @property
    def type(self):
        """Get the attribute type.

        Raises:
            ValueError: "No object matches name: {self.name}"
        """
        logger.debug('Reading %s type', self.name)
        attrType = mc.getAttr(self.name, type=True)
        if attrType == 'bool':
            return bool
        elif attrType in ('long', 'short'):
            return int
        elif attrType == 'string':
            return str
        elif attrType in ('double', 'float'):
            return float
        return attrType

    @property
    def name(self):
        """Get the full node and attribute name for Maya to use."""
        return '{}.{}'.format(self.node, self.attr)

    @property
    def value(self):
        """Get an attribute value.

        Raises:
            ValueError: "No object matches name: {self.name}"
        """
        logger.debug('Reading %s value', self.name)
        return mc.getAttr(self.name)

    @value.setter
    def value(self, value):
        """Set a new attribute value.

        Raises:
            ValueError: "setAttr: No object matches name: {self.name}"
        """
        logger.debug('Setting %s value: %r', self.name, value)
        if isinstance(value, (str, unicode)):
            mc.setAttr(self.name, value, type='string')
        else:
            mc.setAttr(self.name, value)

    @property
    def locked(self):
        """Get the node locked state.

        Raises:
            ValueError: "No object matches name: {self.name}"
        """
        logger.debug('Reading %s locked state', self.name)
        return mc.getAttr(self.name, lock=True)

    @locked.setter
    def locked(self, value):
        """Set the node locked state.

        Raises:
            ValueError: "setAttr: No object matches name: {self.name}"
        """
        logger.debug('Setting %s locked state: %r', self.name, value)
        mc.setAttr(self.name, lock=value)

    @property
    def keyable(self):
        """Get the node keyable state.

        Raises:
            ValueError: "No object matches name: {self.name}"
        """
        logger.debug('Reading %s keyable state', self.name)
        return mc.getAttr(self.name, keyable=True)

    @keyable.setter
    def keyable(self, value):
        """Set the node keyable state.

        Raises:
            ValueError: "setAttr: No object matches name: {self.name}"
        """
        logger.debug('Setting %s keyable state: %s', self.name, value)
        mc.setAttr(self.name, keyable=value)

    @property
    def connections(self):
        """Get the node connections as plugs.

        Raises:
            ValueError: "No object matches name: {self.name}"
        """
        logger.debug('Reading %s connections', self.name)
        connections = []
        for nodeAttr in mc.listConnections(self.name, plugs=True) or ():
            node, attr = nodeAttr.split('.', 1)
            connections.append(type(self)(Node(node), attr))
        return connections

    def create(self, attrType=None, **kwargs):
        """Create the attribute.

        Raises:
            ValueError: "No object matches name: {self.name}"
        """
        if attrType is not None:
            if attrType is bool:
                kwargs['attributeType'] = 'bool'
            elif attrType is int:
                kwargs['attributeType'] = 'long'
            elif attrType is str:
                kwargs['dataType'] = 'string'
            elif attrType is float:
                kwargs['attributeType'] = 'double'
        mc.addAttr(self.node, longName=self.attr, **kwargs)
        return self

    def ensure(self, attrType, **kwargs):
        """Create the attribute if it doesn't exist."""
        if self.exists:
            return self
        return self.create(attrType, **kwargs)

    def delete(self):
        """Delete the attribute."""
        mc.deleteAttr(self.name)


class NodeAttributes(dict):
    """Lazy dictionary storing a cache of all the AttributeProxy values.
    The full list of attributes is not populated until it is requested.
    There is no validation on checking if new attributes already exist.
    """

    __slots__ = ['node', '_loaded']

    def __init__(self, node):
        self.node = node
        self._loaded = False
        super(NodeAttributes, self).__init__()

    def __repr__(self):
        self._ensureAttrs()
        return super(NodeAttributes, self).__repr__()

    def __getitem__(self, attr):
        self._ensureAttr(attr)
        return super(NodeAttributes, self).__getitem__(attr)

    def __setitem__(self, attr, value):
        self[attr].value = value

    def keys(self):
        self._ensureAttrs()
        return super(NodeAttributes, self).keys()

    def values(self):
        self._ensureAttrs()
        return super(NodeAttributes, self).values()

    def items(self):
        self._ensureAttrs()
        return super(NodeAttributes, self).items()

    def _ensureAttr(self, attr, reload=False):
        """Load in the attribute proxy if required."""
        if not reload and attr in self:
            return
        value = AttributeProxy(self.node, attr)
        super(NodeAttributes, self).__setitem__(attr, value)

    def _ensureAttrs(self, reload=False):
        """Load in all attribute proxies if required.

        Raises:
            ValueError: "No object matches name: {self.node}"
        """
        if not reload and self._loaded:
            return
        logger.debug('Building full attribute list for %s', self.node)
        for attr in mc.listAttr(self.node.name):
            self._ensureAttr(attr)
        self._loaded = True


class Node(StrMixin):
    """Object orientated approach to nodes."""

    __slots__ = ['_name', '_attrs']

    NODE_TYPES = {
        'shader': set(mc.listNodeTypes('shader')),
    }

    def __init__(self, name=None):
        if name is not None:
            name = str(name)
        self._name = name
        self._attrs = NodeAttributes(self)

    def __new__(cls, name=None):
        """Create a new node, or attribute proxy if an attribute was given."""
        if isinstance(name, cls):
            return name
        if name and '.' in name:
            node, attr = name.split('.', 1)
            return cls(node).attrs[attr]
        return super(Node, cls).__new__(cls, name)

    def __add__(self, attr):
        """Get a new object or attribute."""
        if attr[0] == '.':
            return self.attrs[attr[1:]]
        return type(self)(str(self) + attr)

    def __eq__(self, other):
        return self.name == other

    def __ne__(self, other):
        return self.name != other

    def __gt__(self, other):
        return self.name > other

    def __ge__(self, other):
        return self.name >= other

    def __lt__(self, other):
        return self.name < other

    def __le__(self, other):
        return self.name <= other

    @property
    def exists(self):
        """Determine if the node exists."""
        if not self._name:
            return False
        logger.debug('Reading if %s exists', self.name)
        return bool(mc.ls(self.name))

    @property
    def type(self):
        """Get the node type.

        Raises:
            RuntimeError: "No object matches name: {self.name}"
        """
        logger.debug('Reading %s type', self.name)
        return mc.nodeType(self.name)

    @property
    def attrs(self):
        """Get the attr dict."""
        return self._attrs

    @property
    def name(self):
        """Get the node name."""
        return self._name or ''

    @name.setter
    def name(self, name):
        """Set a new node name.

        Warnings:
            "New name contains invalid characters. Illegal characters were converted to \"_\"."

        Raises:
            RuntimeError: "New name has no legal characters."
            RuntimeError: "No object matches name"
        """
        logger.debug('Renaming %r to %r', self.name, name)
        self._name = mc.rename(self.name, name)

    @property
    def longName(self):
        """Get the node long name.

        Raises:
            RuntimeError: "No object matches name: {self.name}"
        """
        result = mc.ls(self.name, long=True)
        if result:
            return result[0]
        raise RuntimeError('No object matches name: {}'.format(self.name))

    @property
    def namespace(self):
        """Get the node namespace."""
        parts = self.name.split(':', 1)
        if len(parts) == 1:
            return ':'
        return parts[0]

    @property
    def parents(self):
        """Get the node parents.
        This may be required if the node is instanced.
        """
        return [Node(parent) for parent in mc.listRelatives(self, parent=True, fullPath=True)]

    @property
    def parent(self):
        """Get the node parent."""
        parents = self.parents
        if parents:
            return self.parents[0]
        return None

    @parent.setter
    def parent(self, parent):
        """Set a new node parent."""
        mc.parent(self, parent)

    @property
    def children(self):
        """Get all node children."""
        return [Node(child) for child in mc.listRelatives(self, children=True, fullPath=True)]

    def create(self, nodeType, **kwargs):
        """Create a new node.

        Usage:
            >>> node = Node('myNode')
            >>> node.create('transform')
            Node('myNode')
            >>> node.create('transform')
            Node('myNode1')

        Warnings:
            "Unrecognized node type '{nodeType}'; preserving node information during this session."
        """
        kwargs = {}
        if self._name:
            kwargs['name'] = self._name
        logger.debug('Creating %r node with arguments %s', nodeType, kwargs)

        # Create shading node
        if nodeType in self.NODE_TYPES['shader']:
            self._name = mc.shadingNode(nodeType, asShader=True, **kwargs)

        # Create shading engine
        elif nodeType == 'shadingEngine':
            kwargs.setdefault('renderable', True)
            kwargs.setdefault('noSurfaceShader', True)
            kwargs.setdefault('empty', True)
            self._name = mc.sets(**kwargs)

        # Create other
        else:
            self._name = mc.createNode(nodeType, **kwargs)
        return self

    def ensure(self, nodeType, **kwargs):
        """Make sure the node exists."""
        if self.exists:
            return self
        return self.create(nodeType, **kwargs)

    def delete(self):
        """Delete the node."""
        mc.delete(self)
