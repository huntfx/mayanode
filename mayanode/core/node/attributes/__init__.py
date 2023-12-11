from __future__ import absolute_import

import maya.api.OpenMaya as om2
import maya.cmds as mc

from .keyframes import AttributeKeyframes
from .... import exceptions, types, utils


if str is not bytes:
    unicode = str  # pylint:disable=invalid-name


if str is not bytes:
    unicode = str  # pylint:disable=invalid-name


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
    om2.MFnData.kString: str,
    om2.MFnNumericData.kBoolean: bool,
    om2.MFnNumericData.kInt: int,
    om2.MFnNumericData.kInt64: int,
    om2.MFnNumericData.kShort: int,
    om2.MFnNumericData.kLong: int,
    om2.MFnNumericData.kFloat: float,
    om2.MFnNumericData.kDouble: float,
    om2.MFn.kAttribute2Float: [float, float],
    om2.MFn.kAttribute2Double: [float, float],
    om2.MFn.kAttribute2Int: [int, int],
    om2.MFn.kAttribute2Short: [int, int],
    om2.MFn.kAttribute3Float: [float, float, float],
    om2.MFn.kAttribute3Double: [float, float, float],
    om2.MFn.kAttribute3Int: [int, int, int],
    om2.MFn.kAttribute3Short: [int, int, int],
    om2.MFn.kAttribute4Double: [float, float, float, float],
}


def _getPlugValue(plug):
    """Get the value of the plug as the correct type.
    If unsupported, None will be returned.
    """
    attribute = plug.attribute()
    apiType = attribute.apiType()

    if apiType == om2.MFn.kTypedAttribute:
        attrType = om2.MFnTypedAttribute(attribute).attrType()
        if attrType == om2.MFnData.kString:
            return plug.asString()

    elif apiType == om2.MFn.kNumericAttribute:
        numericType = om2.MFnNumericAttribute(attribute).numericType()
        if numericType == om2.MFnNumericData.kBoolean:
            return plug.asBool()
        if numericType in (om2.MFnNumericData.kInt, om2.MFnNumericData.kInt64, om2.MFnNumericData.kLong):
            return plug.asInt()
        if numericType == om2.MFnNumericData.kFloat:
            return plug.asFloat()
        if numericType == om2.MFnNumericData.kDouble:
            return plug.asDouble()
        if numericType == om2.MFnNumericData.kShort:
            return plug.asShort()

    elif apiType in (om2.MFn.kFloatAngleAttribute, om2.MFn.kDoubleAngleAttribute):
        return plug.asMAngle().asDegrees()  # Equivalent to `math.degrees(plug.asDouble())`
    elif apiType in (om2.MFn.kFloatLinearAttribute, om2.MFn.kDoubleLinearAttribute):
        return plug.asMDistance().asCentimeters()  # Equivalent to `plug.asDouble()`

    elif apiType == om2.MFn.kEnumAttribute:
        return plug.asInt()

    elif apiType == om2.MFn.kAttribute2Float:
        return tuple(plug.child(i).asFloat() for i in range(2))
    elif apiType == om2.MFn.kAttribute2Double:
        return tuple(plug.child(i).asDouble() for i in range(2))
    elif apiType == om2.MFn.kAttribute2Int:
        return tuple(plug.child(i).asInt() for i in range(2))
    elif apiType == om2.MFn.kAttribute2Short:
        return tuple(plug.child(i).asShort() for i in range(2))
    elif apiType == om2.MFn.kAttribute3Float:
        return tuple(plug.child(i).asFloat() for i in range(3))
    elif apiType == om2.MFn.kAttribute3Double:
        return tuple(plug.child(i).asDouble() for i in range(3))
    elif apiType == om2.MFn.kAttribute3Int:
        return tuple(plug.child(i).asInt() for i in range(3))
    elif apiType == om2.MFn.kAttribute3Short:
        return tuple(plug.child(i).asShort() for i in range(3))
    elif apiType == om2.MFn.kAttribute4Double:
        return tuple(plug.child(i).asDouble() for i in range(4))

    raise NotImplementedError(attribute.apiTypeStr)


def _setPlugValue(plug, value):
    """Recursively set the plug value.
    This assumes the correct data types are given.
    """
    if isinstance(value, (str, unicode, types.StrMixin)):
        plug.setString(value)
    elif isinstance(value, float):
        plug.setFloat(value)
    elif isinstance(value, int):
        plug.setInt(value)
    elif isinstance(value, int):
        plug.setBool(value)
    elif isinstance(value, (list, tuple)):
        for i, val in enumerate(value):
            _setPlugValue(plug.child(i), val)
    raise NotImplementedError(type(value))


