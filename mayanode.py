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


class AttributeProxy(object):
    """Easy way of handling attribute values and connections.

    A value is read and set using `.value`.
    A connection is made by using the >> operator between two attributes.
    """

    __slots__ = ['node', 'attr']

    def __init__(self, node, attr):
        self.node = node
        self.attr = attr

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self.name)

    def __bool__(self):
        return bool(mc.ls(self.name))
    __nonzero__ = __bool__

    def __str__(self):
        return str(self.value)

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

    def __rshift__(self, connection):
        """Create an outgoing connection.

        >>> AttributeProxy('node.attr') >> 'othernode.attr'
        """
        if isinstance(connection, type(self)):
            connection = connection.name
        logger.debug('Creating connection: %s >> %s', self.name, connection)
        mc.connectAttr(self.name, connection, force=True)

    def __rrshift__(self, connection):
        """Create an incoming connection.

        >>> 'othernode.attr' >> AttributeProxy('node.attr')
        """
        if isinstance(connection, type(self)):
            connection = connection.name
        logger.debug('Creating connection: %s >> %s', connection, self.name)
        mc.connectAttr(connection, self.name, force=True)

    @property
    def name(self):
        """Get the full node and attribute name for Maya to use."""
        return '{}.{}'.format(self.node, self.attr)

    @property
    def value(self):
        """Get an attribute value."""
        logger.debug('Reading %s value', self.name)
        return mc.getAttr(self.name)

    @value.setter
    def value(self, value):
        """Set a new attribute value."""
        logger.debug('Setting %s value: %r', self.name, value)
        mc.setAttr(self.name, value)

    @property
    def locked(self):
        """Get the node locked state."""
        logger.debug('Reading %s locked state', self.name)
        return mc.getAttr(self.name, lock=True)

    @locked.setter
    def locked(self, value):
        """Set the node locked state."""
        logger.debug('Setting %s locked state: %r', self.name, value)
        mc.setAttr(self.name, lock=value)

    @property
    def keyable(self):
        """Get the node keyable state."""
        logger.debug('Reading %s keyable state', self.name)
        return mc.getAttr(self.name, keyable=True)

    @keyable.setter
    def keyable(self, value):
        """Set the node keyable state."""
        logger.debug('Setting %s keyable state: %s', self.name, value)
        mc.setAttr(self.name, keyable=value)


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
        """Load in all attribute proxies if required."""
        if not reload and self._loaded:
            return
        logger.debug('Building full attribute list for %s', self.node)
        for attr in mc.listAttr(str(self.node)):
            self._ensureAttr(attr)
        self._loaded = True


class Node(object):
    """Object orientated approach to nodes."""

    __slots__ = ['_name', '_attrs']

    NODE_TYPES = {
        'shader': set(mc.listNodeTypes('shader')),
    }

    def __init__(self, name):
        self._name = name
        self._attrs = NodeAttributes(self)

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self._name)

    def __new__(cls, name):
        """Create a new node, or attribute proxy if an attribute was given."""
        if '.' in name:
            node, attr = name.split('.', 1)
            return cls(node).attrs[attr]
        return super(Node, cls).__new__(cls, name)

    def __add__(self, attr):
        """Get a new object or attribute."""
        if attr[0] == '.':
            return self.attrs[attr[1:]]
        return type(self)(str(self) + attr)

    def __str__(self):
        return self._name

    @classmethod
    def create(cls, nodeType, name=None, **kwargs):
        """Create a new node."""
        kwargs = {}
        if name is not None:
            kwargs['name'] = name

        # Create shading node
        if nodeType in cls.NODE_TYPES['shader']:
            return cls(mc.shadingNode(nodeType, asShader=True, **kwargs))

        # Create shading engine
        elif nodeType == 'shadingEngine':
            kwargs.setdefault('renderable', True)
            kwargs.setdefault('noSurfaceShader', True)
            kwargs.setdefault('empty', True)
            return cls(mc.sets(**kwargs))

        # Create other
        return cls(mc.createNode(nodeType, **kwargs))

    @property
    def attrs(self):
        """Get the attr dict."""
        return self._attrs

    @property
    def name(self):
        """Get the node name."""
        return self._name

    @name.setter
    def name(self, name):
        """Set a new node name."""
        mc.rename(self, name)
        self._name = name
