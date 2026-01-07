import re

import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import maya.cmds as mc  # type: ignore

from .. import exceptions, types, utils
from ..type_hints import TYPE_CHECKING, Union, cast, overload

if TYPE_CHECKING:
    from typing import Any, Callable, Iterator, Type
    from typing import KeysView, ValuesView, ItemsView
    from ..type_hints import StrLike


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
    'matrix': (int,) * 16
}

API_TUPLE_TYPES = {
    om2.MFn.kAttribute2Float: (float, float),
    om2.MFn.kAttribute2Double: (float, float),
    om2.MFn.kAttribute2Int: (int, int),
    om2.MFn.kAttribute2Short: (int, int),
    om2.MFn.kAttribute3Float: (float, float, float),
    om2.MFn.kAttribute3Double: (float, float, float),
    om2.MFn.kAttribute3Int: (int, int, int),
    om2.MFn.kAttribute3Short: (int, int, int),
    om2.MFn.kAttribute4Double: (float, float, float, float),
}


def _getArrayIndices(plug):
    # type: (om2.MPlug) -> tuple[int, ...]
    """Get the indices of an array plug.

    The majority of plugs support `getExistingArrayAttributeIndices`,
    but "controlPoints" for example does not, so this is required for now.
    """
    numElements = plug.numElements()
    indices = plug.getExistingArrayAttributeIndices()
    if len(indices) == numElements:
        return tuple(indices)
    return tuple(range(numElements))


