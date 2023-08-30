from __future__ import absolute_import

import maya.cmds as mc

from .keyframes import AttributeKeyframes
from ... import types, utils


if str is not bytes:
    unicode = str  # pylint:disable=invalid-name


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

    def __iter__(self):
        self._ensureAttrs()
        return super(NodeAttributes, self).__iter__()

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
        for attr in utils.runAndLog(mc.listAttr, self.node):
            self._ensureAttr(attr)
        self._loaded = True


class AttributeProxy(types.StrMixin):
    """Easy way of handling attribute values and connections.
    A value is read and set using `.value`.
    A connection is made by using the >> operator between two attributes.
    """

    __slots__ = ['node', 'attr', '_keyframes']

    ATTR_TYPES = {
        'bool': bool,
        'byte': int,
        'short': int,
        'short2': (int, int),
        'short3': (int, int, int),
        'long': int,
        'long2': (int, int),
        'long3': (int, int, int),
        'int32Array': [int],
        'char': str,
        'string': str,
        'stringArray': [str],
        'double': float,
        'double2': (float, float),
        'double3': (float, float, float),
        'doubleArray': [float],
        'float': float,
        'float2': (float, float),
        'float3': (float, float, float),
        'floatArray': [float],
        'int3': (int, int, int),
    }

    def __init__(self, node, attr):
        self.node = node
        self.attr = attr
        self._keyframes = AttributeKeyframes(self)

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
        if isinstance(connection, AttributeProxy):
            connection = connection.name

        if reverse:
            utils.logger.info('Creating connection: %s >> %s', connection, self)
            utils.runAndLog(mc.connectAttr, connection, self, force=True)
        else:
            utils.logger.info('Creating connection: %s >> %s', self, connection)
            utils.runAndLog(mc.connectAttr, self, connection, force=True)

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
        return utils.runAndLog(mc.attributeQuery, self.attr, node=self.node.name, exists=True)

    @property
    def type(self):
        """Get the attribute type.
        Returns:
            Python type for standard attributes.
            Tuple of types if a compound attribute.
            List of a single type if an array attribute.
            String if unsupported.
        """
        attrType = utils.runAndLog(mc.getAttr, self, type=True)
        return self.ATTR_TYPES.get(attrType, attrType)

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
        return utils.runAndLog(mc.getAttr, self)

    @value.setter
    def value(self, value):
        """Set a new attribute value."""
        utils.logger.info('Setting %s value: %r', self, value)
        if isinstance(value, (str, unicode, types.StrMixin)):
            utils.runAndLog(mc.setAttr, self, value, type='string')
        elif isinstance(value, (tuple, list, set)):
            utils.runAndLog(mc.setAttr, self, *value)
        else:
            utils.runAndLog(mc.setAttr, self, value)

    @property
    def locked(self):
        """Get the node locked state.
        Raises:
            ValueError: "No object matches name: {self.name}"
        """
        return utils.runAndLog(mc.getAttr, self, lock=True)

    @locked.setter
    def locked(self, value):
        """Set the node locked state.
        Raises:
            ValueError: "setAttr: No object matches name: {self.name}"
        """
        utils.logger.info('Setting %s locked state: %r', self, value)
        utils.runAndLog(mc.setAttr, self, lock=value)

    @property
    def keyable(self):
        """Get the node keyable state.
        Raises:
            ValueError: "No object matches name: {self.name}"
        """
        return utils.runAndLog(mc.getAttr, self, keyable=True)

    @keyable.setter
    def keyable(self, value):
        """Set the node keyable state.
        Raises:
            ValueError: "setAttr: No object matches name: {self.name}"
        """
        utils.logger.info('Setting %s keyable state: %s', self, value)
        utils.runAndLog(mc.setAttr, self, keyable=value)

    @property
    def connections(self):
        """Get the node connections as plugs.
        Raises:
            ValueError: "No object matches name: {self.name}"
        """
        connections = []
        for nodeAttr in utils.runAndLog(mc.listConnections, self, plugs=True) or ():
            node, attr = nodeAttr.split('.', 1)
            connections.append(type(self)(type(self.node)(node), attr))
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

        utils.logger.info('Adding attribute %s with arguments %s', self, kwargs)
        utils.runAndLog(mc.addAttr, self.node, longName=self.attr, **kwargs)
        return self

    def ensure(self, attrType, **kwargs):
        """Create the attribute if it doesn't exist."""
        if self.exists:
            return self
        return self.create(attrType, **kwargs)

    def delete(self):
        """Delete the attribute."""
        utils.logger.info('Deleting attribute: %s', self)
        utils.runAndLog(mc.deleteAttr, self)

    @property
    def keyframes(self):
        """Get the keyframe dict."""
        return self._keyframes
