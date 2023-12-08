import maya.api.OpenMaya as om2
import maya.cmds as mc

from .attributes import NodeAttributes
from ..bounding_box import BoundingBox
from .. import exceptions, types, utils


_WORLD_HANDLE = None


def _getWorldHandle():
    """Get the handle to the world MObject.
    This is needed as it's parented to everything, but not wanted when
    querying DAG parents.
    """
    global _WORLD_HANDLE
    if _WORLD_HANDLE is not None:
        return _WORLD_HANDLE
    iterator = om2.MItDependencyNodes(om2.MSpace.kWorld)
    while not iterator.isDone():
        mObject = iterator.thisNode()
        if om2.MFnDependencyNode(mObject).name() == 'world':
            _WORLD_HANDLE = om2.MObjectHandle(mObject)
            return _WORLD_HANDLE
        iterator.next()


class Node(utils.StrMixin):
    """Pointer to a Maya node.

    OpenMaya code adapted from https://www.toadstorm.com/blog/?p=628.
    """

    __slots__ = ['_mObject', '_dagPaths', '_instanceNumber', '_dependencyNode', '_attrs']

    NODE_TYPES = {
        'shader': set(mc.listNodeTypes('shader')),
    }

    def __init__(self, name, _instanceNumber=None):
        """Get the handles to the API objects."""
        self._instanceNumber = -1

        if isinstance(name, Node):
            self._mObject = name._mObject
            self._dependencyNode = name._dependencyNode
            self._dagPaths = name._dagPaths
            if _instanceNumber is not None:
                self._instanceNumber = _instanceNumber

        elif isinstance(name, om2.MObject):
            self._mObject = name
            self._dependencyNode = om2.MFnDependencyNode(self._mObject)
            self._dagPaths = om2.MDagPath.getAllPathsTo(self._mObject)
            self._instanceNumber = _instanceNumber or 0

            if len(self._dagPaths) > 1:
                raise NotImplementedError('unable to determine which path to use for mobject')

        else:
            selection = om2.MSelectionList()
            try:
                selection.add(name)
            except Exception as e:
                if 'kInvalidParameter' in e.message:
                    raise exceptions.NodeNotFoundError(name)
                raise
            else:
                self._mObject = selection.getDependNode(0)
                self._dependencyNode = om2.MFnDependencyNode(self._mObject)
                try:
                    self._dagPaths = [selection.getDagPath(0)]
                except TypeError:
                    self._dagPaths = []

        self._attrs = NodeAttributes(self)

    def __new__(cls, name, *args, **kwargs):
        """Create a new class instance, or attribute proxy if an attribute was given."""
        if not isinstance(name, (Node, om2.MObject)) and name and '.' in name:
            node, attr = name.split('.', 1)
            return cls(node, *args, **kwargs).attrs[attr]
        return super(Node, cls).__new__(cls, name, *args, **kwargs)

    def __add__(self, attr):
        """Get a new object or attribute."""
        if attr[0] == '.':
            return self.attrs[attr[1:]]
        return type(self)(str(self) + attr)

    def __eq__(self, other):
        """Determine if two nodes are equal."""
        if isinstance(other, Node):
            return om2.MObjectHandle(self._mObject) == om2.MObjectHandle(other._mObject)
            return self.uuid == other.uuid and self.namespace == other.namespace
        return super(Node, self).__eq__(other)

    def __hash__(self):
        return hash((self.uuid, self.namespace))

    @classmethod
    def create(cls, nodeType, **kwargs):
        """Create a new node.

        Usage:
            >>> node = Node('myNode')
            >>> node.create('transform')
            Node('myNode')
            >>> node.create('transform')
            Node('myNode1')

        Warnings:
            Unrecognized node type '{nodeType}'; preserving node information during this session.
        """
        if kwargs:
            utils.logger.info('Creating "%s" node with arguments %s', nodeType, kwargs)
        else:
            utils.logger.info('Creating "%s" node', nodeType)

        # Create shading node
        if nodeType in cls.NODE_TYPES['shader']:
            result = utils.runAndLog(mc.shadingNode, nodeType, asShader=True, **kwargs)

        # Create shading engine
        elif nodeType == 'shadingEngine':
            kwargs.setdefault('renderable', True)
            kwargs.setdefault('noSurfaceShader', True)
            kwargs.setdefault('empty', True)
            result = utils.runAndLog(mc.sets, **kwargs)

        # Create other
        else:
            result = utils.runAndLog(mc.createNode, nodeType, **kwargs)

        # Get the top level node in the case multiple were created
        if isinstance(result, (list, tuple)):
            result = result[0]

        return cls(result)

    @property
    def exists(self):
        """Determine if the node exists."""
        if self._mObject.isNull():
            return False
        handle = om2.MObjectHandle(self._mObject)
        return handle.isValid()

    @property
    def uuid(self):
        """Get the node UUID."""
        if self._mObject.isNull():
            raise exceptions.InvalidNodeError(self)
        return self._dependencyNode.uuid().asString()

    @property
    def name(self):
        """Get the node name."""
        if self._dagPaths and self._dagPaths[self._instanceNumber].isValid():
            return self._dagPaths[self._instanceNumber].partialPathName()
        if self._mObject.isNull():
            raise exceptions.InvalidNodeError(self)
        return self._dependencyNode.name()

    @name.setter
    def name(self, name):
        """Set a new node name.

        Warnings:
            New name contains invalid characters. Illegal characters were converted to "_".

        Raises:
            RuntimeError: New name has no legal characters.
            RuntimeError: No object matches name
        """
        utils.logger.info('Renaming %r to %r', self, name)
        utils.runAndLog(mc.rename, self, self.namespace + ':' + name)

    @property
    def longName(self):
        """Get the node long name."""
        if self._dagPaths and self._dagPaths[self._instanceNumber].isValid():
            return self._dagPaths[self._instanceNumber].fullPathName()
        return self.name

    @property
    def type(self):
        """Get the node type."""
        if self._mObject.isNull():
            raise exceptions.InvalidNodeError(self)
        return utils.runAndLog(mc.nodeType, self)

    @property
    def attrs(self):
        """Get the attr dict."""
        return self._attrs

    def translate(self, x, y, z):
        """Translate the node with relative coordinates."""
        utils.runAndLog(mc.move, x, y, z, self, relative=True)

    @property
    def translation(self):
        """Get the translation of the node."""
        return types.Coordinate(*utils.runAndLog(mc.xform, self, query=True, translation=True, worldSpace=True))

    @translation.setter
    def translation(self, value):
        """Set a new node translation."""
        utils.runAndLog(mc.xform, self, translation=value, worldSpace=True)

    def rotate(self, x, y, z):
        """Rotate the node with relative coordinates."""
        utils.runAndLog(mc.rotate, x, y, z, self, relative=True)

    @property
    def rotation(self):
        """Get the rotation of the node."""
        return types.Coordinate(*utils.runAndLog(mc.xform, self, query=True, rotation=True, worldSpace=True))

    @rotation.setter
    def rotation(self, value):
        """Set a new node rotation."""
        utils.runAndLog(mc.xform, self, rotation=value, worldSpace=True)

    def scale(self, x, y, z):
        """Rotate the node with relative coordinates."""
        utils.runAndLog(mc.scale, x, y, z, self, relative=True)

    @property
    def scaling(self):
        """Get the scale of the node."""
        return types.Coordinate(*utils.runAndLog(mc.xform, self, query=True, scale=True, worldSpace=True))

    @scaling.setter
    def scaling(self, value):
        """Set a new node scale."""
        utils.runAndLog(mc.xform, self, scale=value, worldSpace=True)

    @property
    def namespace(self):
        """Get the node namespace."""
        parts = self.name.rsplit(':', 1)
        if len(parts) == 1:
            return ''
        return parts[0]

    @namespace.setter
    def namespace(self, namespace):
        """Set a new namespace.
        It will be created if it doesn't exist.
        """
        namespace = namespace.strip(':') if namespace else ''
        if namespace and not utils.runAndLog(mc.namespace, exists=namespace):
            utils.runAndLog(mc.namespace, add=namespace)
        utils.runAndLog(mc.rename, self.name, namespace + ':' + self.name.rsplit(':', 1)[-1])

    @property
    def _parents(self):
        """Get the node parents.
        This is not technically a generator but treat it as such.
        """
        cls = type(self)
        dagNode = om2.MFnDagNode(self._mObject)
        return (cls(parent) for parent in map(dagNode.parent, range(dagNode.parentCount()))
                if om2.MObjectHandle(parent) != _getWorldHandle())

    @property
    def parents(self):
        """Get the node parents."""
        return list(self._parents)

    @property
    def parent(self):
        """Get the node parent."""
        for parent in self._parents:
            return parent
        return None

    @parent.setter
    def parent(self, parent):
        """Set a new node parent.
        Note that Maya will error if setting the parent to the current parent.

        Warnings:
            Object, '{node}', skipped. It is already a child of the parent, '{parent}'.

        Raises:
            AlreadyIsChildError: "{node}" is already a child of "{parent}"
        """
        try:
            if parent:
                utils.runAndLog(mc.parent, self, parent)
            else:
                utils.runAndLog(mc.parent, self, world=True)
        except RuntimeError as e:
            if str(e) == 'Maya command error':
                raise exceptions.AlreadyIsChildError(self, parent or 'world')
            raise

    @property
    def children(self):
        """Get all node children."""
        result = utils.runAndLog(mc.listRelatives, self, children=True, fullPath=True) or []
        return [type(self)(child) for child in result]

    @property
    def shape(self):
        """Get the node shape if it has one."""
        shapes = utils.runAndLog(mc.listRelatives, self, shapes=True, noIntermediate=True, fullPath=True)
        if shapes:
            return type(self)(shapes[0])
        return None

    def instance(self, **kwargs):
        """Create an instance of the object."""
        inst = utils.runAndLog(mc.instance, self, **kwargs)[0]
        return type(self)(inst)

    @property
    def instanced(self):
        """Return if the node is instanced."""
        if self._dagPaths:
            return self._dagPaths[self._instanceNumber].isInstanced()
        return False

    @property
    def instances(self):
        """Get all the node instances including this."""
        if not self._dagPaths or not self.instanced:
            return [self] if self.exists else []

        # Get the correct instance number before populating the paths
        if self._instanceNumber < 0:
            self._instanceNumber = self._dagPaths[0].instanceNumber()

        # Load all the DAG paths
        # There are a few ways to get all the paths:
        #     om2.MDagPath.getAllPathsTo(mObject): 3.8 seconds
        #     om2.MFnDagNode(mObject).getAllPaths()[0]: 4.9 seconds
        #     om2.MFnDagNode(dagPath).getAllPaths()[0]: 5.9 seconds
        self._dagPaths = om2.MDagPath.getAllPathsTo(self._mObject)
        if len(self._dagPaths) == 1:
            return [self] if self.exists else []

        return [self if instanceNumber == self._instanceNumber else type(self)(self, _instanceNumber=instanceNumber)
                for instanceNumber, dagPath in enumerate(self._dagPaths) if dagPath.isValid()]

    @property
    def shadingEngine(self):
        """Get the shading engine assigned to the node.
        Note that this will be assigned to a shape.
        """
        shapes = utils.runAndLog(mc.ls, self, dag=True, shapes=True)
        engines = utils.runAndLog(mc.listConnections, shapes, type='shadingEngine')
        return type(self)(engines[0]) if engines else None

    @shadingEngine.setter
    def shadingEngine(self, shadingEngine):
        """Set a new shadingEngine.

        Warnings:
            No objects specified that can have connections.
        """
        utils.logger.info('Setting %s shader to %s', self, shadingEngine)
        utils.runAndLog(mc.sets, self, edit=True, forceElement=shadingEngine)

    def delete(self):
        """Delete the node.

        Raises:
            DeleteNodeError: No object matches name: {node}
        """
        utils.logger.info('Deleting node: %s', self)
        try:
            utils.runAndLog(mc.delete, self)
        except ValueError as e:
            raise exceptions.DeleteNodeError(self, str(e))

    @property
    def boundingBox(self):
        """Get the bounding box of the node.

        Raises:
            NoBoundingBoxError: "{node}" has no bounding box
        """
        boundingBox = BoundingBox(self)
        if boundingBox == (1e+20, 1e+20, 1e+20, -1e+20, -1e+20, -1e+20):
            raise exceptions.NoBoundingBoxError(self)
        return boundingBox