def _getPlugData(attr, plug=None, value=True):
    # type: (Attribute, om2.MPlug | None, bool) -> Any
    """Get the type or value of a plug.

    Raises:
        RuntimeError: (kFailure): Unexpected Internal Failure
            One example is the "edge" attribute.
    """
    if plug is None:
        plug = attr.api.plug

    isArray = plug.isArray
    isCompound = plug.isCompound

    # Handle parent plugs first if querying values
    if isArray:  # Example: pCubeShape1.uvSet
        if value:
            return list(_getPlugData(attr, child, value=value)
                        for child in map(plug.elementByLogicalIndex, _getArrayIndices(plug)))
    elif isCompound:  # Example: pCube1.translate
        return tuple(_getPlugData(attr, child, value=value)
                     for child in map(plug.child, range(plug.numChildren())))

    attribute = plug.attribute()
    apiType = attribute.apiType()

    # Simple tuple types such as "double2" mapping to (float, float)
    # These should be guaranteed to be arrays at this point
    if apiType in API_TUPLE_TYPES:  # Example: pCubeShape1.uvSet[0].uvSetPoints
        assert isArray
        return [API_TUPLE_TYPES[apiType]]

    # Get types of array containing compound attributes
    if apiType == om2.MFn.kCompoundAttribute:  # Example: pCubeShape1.uvSet
        assert isArray
        return [_getPlugData(attr, plug.elementByLogicalIndex(0), value=value)]

    if apiType == om2.MFn.kTypedAttribute:
        attrType = om2.MFnTypedAttribute(attribute).attrType()
        if attrType == om2.MFnData.kString:
            return plug.asString() if value else str

        if attrType == om2.MFnData.kMatrix:
            if not value:
                return ATTR_TYPES['matrix']
            return types.Matrix4D(om2.MFnMatrixData(plug.asMObject()).matrix())

        if attrType == om2.MFnData.kIntArray:
            if value:
                intArrayData = om2.MFnIntArrayData(attribute)
                return list(intArrayData)
            return [int]

        if attrType == om2.MFnData.kMesh:
            if value:
                raise exceptions.AttributeTypeError(attr.node, attr.attr)
            return 'mesh'

        if attrType == om2.MFnData.kInvalid:
            raise exceptions.InvalidAttributeTypeError(attr.node, attr.attr)

        # If the type is kAny then it may be connected to another value
        if attrType == om2.MFnData.kAny:

            # Example: initialShadingGroup.surfaceShader
            if plug.isDestination:
                return _getPlugData(attr, plug.source(), value=value)

            # Example: pCube1.uvSet[0].uvSetTweakLocation
            return None

        # Component lists are rarer and more complicated, so support is very incomplete
        # Example: pCube1.instObjGroups...objectGrpCompList
        if attrType == om2.MFnData.kComponentList:
            plugObj = plug.asMDataHandle().data()  # Note that `plug.asMObject()` raises on null
            if plugObj.isNull():
                return []
            componentListData = om2.MFnComponentListData(plugObj)  # This still works if plugObj.isNull
            for componentGroup in map(componentListData.get, range(componentListData.length())):
                componentType = componentGroup.apiType()
                if componentType == om2.MFn.kMeshPolygonComponent:
                    singleIndex = om2.MFnSingleIndexedComponent(componentGroup)
                    return list(singleIndex.getElements())
                raise NotImplementedError(componentGroup.apiTypeStr)
            return []

    if apiType == om2.MFn.kNumericAttribute:
        numericType = om2.MFnNumericAttribute(attribute).numericType()

        if numericType == om2.MFnNumericData.kBoolean:
            return [bool] if isArray else plug.asBool() if value else bool
        if numericType in (om2.MFnNumericData.kInt, om2.MFnNumericData.kInt64, om2.MFnNumericData.kLong):
            return [int] if isArray else plug.asInt() if value else int
        if numericType == om2.MFnNumericData.kFloat:
            return [float] if isArray else plug.asFloat() if value else float
        if numericType == om2.MFnNumericData.kDouble:
            return [float] if isArray else plug.asDouble() if value else float
        if numericType == om2.MFnNumericData.kShort:
            return [int] if isArray else plug.asShort() if value else int

    if apiType in (om2.MFn.kFloatAngleAttribute, om2.MFn.kDoubleAngleAttribute):
        if not value:
            return float
        return plug.asMAngle().asDegrees()  # Equivalent to `math.degrees(plug.asDouble())`

    if apiType in (om2.MFn.kFloatLinearAttribute, om2.MFn.kDoubleLinearAttribute):
        if not value:
            return float
        return plug.asMDistance().asCentimeters()  # Equivalent to `plug.asDouble()`

    if apiType == om2.MFn.kEnumAttribute:
        if value:
            return plug.asInt()
        return int

    if apiType == om2.MFn.kTimeAttribute:
        if value:
            return plug.asMTime().value
        return float

    if apiType == om2.MFn.kMatrixAttribute:
        if value:
            martixData = om2.MFnMatrixData(plug.asMObject())
            return types.Matrix4D(martixData.matrix())
        return ATTR_TYPES['matrix']

    if value and apiType == om2.MFn.kMessageAttribute:  # Message attributes have no data values
        raise exceptions.MessageAttributeTypeError(attr.node, attr.attr)

    if apiType == om2.MFn.kGenericAttribute:
        return None

    return mc.getAttr(plug.name(), type=not value)


def _setPlugValue(plug, value):
    # type: (om2.MPlug, Any) -> None
    """Recursively set the plug value.
    This assumes the correct data types are given.

    Warning: Does not work with undo.
    """
    if isinstance(value, (str, unicode, types.StrMixin)):
        plug.setString(str(value))
    elif isinstance(value, float):
        plug.setDouble(value)
    elif isinstance(value, int):
        plug.setInt(value)
    elif isinstance(value, bool):
        plug.setBool(value)
    elif isinstance(value, (list, tuple)):
        for i, val in enumerate(value):
            _setPlugValue(plug.child(i), val)
    else:
        raise NotImplementedError(type(value))


