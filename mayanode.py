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

from __future__ import absolute_import, division

import logging
try:
    from collections.abc import MutableMapping
except ImportError:
    from collections import MutableMapping

import maya.cmds as mc


logger = logging.getLogger(__name__)

if str is not bytes:
    unicode = str


class GenerateFnCall(object):
    """Lazily generate the function call text.
    This is intended for use with debug logging so that the expensive
    string operations don't need to be performed for most users.
    """
    __slots__ = ['fn', 'args', 'kwargs']

    def __init__(self, fn, *args, **kwargs):
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        module = self.fn.__module__
        if module == 'maya.cmds':
            module = 'mc'
        elif module == 'pymel.core':
            module = 'pm'
        args = map(self.repr, self.args)
        kwargs = ('{}={}'.format(k, self.repr(v)) for k, v in self.kwargs.items())
        params = ', '.join(list(args) + list(kwargs))
        return '{}.{}({})'.format(module, self.fn.__name__, params)

    def repr(self, item):
        if isinstance(item, StrMixin):
            item = str(item)
        return repr(item)


def runAndLog(fn, *args, **kwargs):
    """Run functions and log them."""
    fnCall = GenerateFnCall(fn, *args, **kwargs)
    logger.debug('%s', fnCall)
    return fn(*args, **kwargs)


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

    def rsplit(self, *args, **kwargs):
        return self.name.rsplit(*args, **kwargs)


class AttributeProxy(StrMixin):
    """Easy way of handling attribute values and connections.

    A value is read and set using `.value`.
    A connection is made by using the >> operator between two attributes.
    """

    __slots__ = ['node', 'attr', '_keyframes']

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
        if isinstance(connection, type(self)):
            connection = connection.name

        if reverse:
            logger.info('Creating connection: %s >> %s', connection, self)
            runAndLog(mc.connectAttr, connection, self, force=True)
        else:
            logger.info('Creating connection: %s >> %s', self, connection)
            runAndLog(mc.connectAttr, self, connection, force=True)

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
        return runAndLog(mc.attributeQuery, self.attr, node=self.node.name, exists=True)

    @property
    def type(self):
        """Get the attribute type.

        Raises:
            ValueError: "No object matches name: {self.name}"
        """
        logger.debug('mc.getAttr(%r, type=True)', self)
        attrType = runAndLog(mc.getAttr, self, type=True)
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
        return runAndLog(mc.getAttr, self)

    @value.setter
    def value(self, value):
        """Set a new attribute value.

        Raises:
            ValueError: "setAttr: No object matches name: {self.name}"
        """
        logger.info('Setting %s value: %r', self, value)
        if isinstance(value, (str, unicode, StrMixin)):
            runAndLog(mc.setAttr, self, value, type='string')
        elif isinstance(value, (tuple, list, set)):
            runAndLog(mc.setAttr, self, *value)
        else:
            runAndLog(mc.setAttr, self, value)

    @property
    def locked(self):
        """Get the node locked state.

        Raises:
            ValueError: "No object matches name: {self.name}"
        """
        return runAndLog(mc.getAttr, self, lock=True)

    @locked.setter
    def locked(self, value):
        """Set the node locked state.

        Raises:
            ValueError: "setAttr: No object matches name: {self.name}"
        """
        logger.info('Setting %s locked state: %r', self, value)
        runAndLog(mc.setAttr, self, lock=value)

    @property
    def keyable(self):
        """Get the node keyable state.

        Raises:
            ValueError: "No object matches name: {self.name}"
        """
        return runAndLog(mc.getAttr, self, keyable=True)

    @keyable.setter
    def keyable(self, value):
        """Set the node keyable state.

        Raises:
            ValueError: "setAttr: No object matches name: {self.name}"
        """
        logger.info('Setting %s keyable state: %s', self, value)
        runAndLog(mc.setAttr, self, keyable=value)

    @property
    def connections(self):
        """Get the node connections as plugs.

        Raises:
            ValueError: "No object matches name: {self.name}"
        """
        connections = []
        for nodeAttr in runAndLog(mc.listConnections, self, plugs=True) or ():
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

        logger.info('Adding attribute %s with arguments %s', self, kwargs)
        runAndLog(mc.addAttr, self.node, longName=self.attr, **kwargs)
        return self

    def ensure(self, attrType, **kwargs):
        """Create the attribute if it doesn't exist."""
        if self.exists:
            return self
        return self.create(attrType, **kwargs)

    def delete(self):
        """Delete the attribute."""
        logger.info('Deleting attribute: %s', self)
        runAndLog(mc.deleteAttr, self)

    @property
    def keyframes(self):
        """Get the keyframe dict."""
        return self._keyframes


