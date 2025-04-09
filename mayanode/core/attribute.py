from __future__ import absolute_import

import re

import maya.api.OpenMaya as om2  # type: ignore
import maya.cmds as mc  # type: ignore

from .. import exceptions, types, utils
from ..type_hints import TYPE_CHECKING
from ..types import StrLike

if TYPE_CHECKING:
    from typing import Any, Dict, Iterator, List, Optional, Tuple, Type, Union
    from typing import KeysView, ValuesView, ItemsView


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
    'doubleLinear': float,
    'doubleArray': [float],
    'doubleAngle': float,
    'float': float,
    'float2': (float, float),
    'float3': (float, float, float),
    'floatArray': [float],
    'int3': (int, int, int),
}


def _getPlugData(attr, plug=None, value=True):
    # type: (Attribute, Optional[om2.MPlug], bool) -> Optional[Any]
    """Get the type or value of a plug."""
    if plug is None:
        plug = attr.api.plug
    attribute = plug.attribute()
    apiType = attribute.apiType()

    if apiType == om2.MFn.kTypedAttribute:
        attrType = om2.MFnTypedAttribute(attribute).attrType()
        if attrType == om2.MFnData.kString:
            return plug.asString() if value else str
        if attrType == om2.MFnData.kInvalid:
            raise exceptions.InvalidAttributeTypeError(attr.node, attr.attr)

        # If the type is kAny then it may be connected to another value
        if attrType == om2.MFnData.kAny and plug.isDestination:
            return _getPlugData(attr, plug.source(), value=value)

    if apiType == om2.MFn.kNumericAttribute:
        numericType = om2.MFnNumericAttribute(attribute).numericType()
        if numericType == om2.MFnNumericData.kBoolean:
            return plug.asBool() if value else bool
        if numericType in (om2.MFnNumericData.kInt, om2.MFnNumericData.kInt64, om2.MFnNumericData.kLong):
            return plug.asInt() if value else int
        if numericType == om2.MFnNumericData.kFloat:
            return plug.asFloat() if value else float
        if numericType == om2.MFnNumericData.kDouble:
            return plug.asDouble() if value else float
        if numericType == om2.MFnNumericData.kShort:
            return plug.asShort() if value else int

    if apiType in (om2.MFn.kFloatAngleAttribute, om2.MFn.kDoubleAngleAttribute):
        if not value:
            return None  # TODO
        return plug.asMAngle().asDegrees()  # Equivalent to `math.degrees(plug.asDouble())`

    if apiType in (om2.MFn.kFloatLinearAttribute, om2.MFn.kDoubleLinearAttribute):
        if not value:
            return None  # TODO
        return plug.asMDistance().asCentimeters()  # Equivalent to `plug.asDouble()`

    if apiType == om2.MFn.kEnumAttribute:
        if value:
            return plug.asInt()
        return 'enum'  # Match the result from `getAttr`

    if apiType == om2.MFn.kAttribute2Float:
        return tuple(plug.child(i).asFloat() for i in range(2)) if value else (float, float)
    if apiType == om2.MFn.kAttribute2Double:
        return tuple(plug.child(i).asDouble() for i in range(2)) if value else (float, float)
    if apiType == om2.MFn.kAttribute2Int:
        return tuple(plug.child(i).asInt() for i in range(2)) if value else (int, int)
    if apiType == om2.MFn.kAttribute2Short:
        return tuple(plug.child(i).asShort() for i in range(2)) if value else (int, int)
    if apiType == om2.MFn.kAttribute3Float:
        return tuple(plug.child(i).asFloat() for i in range(3)) if value else (float, float, float)
    if apiType == om2.MFn.kAttribute3Double:
        return tuple(plug.child(i).asDouble() for i in range(3)) if value else (float, float, float)
    if apiType == om2.MFn.kAttribute3Int:
        return tuple(plug.child(i).asInt() for i in range(3)) if value else (int, int, int)
    if apiType == om2.MFn.kAttribute3Short:
        return tuple(plug.child(i).asShort() for i in range(3)) if value else (int, int, int)
    if apiType == om2.MFn.kAttribute4Double:
        return tuple(plug.child(i).asDouble() for i in range(4)) if value else (float, float, float, float)

    if value and apiType == om2.MFn.kMessageAttribute:
        raise RuntimeError('Message attributes have no data values')  # Match the mc.getAttr error
    return None


def _setPlugValue(plug, value):
    # type: (om2.MPlug, Any) -> None
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