class AttributeChildren(types.MappedLazyList['Attribute', om2.MPlug, Union[str, int]]):
    """Access the child attributes."""

    __slots__ = ['_node', '_plug']

    @property
    def ItemType(self):  # type: () -> Type[Attribute]
        """Return the object this list contains."""
        return Attribute

    @property
    def IndexType(self):  # type: () -> Type[str | int]
        """Get the correct index type to use.
        For arrays use integers, otherwise use the attribute names.
        """
        if self.plug.isArray:
            return int
        return str

    def _getIndex(self, value):
        # type: (Any) -> str | int
        if self.plug.isArray:
            return int(value)
        return str(value)

    def __init__(self, node, plug):
        # type: (Node, om2.MPlug) -> None
        super(AttributeChildren, self).__init__()
        self._node = node
        self._plug = plug

    @property
    def node(self):
        # type: () -> Node
        """Get the node."""
        return self._node

    @property
    def plug(self):
        """Get the parent plug."""
        return self._plug

    def __eq__(self, other):
        # type: (Any) -> bool
        if isinstance(other, AttributeChildren):
            return self.node == other.node and self.plug == other.plug
        return super(AttributeChildren, self).__eq__(other)

    def __contains__(self, item):
        # type: (StrLike) -> bool
        """If a particular attribute is a child."""
        if isinstance(item, Attribute):
            return item.api.plug in self._getApiObjects()
        if isinstance(item, om2.MPlug):
            return item in self._getApiObjects()
        return super(AttributeChildren, self).__contains__(item)

    def _loadApiObjects(self):
        # type: () -> list[om2.MPlug]
        """Load all API objects."""
        plug = self.plug
        if plug.isArray:
            return [plug.elementByLogicalIndex(i) for i in _getArrayIndices(plug)]
        if plug.isCompound:
            return [plug.child(i) for i in range(plug.numChildren())]
        return []

    def _loadListItem(self, apiObject):
        # type: (om2.MPlug) -> Attribute
        """Load the Attribute from the plug."""
        return Attribute(self.node, apiObject)

    def _generateKeys(self, apiObject, moduleObject):
        # type: (om2.MPlug, Attribute) -> Iterator[str | int]
        """Generate possible keys to use to get the children."""
        if apiObject.isChild:
            yield apiObject.partialName(useLongNames=True, includeInstancedIndices=True).split('.')[-1]
            yield apiObject.partialName(useLongNames=False, includeInstancedIndices=True).split('.')[-1]

        elif apiObject.isCompound or apiObject.isElement:
            yield apiObject.logicalIndex()


class NodeAttributes(types.MappedLazyList['Attribute', om2.MPlug, str]):
    """Access the attributes on a node."""

    __slots__ = ['_node']

    @property
    def ItemType(self):  # type: () -> Type[Attribute]
        """Return the object this list contains."""
        return Attribute

    def __init__(self, node):
        # type: (Node) -> None
        super(NodeAttributes, self).__init__()
        self._node = node

    @property
    def node(self):
        # type: () -> Node
        """Get the node."""
        return self._node

    def __eq__(self, other):
        # type: (Any) -> bool
        if isinstance(other, NodeAttributes):
            return self.node == other.node
        return super(NodeAttributes, self).__eq__(other)

    def __len__(self):
        # type: () -> int
        """Get the number of attributes.

        Note that `self.node.api.dependencyNode.attributeCount()` is not
        accurate for this as it includes the child plugs we ignore. This
        function is left in place however as a reminder.
        """
        return super(NodeAttributes, self).__len__()

    def __contains__(self, item):
        # type: (Any) -> bool
        """If a particular attribute exists in a node."""
        item = str(item)
        return self.node.api.dependencyNode.hasAttribute(str(item)) or item in self._mappedKeys

    def __getitem__(self, index):
        # type: (str) -> Attribute
        try:
            return super(NodeAttributes, self).__getitem__(index)
        except KeyError as e:
            raise exceptions.AttributeNotFoundError(self.node, e.message)

    def get(self, attr, default=None):
        # type: (str, Any) -> Any
        """Return an attribute if it exists."""
        if attr in self:
            return self[attr]
        return default

    def __setitem__(self, attr, value):
        # type: (str, Any) -> None
        """Set an attribute value."""
        self.__getitem__(attr).value = value

    def _loadApiObjects(self):
        # type: () -> list[om2.MPlug]
        """Load all API objects."""
        depNode = self.node.api.dependencyNode
        apiObjects = (depNode.attribute(i) for i in range(depNode.attributeCount()))
        plugs = (depNode.findPlug(apiObject, False) for apiObject in apiObjects)

        # Filter out the child plugs with a logical index of -1
        result = []
        for plug in plugs:
            if plug.isChild:
                parent = plug.parent()
                while parent.isChild:
                    parent = parent.parent()
                if parent.isElement:
                    continue
            result.append(plug)
        return result

    def _loadListItem(self, plug):
        # type: (om2.MPlug) -> Attribute
        """Load the Attribute from the plug."""
        return Attribute(self.node, plug)

    def _generateKeys(self, plug, moduleObject):
        # type: (om2.MPlug, Attribute) -> Iterator[str]
        """Generate the key to access the attribute.

        Skip any attribute with multiple path parts at this stage,
        eg. pCubeShape1.uvSet[-1].uvSetName / lambert1.lightDataArray.lightDirection
        """
        plug = moduleObject.api.plug
        name = plug.partialName(useLongNames=False)
        if '.'  not in name:
            yield name
            yield plug.partialName(useLongNames=True)

    def create(self, longName, type=None, **kwargs):
        # type: (str, str | None, **Any) -> Attribute
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
        self.refresh()
        return self.__getitem__(longName)

    @property
    def keyable(self):
        # type: () -> list[Attribute]
        """Get all keyable attributes."""
        return [attr for attr in self.values() if attr.keyable]


