from __future__ import absolute_import

import maya.api.OpenMaya as om2
import maya.cmds as mc

from .... import exceptions, types, utils


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

    Raises:
        NotImplementedError: If the type is not yet supported.
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

    elif apiType == om2.MFn.kMessageAttribute:
        raise RuntimeError('Message attributes have no data values')  # Match the mc.getAttr error

    raise NotImplementedError(attribute.apiTypeStr)


def _setPlugValue(plug, value):
    """Recursively set the plug value.
    This assumes the correct data types are given.

    Warning: Does not work with undo.
    """
    if isinstance(value, (str, unicode, types.StrMixin)):
        plug.setString(value)
    elif isinstance(value, float):
        plug.setFloat(value)
    elif isinstance(value, int):
        plug.setInt(value)
    elif isinstance(value, bool):
        plug.setBool(value)
    elif isinstance(value, (list, tuple)):
        for i, val in enumerate(value):
            _setPlugValue(plug.child(i), val)
    else:
        raise NotImplementedError(type(value))


class NodeAttributes(dict):
    """Lazy dictionary storing a cache of all the Attribute values.
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
        if isinstance(attr, om2.MPlug):
            attrName = attr.partialName(useLongNames=True)
        else:
            attrName = attr

        # Skip any attribute with multiple path parts at this stage
        # eg. pCubeShape1.uvSet[-1].uvSetName / lambert1.lightDataArray.lightDirection
        if '.' in attrName:
            return False

        if not reload and super(NodeAttributes, self).__contains__(attrName):
            return False

        value = Attribute(self.node, attr)
        super(NodeAttributes, self).__setitem__(attrName, value)
        return True

    def _ensureAttrs(self, reload=False):
        """Load in all attribute proxies if required.

        Equivalent:
            `mc.listAttr(self)`

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self.node)
        if not reload and self._loaded:
            return

        depNode = self.node.api.dependencyNode
        attrs = map(depNode.attribute, range(depNode.attributeCount()))
        for attr in attrs:
            self._ensureAttr(depNode.findPlug(attr, False))

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


def _getPlugFromDepNode(depNode, attr):
    """Follow a valid attribute path to the correct plug.
    Returns None in the case of failure.
    """
    children = []
    for child in attr.split('.'):
        if child[-1] == ']':
            children.extend(child[:-1].split('['))
        else:
            children.append(child)

    try:
        plug = depNode.findPlug(children[0], False)
    except RuntimeError as e:
        if str(e) == '(kInvalidParameter): Object is incompatible with this method':
            return None
        raise

    for child in children[1:]:
        if plug.isArray:
            plug = plug.elementByLogicalIndex(int(child))
        elif plug.isCompound:
            for plug in map(plug.child, range(plug.numChildren())):
                if plug.name().endswith('.' + child):
                    break
            else:
                return None

    return plug