class _ApiData(object):
    """Hold the OpenMaya API objects for an attribute."""

    __slots__ = ['_plug', '_attribute']

    def __init__(self, plug):
        self._plug = plug
        self._attribute = None

    @classmethod
    def fromNode(cls, node, attr):
        """Get an attribute from a Node instance.

        Raises:
            AttributeNotFoundError
        """
        try:
            plug = node.api.dependencyNode.findPlug(attr, False)
        except RuntimeError as e:
            if str(e) != '(kInvalidParameter): Object is incompatible with this method':
                raise
            raise exceptions.AttributeNotFoundError(node, attr)
        return cls(plug)

    @property
    def plug(self):
        """Get the `MPlug`."""
        return self._plug

    @property
    def attribute(self):
        """Get the `MFnAttribute`.

        Notable methods:
            `name`
            `shortName`
        """
        if self._attribute is None:
            self._attribute = om2.MFnAttribute(self.plug.attribute())
        return self._attribute


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

    def __len__(self):
        self._ensureAttrs()
        return super(NodeAttributes, self).__len__()

    def __contains__(self, value):
        """Determine if the attribute exists on the node."""
        if not self._loaded:
            if super(NodeAttributes, self).__contains__(value):
                return True
            if self.node.api.dependencyNode.hasAttribute(value):
                self._ensureAttr(value)
                return True
            return False
        return super(NodeAttributes, self).__contains__(value)

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
        if not reload and super(NodeAttributes, self).__contains__(attr):
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
            # Skip compound attributes, not yet supported (eg. lambert1.lightDataArray.lightDirection)
            if '.' in attr:
                continue
            self._ensureAttr(attr)
        self._loaded = True

    def create(self, attr, attrType=None, **kwargs):
        """Create the attribute."""
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
        utils.runAndLog(mc.addAttr, self.node, longName=attr, **kwargs)
        return self.__getitem__(attr)


class AttributeProxy(types.StrMixin):
    """Easy way of handling attribute values and connections.

    A value is read and set using `.value`.
    A connection is made by using the >> operator between two attributes.
    """

    __slots__ = ['node', 'attr', 'api', '_keyframes']


    def __init__(self, node, attr):
        self.node = node
        if isinstance(attr, om2.MPlug):
            self.api = _ApiData(attr)
            self.attr = self.api.attribute.name

        else:
            self.attr = attr
            self.api = _ApiData.fromNode(self.node, attr)

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
        return self.node.api.dependencyNode.hasAttribute(self.attr)
        # return utils.runAndLog(mc.attributeQuery, self.attr, node=self.node.name, exists=True)

    @property
    def type(self):
        """Get the attribute type.

        Returns:
            Python type for standard attributes.
            Tuple of types if a compound attribute.
            List of a single type if an array attribute.
            String if unsupported (eg. "enum").
        """
        if self.api:
            attribute = self.api.plug.attribute()
            apiType = attribute.apiType()

            if apiType == om2.MFn.kTypedAttribute:
                attrType = om2.MFnTypedAttribute(attribute).attrType()
                if attrType in ATTR_TYPES:
                    return ATTR_TYPES[attrType]

            elif apiType == om2.MFn.kNumericAttribute:
                numericType = om2.MFnNumericAttribute(attribute).numericType()
                if numericType in ATTR_TYPES:
                    return ATTR_TYPES[numericType]

            elif apiType == om2.MFn.kEnumAttribute:
                return 'enum'  # Match the getAttr result

        attrType = utils.runAndLog(mc.getAttr, self, type=True)
        return ATTR_TYPES.get(attrType, attrType)

    @property
    def name(self):
        """Get the full node and attribute name for Maya to use."""
        if self.api:
            return self.api.plug.name()
        return '{}.{}'.format(self.node, self.attr)

    @property
    def value(self):
        """Get an attribute value."""
        if self.api:
            try:
                return _getPlugValue(self.api.plug)
            except NotImplementedError:
                pass
        return utils.runAndLog(mc.getAttr, self)

    @value.setter
    def value(self, value):
        """Set a new attribute value."""
        utils.logger.info('Setting %s value: %r', self, value)
        if self.api:
            while True:
                try:
                    _setPlugValue(self.api.plug, value)
                except NotImplementedError:
                    break
                return

        if isinstance(value, (str, unicode, types.StrMixin)):
            utils.runAndLog(mc.setAttr, self, value, type='string')
        elif isinstance(value, (tuple, list)):
            utils.runAndLog(mc.setAttr, self, *value)
        else:
            utils.runAndLog(mc.setAttr, self, value)

    @property
    def locked(self):
        """Get the node locked state."""
        if self.api:
            return self.api.plug.isLocked
        return utils.runAndLog(mc.getAttr, self, lock=True)

    @locked.setter
    def locked(self, value):
        """Set the node locked state."""
        utils.logger.info('Setting %s locked state: %r', self, value)
        utils.runAndLog(mc.setAttr, self, lock=value)

    @property
    def keyable(self):
        """Get the node keyable state."""
        if self.api:
            return self.api.plug.isKeyable
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
        """Get the node connections as plugs."""
        cls = type(self)
        Node = type(self.node)

        connections = []
        if self.api:
            for plug in self.api.plug.connectedTo(True, True):
                node = plug.node()
                connections.append(cls(Node(node), plug))
        else:
            for nodeAttr in utils.runAndLog(mc.listConnections, self, plugs=True) or ():
                node, attr = nodeAttr.split('.', 1)
                connections.append(cls(Node(node), attr))
        return connections

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