class AttributeKeyframes(MutableMapping):
    """Dictionary interface to keyframes on a specific attribute."""

    def __init__(self, attr):
        self.attr = attr
        super(AttributeKeyframes, self).__init__()

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self.attr)

    def __len__(self):
        return len(self.keys())

    def __iter__(self):
        for key, value in zip(self.keys(), self.values()):
            yield key, value

    def __getitem__(self, frame):
        return KeyframeProxy(self, frame)

    def __setitem__(self, frame, value):
        KeyframeProxy(self, frame).set(value)

    def __delitem__(self, frame):
        KeyframeProxy(self, frame).delete()

    def keys(self):
        return runAndLog(mc.keyframe, self.attr.node, attribute=self.attr.attr, query=True, timeChange=True)

    def values(self):
        return runAndLog(mc.keyframe, self.attr.node, attribute=self.attr.attr, query=True, valueChange=True)


class KeyframeProxy(object):
    """Controls for keyframes on a specific attribute and frame."""

    __slots__ = ['kf', 'frame']

    def __init__(self, keyframe, frame=None):
        self.kf = keyframe

        if frame is None:
            frame = runAndLog(mc.currentTime, query=True)

        self.frame = frame

    def __repr__(self):
        return '{}({!r}, {})'.format(type(self).__name__, self.kf, self.frame)

    @property
    def value(self):
        if not isinstance(self.frame, slice):
            result = runAndLog(mc.keyframe, self.kf.attr.node, attribute=self.kf.attr.attr, query=True, valueChange=True, time=(self.frame, self.frame))
            if not result:
                return None
            return result[0]

        if (self.frame.step or 1) != 1:
            results = []
            for frame in range(self.frame.start, self.frame.stop, self.frame.step):
                result = runAndLog(mc.keyframe, self.kf.attr.node, attribute=self.kf.attr.attr, query=True, valueChange=True, time=(frame, frame))
            return results

        return runAndLog(mc.keyframe, self.kf.attr.node, attribute=self.kf.attr.attr, query=True, valueChange=True, time=(self.frame.start, self.frame.stop))

    def set(self, value=None):
        logger.info('Setting keyframe on "%s" (frame %s, value %s)', self.kf.attr, self.frame, value)

        args = [self.kf.attr.node]
        kwargs = dict(attribute=self.kf.attr.attr, time=self.frame)

        if isinstance(self.frame, slice):
            kwargs['time'] = list(range(self.frame.start, self.frame.stop, self.frame.step or 1))
        else:
            kwargs['time'] = self.frame

        if value is not None:
            kwargs['value'] = value

        runAndLog(mc.setKeyframe, *args, **kwargs)

    def delete(self):
        logger.info('Deleting keyframe on "%s" (frame %s)', self.kf.attr, self.frame)
        if not isinstance(self.frame, slice):
            runAndLog(mc.cutKey, self.kf.attr.node, attribute=self.kf.attr.attr, time=(self.frame, self.frame))

        elif (self.frame.step or 1) != 1:
            for frame in range(self.frame.start, self.frame.stop, self.frame.step):
                runAndLog(mc.cutKey, self.kf.attr.node, attribute=self.kf.attr.attr, time=(frame, frame))

        else:
            runAndLog(mc.cutKey, self.kf.attr.node, attribute=self.kf.attr.attr, time=(self.frame.start, self.frame.stop))


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
        for attr in runAndLog(mc.listAttr, self.node):
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
        return bool(runAndLog(mc.ls, self))

    @property
    def type(self):
        """Get the node type.

        Raises:
            RuntimeError: "No object matches name: {self.name}"
        """
        return runAndLog(mc.nodeType, self)

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
        logger.info('Renaming %r to %r', self, name)
        self._name = runAndLog(mc.rename, self, name)

    @property
    def longName(self):
        """Get the node long name.

        Raises:
            RuntimeError: "No object matches name: {self.name}"
        """
        result = mc.ls(self.name, long=True)
        if result:
            return result[0]
        raise RuntimeError('No object matches name: {}'.format(self))

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
        return [Node(parent) for parent in runAndLog(mc.listRelatives, self, parent=True, fullPath=True)]

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
        runAndLog(mc.parent, self, parent)

    @property
    def children(self):
        """Get all node children."""
        return [Node(child) for child in runAndLog(mc.listRelatives, self, children=True, fullPath=True)]

    @property
    def shape(self):
        """Get the node shape if it has one."""
        shapes = runAndLog(mc.listRelatives, shapes=True, noIntermediate=True, fullPath=True)
        if shapes:
            return Node(shapes[0])
        return None

    @property
    def instances(self):
        """Get all the node instances including self."""
        return [Node(inst) for inst in runAndLog(mc.ls, self, allPaths=True)]

    @property
    def shadingEngine(self):
        """Get the shading engine assigned to the node.
        Note that this will be assigned to a shape.
        """
        shapes = runAndLog(mc.ls, self, dag=True, shapes=True)
        engines = runAndLog(mc.listConnections, shapes, type='shadingEngine')
        if engines:
            return Node(engines[0])
        return None

    @property
    def boundingBox(self):
        """Get the bounding box of the node."""
        return BoundingBox(self)

    @shadingEngine.setter
    def shadingEngine(self, shadingEngine):
        """Set a new shadingEngine."""
        logger.info('Setting %s shader to %s', self, shadingEngine)
        runAndLog(mc.sets, self, edit=True, forceElement=shadingEngine)

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
        logger.info('Creating %r node with arguments %s', nodeType, kwargs)

        # Ensure data is loaded
        if 'shader' not in self.NODE_TYPES:
            self.NODE_TYPES['shader'] = set(runAndLog, mc.listNodeTypes('shader'))

        # Create shading node
        if nodeType in self.NODE_TYPES['shader']:
            self._name = runAndLog(mc.shadingNode, nodeType, asShader=True, **kwargs)

        # Create shading engine
        elif nodeType == 'shadingEngine':
            kwargs.setdefault('renderable', True)
            kwargs.setdefault('noSurfaceShader', True)
            kwargs.setdefault('empty', True)
            self._name = runAndLog(mc.sets, **kwargs)

        # Create other
        else:
            self._name = runAndLog(mc.createNode, nodeType, **kwargs)
        return self

    def ensure(self, nodeType, **kwargs):
        """Make sure the node exists."""
        if self.exists:
            return self
        return self.create(nodeType, **kwargs)

    def delete(self):
        """Delete the node."""
        logger.info('Deleting node: %s', self)
        runAndLog(mc.delete, self)


