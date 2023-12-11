import maya.api.OpenMaya as om2
import maya.cmds as mc

from .attributes import NodeAttributes
from ..bounding_box import BoundingBox
from .. import exceptions, types, utils


if str is not bytes:
    unicode = str


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


class ApiData(object):
    """Hold the OpenMaya API objects for a node."""

    __slots__ = ['_object', '_handle', '_instanceNumber',
                 '_dagPaths', '_dependencyNode', '_dagNode']

    def __init__(self, mObject, instanceNumber=-1):
        self._object = mObject
        self._handle = None
        self._instanceNumber = instanceNumber
        self._dependencyNode = self._dagNode = self._dagPaths = None

    def __eq__(self, other):
        if isinstance(other, ApiData):
            return self.handle == other.handle
        return False

    def __hash__(self):
        return self.handle.hashCode()

    @classmethod
    def fromName(cls, name):
        # pylint: disable=protected-access
        """Get API data from the name of a node."""
        selection = om2.MSelectionList()
        try:
            selection.add(name)
        except Exception as e:
            if 'kInvalidParameter' in e.message:
                raise exceptions.NodeNotFoundError(name)
            raise

        new = cls(selection.getDependNode(0))
        try:
            new._dagPaths = [selection.getDagPath(0)]
        except TypeError:
            new._dagPaths = []
        return new

    def copy(self, instanceNumber=-1):
        # pylint: disable=protected-access
        """Create a new copy of the object."""
        new = type(self)(self.object, instanceNumber)
        new._handle = self._handle
        new._dagPaths = self._dagPaths
        new._dependencyNode = self._dependencyNode
        new._dagNode = self._dagNode
        new._dagPaths = self._dagPaths
        return new

    @property
    def object(self):
        """Get the `MObject`.

        Notable methods:
            `isNull()`
        """
        return self._object

    @property
    def handle(self):
        """Get the `MObjectHandle`.

        Notable methods:
            `isValid()`
            `hashCode()`
        """
        if self._handle is None:
            self._handle = om2.MObjectHandle(self.object)
        return self._handle

    @property
    def dependencyNode(self):
        """Get the `MFnDependencyNode`.

        Notable methods:
            `name()`
            `findPlug(attrName, isNetworked)`
        """
        if self._dependencyNode is None:
            self._dependencyNode = om2.MFnDependencyNode(self.object)
        return self._dependencyNode

    @property
    def dagNode(self):
        """Get the `MFnDagNode`.

        Notable methods:
            `parentCount()`
            `parent(idx)`
        """
        if self._dagNode is None:
            self._dagNode = om2.MFnDagNode(self.object)
        return self._dagNode

    @property
    def dagPath(self):
        """Get the `MDagPath` object, or None.

        Notable methods:
            `fullPathName()`
            `partialPathName()`

        If the class was created with an `MObject`, then the `MDagPath`
        may not be set yet. For now, just get any `MDagPath`, since
        `MObjects` can have multiple and don't specify which to use.
        """
        # Load for the first time
        if self._dagPaths is None:
            dagPath = om2.MDagPath.getAPathTo(self.object)
            self._dagPaths = [dagPath]
            return dagPath

        # Loaded before and none exist
        if self._instanceNumber < 1 and not self._dagPaths:
            return None

        return self._dagPaths[self._instanceNumber]

    @property
    def dagPaths(self):
        """Get all `MDagPath` objects to this node and instances.
        Because instances can be created and deleted, it is recommended
        to run `recalculateDagPaths()` first.
        """
        if self._dagPaths is None:
            self.recalculateDagPaths()

        # Get the correct instance number before populating the paths
        if self._instanceNumber < 0:
            return []
        return self._dagPaths

    def recalculateDagPaths(self):
        """Recalculate all the `MDagPath` nodes.
        This should only be used when checking for instances, since they
        can be created or deleted at any time.

        Returns:
            The instance number of the current DAG path.
        """
        if self._instanceNumber < 0:
            # If no paths have been loaded, then assume the class was
            # created with an MObject, which has no specific DAG index
            if self._dagPaths is None:
                self._instanceNumber = 0

            # If there is a path, then its index is likely correct
            elif self._dagPaths:
                self._instanceNumber = self._dagPaths[0].instanceNumber()

        # Load all the DAG paths
        # There are a few ways to get all the paths:
        #     om2.MDagPath.getAllPathsTo(mObject): 3.8 seconds
        #     om2.MFnDagNode(mObject).getAllPaths(): 4.9 seconds
        #     om2.MFnDagNode(dagPath).getAllPaths(): 5.9 seconds
        # Since `MFnDagNode` is already used to get parents, it's
        # probably more efficient to use it here, despite being slower
        # overall
        self._dagPaths = self.dagNode.getAllPaths()
        return self._instanceNumber


class Node(utils.StrMixin):
    """Pointer to a Maya node.

    OpenMaya code adapted from https://www.toadstorm.com/blog/?p=628.
    """

    __slots__ = ['api', '_attrs']

    NODE_TYPES = {
        'shader': set(mc.listNodeTypes('shader')),
    }

    def __init__(self, name, _instanceNumber=-1):
        """Setup the data.

        Parameters:
            name (str): Name of the node.
            _instanceNumber (int): MObject instance number.
                This should not be set manually. It only applies when
                loading with an MObject.
            """
        if isinstance(name, Node):
            self.api = name.api.copy(instanceNumber=_instanceNumber)
        elif isinstance(name, om2.MObject):
            self.api = ApiData(name, instanceNumber=_instanceNumber)
        else:
            self.api = ApiData.fromName(name)

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
            return self.api.handle == other.api.handle
        return super(Node, self).__eq__(other)

    def __hash__(self):
        return hash(self.api)

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
        return self.api.handle.isValid()

    @property
    def uuid(self):
        """Get the node UUID."""
        if self.api.object.isNull():
            raise exceptions.InvalidNodeError(self)
        return self.api.dependencyNode.uuid().asString()

    @property
    def name(self):
        """Get the node name."""
        if self.api.dagPath and self.api.dagPath.isValid():
            return self.api.dagPath.partialPathName()
        if self.api.object.isNull():
            raise exceptions.InvalidNodeError(self)
        return self.api.dependencyNode.name()

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
        self.api.dependencyNode.setName(self.namespace + ':' + name)
        # utils.runAndLog(mc.rename, self, self.namespace + ':' + name)

    @property
    def longName(self):
        """Get the node long name."""
        if self.api.dagPath and self.api.dagPath.isValid():
            return self.api.dagPath.fullPathName()
        return self.name

    @property
    def type(self):
        """Get the node type."""
        if self.api.object.isNull():
            raise exceptions.InvalidNodeError(self)
        return self.api.dependencyNode.typeName
        # return utils.runAndLog(mc.nodeType, self)

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
        return self.api.dependencyNode.namespace

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
        """Get the node parents as a generator."""
        cls = type(self)
        dagParents = map(self.api.dagNode.parent, range(self.api.dagNode.parentCount()))
        return (cls(parent) for parent in dagParents
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
        return self.api.dagPath is not None and self.api.dagPath.isInstanced()

    @property
    def instances(self):
        """Get all the node instances including this."""
        if not self.instanced:
            return [self] if self.exists else []

        instanceNumber = self.api.recalculateDagPaths()
        return [self if instanceNumber == i else type(self)(self, _instanceNumber=i)
                for i, dagPath in enumerate(self.api.dagPaths) if dagPath.isValid()]

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