class AttributeChildren(types.MappedLazyList):
    """Access the child attributes.

    TODO: Short attribute names
    """

    def __init__(self, node, plug):
        # type: (Node, om2.MPlug) -> None
        keyType = str  # type: Type[Any]
        if plug.isArray:
            plugs = map(plug.elementByLogicalIndex, plug.getExistingArrayAttributeIndices())
            keyType = int

        elif plug.isCompound:
            plugs = map(plug.child, range(plug.numChildren()))

        else:
            plugs = map(plug.child, ())  # Keep the type hints happy
        super(AttributeChildren, self).__init__((Attribute(node, plug) for plug in plugs), keyType=keyType)

    def generateKey(self, value):
        # type: (Any) -> Any
        if isinstance(value, Attribute):
            plug = value.api.plug
            if plug.isChild:
                return value.name.rsplit('.', 1)[-1]
            if plug.isCompound or plug.isElement:
                return value.api.plug.logicalIndex()
        raise NotImplementedError(type(value).__name__)


class NodeAttributes(dict):
    """Lazy dictionary storing a cache of all the Attribute values.
    The full list of attributes is not populated until it is requested.
    There is no validation on checking if new attributes already exist.
    """

    __slots__ = ['node', '_loaded']

    def __init__(self, node):
        # type: (Node) -> None
        self.node = node
        self._loaded = False
        super(NodeAttributes, self).__init__()

    def __repr__(self):
        # type: () -> str
        self._ensureAttrs()
        return super(NodeAttributes, self).__repr__()

    def __getitem__(self, attr):
        # type: (str) -> Attribute
        self._ensureAttr(attr)
        return super(NodeAttributes, self).__getitem__(attr)

    def __setitem__(self, attr, value):
        # type: (str, Attribute) -> None
        self[attr].value = value

    def __iter__(self):
        # type: () -> Iterator[str]
        self._ensureAttrs()
        return super(NodeAttributes, self).__iter__()

    def __len__(self):
        # type: () -> int
        self._ensureAttrs()
        return super(NodeAttributes, self).__len__()

    def __contains__(self, value):
        # type: (Any) -> bool
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
        # type: () -> KeysView
        self._ensureAttrs()
        return super(NodeAttributes, self).keys()

    def values(self):
        # type: () -> ValuesView
        self._ensureAttrs()
        return super(NodeAttributes, self).values()

    def items(self):
        # type: () -> ItemsView
        self._ensureAttrs()
        return super(NodeAttributes, self).items()

    def get(self, attr, default=None):
        # type: (str, Any) -> Any
        """Return an attribute if it exists."""
        if attr in self:
            return self[attr]
        return default

    def _ensureAttr(self, attr, reload=False):
        # type: (Union[om2.MPlug, str], bool) -> bool
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
        # type: (bool) -> None
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

    def create(self, longName, type=None, **kwargs):
        # type: (str, Optional[str], **Any) -> Attribute
        """Create the attribute."""
        if type is not None:
            if type is bool:
                kwargs['attributeType'] = 'bool'
            elif type is int:
                kwargs['attributeType'] = 'long'
            elif type is str:
                kwargs['dataType'] = 'string'
            elif type is float:
                kwargs['attributeType'] = 'double'

        utils.logger.info('Adding attribute "%s.%s" with arguments %s', self.node, longName, kwargs)
        mc.addAttr(self.node, longName=longName, **kwargs)
        return self.__getitem__(longName)