class BoundingBox(tuple):
    """Get the bounding box of a node and perform calculations."""

    def __new__(cls, node):
        boundingBox = runAndLog(mc.exactWorldBoundingBox, node)
        new = tuple.__new__(cls, boundingBox)
        new.node = node
        return new

    @property
    def x(self):
        """Get the X coordinate."""
        return (self.xMax + self.xMin) / 2

    @property
    def y(self):
        """Get the Y coordinate."""
        return (self.yMax + self.yMin) / 2

    @property
    def z(self):
        """Get the Z coordinate."""
        return (self.zMax + self.zMin) / 2

    @property
    def origin(self):
        """Get the origin coordinate."""
        return (self.x, self.y, self.z)

    @property
    def xMin(self):
        """Get the minimum X limit."""
        return self.__getitem__(0)

    @property
    def yMin(self):
        """Get the minimum Y limit."""
        return self.__getitem__(1)

    @property
    def zMin(self):
        """Get the minimum Z limit."""
        return self.__getitem__(2)

    @property
    def xMax(self):
        """Get the maximum X limit."""
        return self.__getitem__(3)

    @property
    def yMax(self):
        """Get the maximum Y limit."""
        return self.__getitem__(4)

    @property
    def zMax(self):
        """Get the maximum Z limit."""
        return self.__getitem__(5)

    @property
    def width(self):
        """Get the width."""
        return abs(self.xMax - self.xMin)

    @property
    def height(self):
        """Get the height."""
        return abs(self.yMax - self.yMin)

    @property
    def depth(self):
        """Get the depth."""
        return abs(self.zMax - self.zMin)

    def drawCube(self):
        """Draw a cube representation of the bounding box."""
        cube = mc.polyCube(width=self.width, height=self.height, depth=self.depth, name='BoundingBox')[0]
        mc.move(self.x, self.y, self.z, cube, absolute=True)
        mc.parent(cube, self.node)
        return cube