class Attribute(types.StrMixin):
    """Easy way of handling attribute values and connections.

    A value is read and set using `.value`.
    A connection is made by using the >> operator between two attributes.
    """

    __slots__ = ['node', 'attr', 'api', '_keyframes', '_compoundChildren']

    class ApiData(object):
        """Hold the OpenMaya API objects."""

        __slots__ = ['_plug', '_attribute']

        def __init__(self, plug):
            """Store the plug.

            If the plug is networked, then convert to non networked, as
            otherwise all sorts of crashes and instability can happen
            by holding the plug in memory.
            """
            self._plug = utils.unnetworkPlug(plug)
            self._attribute = None

        @classmethod
        def fromNode(cls, node, attr):
            """Get an attribute from a Node instance.

            Raises:
                AttributeNotFoundError
            """
            plug = _getPlugFromDepNode(node.api.dependencyNode, attr)
            if plug is None:
                raise exceptions.AttributeNotFoundError(node, attr)
            return cls(plug)

        @classmethod
        def fromAttr(cls, attr):
            """Get an attribute from an attribute string.

            Raises:
                AttributeNotFoundError
                NodeNotFoundError
            """
            node, attr = attr.split('.', 1)

            selection = om2.MSelectionList()
            try:
                selection.add(node)
            except RuntimeError as e:
                if str(e) == '(kInvalidParameter): Object does not exist':
                    raise exceptions.NodeNotFoundError(node)
                raise
            dependNode = selection.getDependNode(0)
            dependencyNode = om2.MFnDependencyNode(dependNode)

            plug = _getPlugFromDepNode(dependencyNode, attr)
            if plug is None:
                raise exceptions.AttributeNotFoundError(node, attr)
            return cls(plug)

        @property
        def plug(self):
            """Get the `MPlug`.

            Notable methods:
                `name()`
                `partialName(useFullAttributePath=True)`
            """
            return self._plug

        @property
        def plugs(self):
            """Get all the `MPlug` objects in the case of arrays."""
            if self.plug.isArray:
                return [self.plug.elementByPhysicalIndex(i) for i in range(self.plug.numElements())]
            return [self.plug]

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

    def __init__(self, node, attr):
        """Create the attribute proxy.

        Parameters:
            node (Node): Instance of the current node.
            attr (str|MPlug): Attribute of the node.
                If using a networked plug that is attached to an
                attribute that no longer exists, then Maya will crash.
        """
        self.node = node
        if isinstance(attr, om2.MPlug):
            self.api = Attribute.ApiData(attr)
            self.attr = self.api.plug.partialName(useLongNames=True)

        else:
            self.attr = attr
            self.api = Attribute.ApiData.fromNode(self.node, attr)

        self._keyframes = AttributeKeyframes(self)
        self._compoundChildren = None

    @classmethod
    def ls(self, attr):
        """Search the scene for an attribute."""
        result = utils.runAndLog(mc.ls, '*.' + attr)
        split = (item.split('.', 1) for item in result)
        return [Attribute(Node(node), attr) for node, attr in split]

    def __bool__(self):
        return self.exists
    __nonzero__ = __bool__

    def __eq__(self, value):
        if value == self.attr:
            return True
        return super(Attribute, self).__eq__(value)

    def __float__(self):
        return float(self.value)

    def __int__(self):
        return int(self.value)

    def __add__(self, value):
        """Allow attribute names to be added to.

        >>> Attribute('node.val') + 'ue'
        Attribute('node.value')
        """
        return type(self)(self.node, self.attr + value)

    def __rshift__(self, connection):
        """Create an outgoing connection.

        >>> Attribute('node.attr') >> 'othernode.attr'
        """
        return self.connect(connection)

    def __rrshift__(self, connection):
        """Create an incoming connection.

        >>> 'othernode.attr' >> Attribute('node.attr')
        """
        return self.connect(connection, reverse=True)

    def __floordiv__(self, connection):
        """Break an outgoing connection.

        >>> Attribute('node.attr') // 'othernode.attr'
        """
        return self.disconnect(connection)

    def __rfloordiv__(self, connection):
        """Break an incoming connection.

        >>> 'othernode.attr' // Attribute('node.attr')
        """
        return self.disconnect(connection, reverse=True)

    def split(self, *args, **kwargs):
        """Add the ability to split for backwards compatibility."""
        return self.name.split(*args, **kwargs)

    @property
    def exists(self):
        """Determine if the attribute already exists.

        Equivelant:
            `mc.attributeQuery(attr, node=node, exists=True)`.

        This should be done before calling any plug methods as an
        invalid plug can cause Maya crashes.

        Note that deleting an attribute does not invalidate the plug,
        but it does update the dependency node. Deleting a node does
        the opposite with networked plugs, but any other plugs are left
        as valid. A check on the parent node is needed for these.
        """
        plug = self.api.plug
        if plug.isNull:
            return False
        if not self.node.exists:
            return False

        # TODO: Test what happens when parent attribute is deleted
        if plug.isElement:
            return True
        if plug.isChild:
            return True

        return self.node.api.dependencyNode.hasAttribute(self.attr)

    @property
    def type(self):
        """Get the attribute type.

        Returns:
            Python type for standard attributes.
            Tuple of types if a compound attribute.
            List of a single type if an array attribute.
            String if unsupported (eg. "enum").
        """
        if not self.api.plug.isNull:
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
        if not self.api.plug.isNull:
            return self.api.plug.name()
        return '{}.{}'.format(self.node, self.attr)

    @property
    def value(self):
        """Get an attribute value."""
        if not self.api.plug.isNull:
            try:
                return _getPlugValue(self.api.plug)
            except NotImplementedError:
                pass
        return utils.runAndLog(mc.getAttr, self)

    @value.setter
    def value(self, value):
        """Set a new attribute value.

        Raises:
            NodeDeletedError
            AttributeLockedError
            AttributeConnectedError
        """
        utils.logger.info('Setting %s value: %r', self, value)
        utils.raiseIfNodeNotFound(self.node)
        if not self.api.plug.isNull:
            if self.api.plug.isLocked:
                raise exceptions.AttributeLockedError(self.node, self.attr)
            if self.api.plug.isConnected:
                raise exceptions.AttributeConnectedError(self.node, self.attr)

        if isinstance(value, (str, unicode, types.StrMixin)):
            utils.runAndLog(mc.setAttr, self, value, type='string')
        elif isinstance(value, (tuple, list)):
            utils.runAndLog(mc.setAttr, self, *value)
        else:
            utils.runAndLog(mc.setAttr, self, value)

    @property
    def locked(self):
        """Get the node locked state."""
        if not self.api.plug.isNull:
            return self.api.plug.isLocked
        return utils.runAndLog(mc.getAttr, self, lock=True)

    @locked.setter
    def locked(self, value):
        """Set the node locked state.

        Raises:
            NodeDeletedError
        """
        utils.logger.info('Setting %s locked state: %r', self, value)
        utils.raiseIfNodeNotFound(self.node)
        utils.runAndLog(mc.setAttr, self, lock=value)

    @property
    def keyable(self):
        """Get the node keyable state."""
        if not self.api.plug.isNull:
            return self.api.plug.isKeyable
        return utils.runAndLog(mc.getAttr, self, keyable=True)

    @keyable.setter
    def keyable(self, value):
        """Set the node keyable state.

        Raises:
            NodeDeletedError
        """
        utils.logger.info('Setting %s keyable state: %s', self, value)
        utils.raiseIfNodeNotFound(self.node)
        utils.runAndLog(mc.setAttr, self, keyable=value)

    def connect(self, target, reverse=False):
        """Create a connection.
        Set `reverse` to reverse the connection direction.

        Raises:
            AttributeNotFoundError: If the source or destination
                attribute is not found.
            NodeNotFoundError: If the destination node was not found.

        Returns:
            True if successful otherwise False
        """
        if not self.exists:
            raise exceptions.AttributeNotFoundError(self.node, self.attr)

        if isinstance(target, Attribute):
            plug = target.api.plug
        elif isinstance(target, om2.MPlug):
            plug = target
        else:
            plug = Attribute.ApiData.fromAttr(target).plug

        return Connection(self.node, self.api.plug, plug, reverse=reverse).connect()

    def disconnect(self, target, reverse=False):
        """Remove a connection.
        Set `reverse` to reverse the direction.

        Raises:
            AttributeNotFoundError: If the source or destination
                attribute was not found.
            NodeNotFoundError: If the destination node is not valid.

        Returns:
            True if successful otherwise False
        """
        if not self.exists:
            raise exceptions.AttributeNotFoundError(self.node, self.attr)

        if isinstance(target, Attribute):
            plug = target.api.plug
        elif isinstance(target, om2.MPlug):
            plug = target
        else:
            plug = Attribute.ApiData.fromAttr(target).plug

        return Connection(self.node, self.api.plug, plug, reverse=reverse).disconnect()

    @property
    def connections(self):
        """Get the attribute connections as plugs."""
        if self.api.plug.isNull:
            return []
        return AttributeConnectionProxy(self)

    def ensure(self, attrType, **kwargs):
        """Create the attribute if it doesn't exist."""
        if self.exists:
            return self
        return self.connect(attrType, **kwargs)

    def delete(self):
        """Delete the attribute.

        Raises:
            NodeDeletedError
            RuntimeError: Cannot delete static attribute 'pCube1.translate' from node 'pCube1'.
            RuntimeError: Cannot delete child 'pCube1.translateX' of compound attribute 'translate'.
        """
        utils.logger.info('Deleting attribute: %s', self)
        utils.raiseIfNodeNotFound(self.node)
        utils.runAndLog(mc.deleteAttr, self)

    @property
    def keyframes(self):
        """Get the keyframe dict."""
        return self._keyframes

    def __iter__(self):
        """Iterate over array children."""
        plug = self.api.plug

        # If array, create a live up to date copy of the children
        if plug.isArray:
            plugs = map(plug.elementByPhysicalIndex, range(plug.numElements()))
            return iter(Attribute(self.node, plug) for plug in plugs)

        # If compound, then regenerate any children previously stored
        if plug.isCompound:
            self._reloadCompoundChildren()
            return iter(self._compoundChildren.values())

        return []

    def __getitem__(self, value):
        """Get a child attribute.

        Raises:
            TypeError: plug is not an array or compound
            TypeError: array indexes must be integers
            IndexError: array index out of range
            KeyError: compound attribute does not exist

        TODO:
            Tests
        """
        plug = self.api.plug
        if plug.isArray:
            if not isinstance(value, int):
                raise TypeError('array indexes much be integers, not {}'.format(type(value)))
            if not 0 <= value < plug.numElements():
                raise IndexError('array index "{}" out of range'.format(value))
            return Attribute(self.node, plug.elementByPhysicalIndex(value))

        elif plug.isCompound:
            # Load the child plugs if not already loaded
            if self._compoundChildren is None or value not in self._compoundChildren:
                self._reloadCompoundChildren()

            try:
                return self._compoundChildren[value]
            except KeyError:
                raise KeyError('compound attribute "{}" does not exist'.format(value))

        raise TypeError('plug is not an array or compound')

    def keys(self):
        """Get all child element indexes or names."""
        plug = self.api.plug
        if plug.isArray:
            return list(range(plug.numElements()))
        if plug.isCompound:
            self._reloadCompoundChildren()
            return self._compoundChildren.keys()
        return []

    def items(self):
        """Get the name and attribute of all children."""
        plug = self.api.plug
        if plug.isArray:
            for i in range(plug.numElements()):
                yield i, Attribute(self.node, plug.elementByPhysicalIndex(i))

        elif plug.isCompound:
            self._reloadCompoundChildren()
            for k, v in self._compoundChildren.items():
                yield k, v

    def __len__(self):
        """Get the number of child attributes."""
        plug = self.api.plug
        if plug.isArray:
            return plug.numElements()
        if plug.isCompound:
            return plug.numChildren()
        return 0

    def _reloadCompoundChildren(self):
        """Load all the children of a compound plug.

        Raises:
            TypeError: plug is not a compound
        """
        if not self.api.plug.isCompound:
            raise TypeError('plug is not a compound')
        childPlugs = map(self.api.plug.child, range(self.api.plug.numChildren()))
        childAttrs = (Attribute(self.node, plug) for plug in childPlugs)
        self._compoundChildren = {attr.name.rsplit('.', 1)[-1]: attr for attr in childAttrs}

    @property
    def uvLinks(self):
        """Get the nodes linked to this UV set attribute.

        TODO:
            Tests
        """
        links = utils.runAndLog(mc.uvLink, query=True, uvSet=self.name)
        return [Node(link) for link in links]


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .keyframes import AttributeKeyframes
from ...connection import AttributeConnectionProxy, Connection
from ...node import Node