def _getPlugFromDepNode(depNode, attr):
    # type: (om2.MFnDependencyNode, str) -> Optional[om2.MPlug]
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
    A connection is made by using the `>>` operator between two attrs,
    and `//` is used to disconnect.

    TODO:
        Add create/ensure methods if possible
    """

    __slots__ = ['node', 'attr', 'api', '_compoundChildren']

    class ApiData(object):
        """Hold the OpenMaya API objects."""

        __slots__ = ['_plug', '_attribute', '_numericAttribute']

        def __init__(self, plug):
            # type: (om2.MPlug) -> None
            """Store the plug.

            If the plug is networked, then convert to non networked, as
            otherwise all sorts of crashes and instability can happen
            by holding the plug in memory.
            """
            self._plug = utils.unnetworkPlug(plug)
            self._attribute = None
            self._numericAttribute = None

        @classmethod
        def fromNode(cls, node, attr):
            # type: (Node, str) -> Attribute.ApiData
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
            # type: (str) -> Attribute.ApiData
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
            # type: () -> om2.MPlug
            """Get the `MPlug`.

            Notable methods:
                `name()`
                `partialName(useFullAttributePath=True)`
            """
            return self._plug

        @property
        def plugs(self):
            # type: () -> List[om2.MPlug]
            """Get all the `MPlug` objects associated with this attribute.
            Only array attributes contain multiple plugs.
            """
            plug = self.plug
            result = [plug]
            if plug.isArray:
                result.extend(map(plug.elementByLogicalIndex, plug.getExistingArrayAttributeIndices()))
            return result

        @property
        def attribute(self):
            # type: () -> om2.MFnAttribute
            """Get the `MFnAttribute`.

            Notable methods:
                `name`
                `shortName`
            """
            if self._attribute is None:
                self._attribute = om2.MFnAttribute(self.plug.attribute())
            return self._attribute

        @property
        def numericAttribute(self):
            # type: () -> om2.MFnNumericAttribute
            """Get the `MFnNumericAttribute`.

            Notable methods:
                `unitType`
                `getMin`
                `hasMin`
                `getMax`
                `hasMax`
                `getSoftMin`
                `hasSoftMin`
                `getSoftMax`
                `hasSoftMax`
            """
            if self._numericAttribute is None:
                attribute = self.plug.attribute()
                if attribute.apiType() == om2.MFn.kNumericAttribute:
                    self._numericAttribute = om2.MFnNumericAttribute(attribute)
                else:
                    self._numericAttribute = -1

            if self._numericAttribute == -1:
                return None
            return self._numericAttribute

    def __init__(self, node, attr):
        # type: (StrLike, Union[str, om2.MPlug]) -> None
        """Create the attribute proxy.

        Parameters:
            node (Node): Instance of the current node.
            attr (str|MPlug): Attribute of the node.
                If using a networked plug that is attached to an
                attribute that no longer exists, then Maya will crash.
        """
        self.node = Node(node)

        if isinstance(attr, om2.MPlug):
            self.api = Attribute.ApiData(attr)
            self.attr = self.api.plug.partialName(useLongNames=True, includeInstancedIndices=True)
        else:
            self.attr = attr
            self.api = Attribute.ApiData.fromNode(self.node, attr)

        self._compoundChildren = None  # type: Optional[Dict[str, Attribute]]

    @classmethod
    def ls(self, attr):
        # type: (str) -> List[Attribute]
        """Search the scene for an attribute."""
        result = mc.ls('*.' + attr)
        split = (item.split('.', 1) for item in result)
        return [Attribute(Node(node), attr) for node, attr in split]

    def __bool__(self):
        # type: () -> bool
        return self.exists
    __nonzero__ = __bool__

    def __eq__(self, value):
        # type: (Any) -> bool
        plug = self.api.plug
        if plug is None:
            return value == self.attr
        if isinstance(value, Attribute):
            return plug == value.api.plug
        if isinstance(value, Connection):
            return plug == value._dstPlug

        value = str(value)
        if not value:
            return False

        if '.' in value:
            # Check full attribute path (`|n1|n2.t.tx`)
            # If node matches then continue past here
            if value[0] == '|':
                node, value = value.split('.', 1)
                if self.node != node:
                    return False

            # Check partial attribute path (`|n1|n2.t.tx`)
            # If node matches then continue past here
            elif '|' in value:
                node, value = value.split('.', 1)
                if not self.node.endswith(node):
                    return False

            # Check node short name (`n2.t.tx`)
            else:
                node, possibleValue = value.split('.', 1)
                if self.node.endswith(node):
                    value = possibleValue

        useFullAttributePath = '.' in value
        partialName = plug.partialName(useFullAttributePath=useFullAttributePath)
        longName = plug.partialName(useFullAttributePath=useFullAttributePath, useLongNames=True)

        # Check plug element index if not included in the name
        if plug.isElement and '[' not in partialName:
            isElement = re.match(r'(.*?)\[(\d)\]', value)
            if not isElement:
                return False
            value, element = isElement.groups()
            if int(element) != plug.logicalIndex():
                return False

        return value in (partialName, longName) or partialName.endswith(value) or longName.endswith(value)

    def __float__(self):
        # type: () -> float
        return float(self.value)

    def __int__(self):
        # type: () -> int
        return int(self.value)

    def __rshift__(self, connection):
        # type: (Union[str, Attribute, om2.MPlug]) -> bool
        """Create an outgoing connection.

        >>> Attribute('node.attr') >> 'othernode.attr'
        """
        return self.connect(connection)

    def __rrshift__(self, connection):
        # type: (Union[str, Attribute, om2.MPlug]) -> bool
        """Create an incoming connection.

        >>> 'othernode.attr' >> Attribute('node.attr')
        """
        return self.connect(connection, reverse=True)

    def __floordiv__(self, connection):
        # type: (Union[str, Attribute, om2.MPlug]) -> bool
        """Break an outgoing connection.

        >>> Attribute('node.attr') // 'othernode.attr'
        """
        return self.disconnect(connection)

    def __rfloordiv__(self, connection):
        # type: (Union[str, Attribute, om2.MPlug]) -> bool
        """Break an incoming connection.

        >>> 'othernode.attr' // Attribute('node.attr')
        """
        return self.disconnect(connection, reverse=True)

    def split(self, *args, **kwargs):
        # type: (*Any, **Any) -> List[str]
        """Add the ability to split for backwards compatibility."""
        return self.name.split(*args, **kwargs)

    @property
    def exists(self):
        # type: () -> bool
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
        if not self.node.exists:
            return False

        # Walk through the plugs until the top one
        plug = self.api.plug
        checkElementIn = [] # type: List[Tuple[om2.MPlug, om2.MPlug]]
        while True:
            if plug.isNull:
                return False

            # Array child (eg. uvSet[0])
            if plug.isElement:
                parent = plug.array()
                checkElementIn.append((plug, parent))
                plug = parent

            # Compound child (eg. uvSet[0].uvSetName)
            elif plug.isChild:
                plug = plug.parent()

            else:
                break

        # Check
        if not self.node.api.dependencyNode.hasAttribute(plug.partialName()):
            return False

        # This needs to be done after, because if the attribute is deleted
        # then `getExistingArrayAttributeIndices` will crash Maya
        for child, parent in checkElementIn:
            if child.logicalIndex() not in parent.getExistingArrayAttributeIndices():
                return False
        return True

    @property
    def type(self):
        # type: () -> Any
        """Get the attribute type.

        Raises:
            AttributeNotFoundError
            InvalidAttributeTypeError

        Returns:
            Python type for standard attributes.
            Tuple of types if a compound attribute.
            List of a single type if an array attribute.
            String if unsupported (eg. "enum").
        """
        if not self.api.plug.isNull:
            result = _getPlugData(self, value=False)
            if result is not None:
                return result

        try:
            attrType = mc.getAttr(self, type=True)
        except ValueError as e:
            if 'No object matches name' in str(e):
                raise exceptions.AttributeNotFoundError(self.node, self.attr)
        return ATTR_TYPES.get(attrType, attrType)

    @property
    def name(self):
        # type: () -> str
        """Get the full node and attribute name for Maya to use."""
        return '{}.{}'.format(self.node, self.attr)

    @property
    def value(self):
        # type: () -> Any
        """Get an attribute value.

        Raises:
            InvalidAttributeTypeError
        """
        if not self.api.plug.isNull:
            result = _getPlugData(self, value=True)
            if result is not None:
                return result
        return mc.getAttr(self)

    @value.setter
    def value(self, value):
        # type: (Any) -> None
        """Set a new attribute value.

        Raises:
            NodeDeletedError
            AttributeLockedError
            AttributeConnectedError
            AttributeTooLowError
            AttributeTooHighError
        """
        utils.logger.info('Setting %s value: %r', self, value)
        utils.raiseIfNodeNotFound(self.node)
        plug = self.api.plug
        if not plug.isNull:
            if plug.isLocked:
                raise exceptions.AttributeLockedError(self.node, self.attr)

            if plug.isConnected:
                for otherPlug in plug.connectedTo(True, False):
                    if not otherPlug.node().hasFn(om2.MFn.kAnimCurve):
                        raise exceptions.AttributeConnectedError(self.node, self.attr)

        if isinstance(value, (str, unicode, types.StrMixin)):
            mc.setAttr(self, value, type='string')
        elif isinstance(value, (tuple, list)):
            mc.setAttr(self, *value)
        else:
            if isinstance(value, (float, int)):
                minValue = self.min
                if minValue is not None and value < minValue:
                    raise exceptions.AttributeTooLowError(self.node, self.attr, minValue)
                maxValue = self.max
                if maxValue is not None and value > maxValue:
                    raise exceptions.AttributeTooHighError(self.node, self.attr, maxValue)
            mc.setAttr(self, value)

    @property
    def locked(self):
        # type: () -> bool
        """Get the attribute locked state."""
        if not self.api.plug.isNull:
            return self.api.plug.isLocked
        return mc.getAttr(self, lock=True)

    @locked.setter
    def locked(self, value):
        # type: (bool) -> None
        """Set the attribute locked state.

        Raises:
            NodeDeletedError
        """
        utils.logger.info('Setting %s locked state: %r', self, value)
        utils.raiseIfNodeNotFound(self.node)
        mc.setAttr(self, lock=value)

    def lock(self):
        # type: () -> None
        """Lock the attribute."""
        self.locked = True

    def unlock(self):
        # type: () -> None
        """Unlock the attribute."""
        self.locked = False

    @property
    def keyable(self):
        # type: () -> bool
        """Get the node keyable state."""
        if not self.api.plug.isNull:
            return self.api.plug.isKeyable
        return mc.getAttr(self, keyable=True)

    @keyable.setter
    def keyable(self, value):
        # type: (bool) -> None
        """Set the node keyable state.

        Raises:
            NodeDeletedError
        """
        utils.logger.info('Setting %s keyable state: %s', self, value)
        utils.raiseIfNodeNotFound(self.node)
        mc.setAttr(self, keyable=value)

    def connect(self, target, reverse=False):
        # type: (Union[str, Attribute, om2.MPlug], bool) -> bool
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
        # type: (Union[str, Attribute, om2.MPlug], bool) -> bool
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
        # type: () -> AttributeConnectionProxy
        """Get the attribute connections as plugs."""
        return AttributeConnectionProxy(self)

    def create(self, type=None, **kwargs):
        # type: (Optional[str], **Any) -> None
        """Create the attribute."""
        try:
            if type is None:
                type = self.type
        except exceptions.AttributeNotFoundError:
            pass

        if type is not None:
            if type is bool:
                kwargs['attributeType'] = 'bool'
            elif type is int:
                kwargs['attributeType'] = 'long'
            elif type is str:
                kwargs['dataType'] = 'string'
            elif type is float:
                kwargs['attributeType'] = 'double'

        utils.logger.info('Adding attribute %s with arguments %s', self, kwargs)
        mc.addAttr(self.node, longName=self.attr, **kwargs)

    def delete(self):
        # type: () -> None
        """Delete the attribute.

        Raises:
            NodeDeletedError
            RuntimeError: Cannot delete static attribute 'pCube1.translate' from node 'pCube1'.
            RuntimeError: Cannot delete child 'pCube1.translateX' of compound attribute 'translate'.
        """
        utils.logger.info('Deleting attribute: %s', self)
        utils.raiseIfNodeNotFound(self.node)
        if self.api.plug.isElement:
            mc.removeMultiInstance(self, b=True)
        else:
            mc.deleteAttr(self)

    @property
    def keyframes(self):
        # type: () -> AttributeKeyframes
        """Get the keyframe dict."""
        return AttributeKeyframes(self)

    @keyframes.deleter
    def keyframes(self):
        # type: () -> None
        """Delete all keyframes on the current attribute."""
        AttributeKeyframes(self).delete()

    @property
    def children(self):
        # type: () -> AttributeChildren
        """Get all attribute children.

        Raises:
            AttributeNotFoundError
        """
        if not self.exists:
            raise exceptions.AttributeNotFoundError(self.node, self.attr)
        return AttributeChildren(self.node, self.api.plug)

    def __len__(self):
        # type: () -> int
        """Get the number of child attributes."""
        plug = self.api.plug
        if plug.isArray:
            return plug.numElements()
        if plug.isCompound:
            return plug.numChildren()
        return 0

    @property
    def uvLinks(self):
        # type: () -> List[Node]
        """Get the nodes linked to this UV set attribute.

        TODO:
            Tests
        """
        links = mc.uvLink(query=True, uvSet=self.name)
        return [Node(link) for link in links]

    @property
    def min(self):
        # type: () -> Optional[float]
        """Get the minimum value if set."""
        nattr = self.api.numericAttribute
        if nattr is not None and nattr.hasMin():
            return nattr.getMin()
        return None

    @property
    def max(self):
        # type: () -> Optional[float]
        """Get the maximum value if set."""
        nattr = self.api.numericAttribute
        if nattr is not None and nattr.hasMax():
            return nattr.getMax()
        return None

    @property
    def softMin(self):
        # type: () -> Optional[float]
        """Get the soft minimum value if set."""
        nattr = self.api.numericAttribute
        if nattr is not None and nattr.hasSoftMin():
            return nattr.getSoftMin()
        return None

    @property
    def softMax(self):
        # type: () -> Optional[float]
        """Get the soft maximum value if set."""
        nattr = self.api.numericAttribute
        if nattr is not None and nattr.hasSoftMax():
            return nattr.getSoftMax()
        return None


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .connection import AttributeConnectionProxy, Connection
from .keyframes import AttributeKeyframes
from .node import Node