def _getPlugFromDepNode(depNode, attr):
    # type: (om2.MFnDependencyNode, str) -> om2.MPlug | None
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
            self._attribute = None  # type: om2.MFnAttribute | None
            self._numericAttribute = None  # type: om2.MFnNumericAttribute | utils.NotSet | None

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

        @plug.setter
        def plug(self, plug):
            # type: (om2.MPlug) -> None
            """Update the plug."""
            if plug is not self._plug:
                self._plug = plug
                self._attribute = None
                self._numericAttribute = None

        @property
        def plugs(self):
            # type: () -> list[om2.MPlug]
            """Get all the `MPlug` objects associated with this attribute.
            Only array attributes contain multiple plugs.
            """
            plug = self.plug
            result = [plug]
            if plug.isArray:
                result.extend(map(plug.elementByLogicalIndex, _getArrayIndices(plug)))
            return result

        @property
        def attribute(self):
            # type: () -> om2.MFnAttribute
            """Get the `MFnAttribute`.

            Notable methods:
                `name`
                `shortName`
                `writable`
                `readable`
            """
            if self._attribute is None:
                self._attribute = om2.MFnAttribute(self.plug.attribute())
            return self._attribute

        @property
        def numericAttribute(self):
            # type: () -> om2.MFnNumericAttribute | None
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
            nAttr = self._numericAttribute
            if nAttr is None:
                attribute = self.plug.attribute()
                if attribute.apiType() == om2.MFn.kNumericAttribute:
                    nAttr = self._numericAttribute = om2.MFnNumericAttribute(attribute)
                else:
                    nAttr = self._numericAttribute = utils.NOT_SET

            if isinstance(nAttr, utils.NotSet):
                return None
            return nAttr

    def __init__(self, node, attr):
        # type: (StrLike, str | om2.MPlug) -> None
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

        self._compoundChildren = None  # type: dict[str, Attribute] | None

    @classmethod
    def ls(self, attr):
        # type: (str) -> list[Attribute]
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
        # type: (ConnectionType) -> bool
        """Create an outgoing connection.

        >>> Attribute('node.attr') >> 'othernode.attr'
        """
        return self.connect(connection)

    def __rrshift__(self, connection):
        # type: (ConnectionType) -> bool
        """Create an incoming connection.

        >>> 'othernode.attr' >> Attribute('node.attr')
        """
        return self.connect(connection, reverse=True)

    def __floordiv__(self, connection):
        # type: (ConnectionType) -> bool
        """Break an outgoing connection.

        >>> Attribute('node.attr') // 'othernode.attr'
        """
        return self.disconnect(connection)

    def __rfloordiv__(self, connection):
        # type: (ConnectionType) -> bool
        """Break an incoming connection.

        >>> 'othernode.attr' // Attribute('node.attr')
        """
        return self.disconnect(connection, reverse=True)

    def split(self, *args, **kwargs):
        # type: (*Any, **Any) -> list[str]
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
        checkElementIn = [] # type: list[tuple[om2.MPlug, om2.MPlug]]
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

        # Check the attribute actually exist
        if not self.node.api.dependencyNode.hasAttribute(plug.partialName()):
            return False

        # This needs to be done last, because if the attribute is deleted
        # then `getExistingArrayAttributeIndices` will crash Maya
        for child, parent in checkElementIn:
            if child.logicalIndex() not in _getArrayIndices(parent):
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
            String name (e.g. "message") or None if unsupported.
        """
        self.api.plug = utils.refreshPlug(self.node.api.object, self.api.plug)
        if not self.api.plug.isNull:
            result = _getPlugData(self, value=False)
            if result is not None:
                return result

        try:
            attrType = mc.getAttr(self, type=True)
        except ValueError as e:
            if 'No object matches name' in str(e):
                raise exceptions.AttributeNotFoundError(self.node, self.attr)
            if 'The value for the attribute could not be retrieved.' in str(e):
                raise exceptions.InvalidAttributeTypeError(self.node, self.attr)
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
            AttributeMessageTypeError
        """
        self.api.plug = utils.refreshPlug(self.node.api.object, self.api.plug)
        if not self.api.plug.isNull:
            try:
                result = _getPlugData(self, value=True)
            except RuntimeError as e:
                if '(kFailure): Unexpected Internal Failure' in str(e):
                    raise exceptions.InvalidAttributeTypeError(self.node, self.attr)
                raise
            if result is not None:
                return result
        return mc.getAttr(self)

    @value.setter
    def value(self, value):
        # type: (Any) -> None
        """Set a new attribute value.

        Raises:
            NodeDeletedError
            AttributeDeletedError
            AttributeLockedError
            AttributeConnectedError
            AttributeTooLowError
            AttributeTooHighError
        """
        utils.logger.info('Setting %s value: %r', self, value)
        utils.raiseIfAttrNotFound(self)
        plug = self.api.plug
        if not plug.isNull:
            if plug.isLocked:
                raise exceptions.AttributeLockedError(self.node, self.attr)

            if plug.isConnected:
                for otherPlug in plug.connectedTo(True, False):
                    if not otherPlug.node().hasFn(om2.MFn.kAnimCurve):
                        raise exceptions.AttributeConnectedError(self.node, self.attr)

            if not self.api.attribute.writable:
                raise exceptions.AttributeNotWritableError(self.node, self.attr)

        # Stop here if no value is given
        if value is None:
            return

        # Handle array/compound attributes
        if self.api.plug.isArray or self.api.plug.isCompound:
            children = self.children
            assert len(children) == len(value)
            for child, val in zip(children, value):
                if val is not None:
                    child.value = val
            return

        try:
            mayaType = mc.getAttr(self, type=True)

        except RuntimeError as e:
            if 'No object matches name' in str(e):
                raise exceptions.AttributeNotFoundError(self.node, self.attr)

        # Special case for amtrix types, to handle the array attributes
        if mayaType == 'matrix' and not plug.isNull:
            attribute = plug.attribute()
            apiType = attribute.apiType()
            if apiType == om2.MFn.kTypedAttribute and plug.isArray:
                self = self.children[0]

        # Set new value
        kwargs = {}
        if isinstance(value, (str, unicode, types.StrMixin)):
            mc.setAttr(self, value, type='string')

        elif isinstance(value, (tuple, list, types.Matrix4D)):
            if mayaType == 'TdataCompound':
                children = self.children
                assert len(children) == len(value)
                for child, val in zip(children, value):
                    child.value = val
            else:
                kwargs['type'] = mayaType
                mc.setAttr(self, *value, **kwargs)

        else:
            if isinstance(value, (float, int)):
                minValue = self.min
                if minValue is not None and value < minValue:
                    raise exceptions.AttributeTooLowError(self.node, self.attr, minValue)
                maxValue = self.max
                if maxValue is not None and value > maxValue:
                    raise exceptions.AttributeTooHighError(self.node, self.attr, maxValue)
            else:
                kwargs['type'] = mayaType

            mc.setAttr(self, value, **kwargs)

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
            AttributeDeletedError
        """
        utils.logger.info('Setting %s locked state: %r', self, value)
        utils.raiseIfAttrNotFound(self)
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
            AttributeDeletedError
        """
        utils.logger.info('Setting %s keyable state: %s', self, value)
        utils.raiseIfAttrNotFound(self)
        mc.setAttr(self, keyable=value)

    def connect(self, target, reverse=False):
        # type: (ConnectionType, bool) -> bool
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
        # type: (ConnectionType, bool) -> bool
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
        # type: (str | None, **Any) -> None
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
        self.api.plug = utils.unnetworkPlug(self.node.api.dependencyNode.findPlug(self.attr, False))

    def delete(self):
        # type: () -> None
        """Delete the attribute.

        Raises:
            NodeDeletedError
            AttributeDeletedError
            RuntimeError: Cannot delete static attribute 'pCube1.translate' from node 'pCube1'.
            RuntimeError: Cannot delete child 'pCube1.translateX' of compound attribute 'translate'.
        """
        utils.logger.info('Deleting attribute: %s', self)
        utils.raiseIfAttrNotFound(self)
        if self.api.plug.isElement:
            mc.removeMultiInstance(self, b=True)
        else:
            mc.deleteAttr(self)

    @property
    def keyframes(self):
        # type: () -> AttributeKeyframes
        """Get the keyframe dict."""
        return AttributeKeyframes(self)

    @keyframes.setter
    def keyframes(self, keyframes):
        # type:  (KeyframeBase) -> None
        """Copy the keyframes from something else."""
        keyframes.copyKey()
        self.keyframes.pasteKey()

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
        # type: () -> list[Node]
        """Get the nodes linked to this UV set attribute.

        TODO:
            Tests
        """
        links = mc.uvLink(query=True, uvSet=self.name)
        return [Node(link) for link in links]

    @property
    def min(self):
        # type: () -> float | None
        """Get the minimum value if set."""
        nattr = self.api.numericAttribute
        if nattr is not None and nattr.hasMin():
            return nattr.getMin()
        return None

    @property
    def max(self):
        # type: () -> float | None
        """Get the maximum value if set."""
        nattr = self.api.numericAttribute
        if nattr is not None and nattr.hasMax():
            return nattr.getMax()
        return None

    @property
    def softMin(self):
        # type: () -> float | None
        """Get the soft minimum value if set."""
        nattr = self.api.numericAttribute
        if nattr is not None and nattr.hasSoftMin():
            return nattr.getSoftMin()
        return None

    @property
    def softMax(self):
        # type: () -> float | None
        """Get the soft maximum value if set."""
        nattr = self.api.numericAttribute
        if nattr is not None and nattr.hasSoftMax():
            return nattr.getSoftMax()
        return None

    @property
    def readable(self):
        # type: () -> bool
        """Get if the attribute is readable."""
        return self.api.attribute.readable

    @property
    def writable(self):
        # type: () -> bool
        """Get if the attribute is writable."""
        return self.api.attribute.writable

    @property
    def driver(self):
        # type: () -> Attribute
        """Get the source attribute driving this one."""
        plug = self.api.plug
        while plug.isDestination:
            new = plug.source()
            if new.node().hasFn(om2.MFn.kAnimCurve):
                break
            plug = new
        return Attribute(Node(plug.node()), plug)

    @property
    def default(self):
        # type: () -> bool
        """Determine if the attribute value is equiavlent to its default."""
        plug = self.api.plug
        if plug.isNull:
            return True
        return plug.isDefaultValue()


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .connection import AttributeConnectionProxy, Connection
from .keyframes import AttributeKeyframes, KeyframeBase
from .node import Node
ConnectionType = om2.MPlug
