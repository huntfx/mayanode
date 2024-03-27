import math

import maya.api.OpenMaya as om2
import maya.cmds as mc

from ... import exceptions, types, utils


NODE_TYPES = {
    'shader': set(mc.listNodeTypes('shader')),
}

_WORLD_HANDLE = None

_WORLD_DAG_PATH = None


def _getWorldHandle():
    """Get the handle to the world `MObject`.
    This is needed as it's parented to everything, but not wanted when
    querying DAG parents.
    """
    global _WORLD_HANDLE, _WORLD_DAG_PATH
    if _WORLD_HANDLE is not None:
        return _WORLD_HANDLE
    iterator = om2.MItDependencyNodes(om2.MSpace.kWorld)
    while not iterator.isDone():
        mObject = iterator.thisNode()
        if om2.MFnDependencyNode(mObject).name() == 'world':
            _WORLD_HANDLE = om2.MObjectHandle(mObject)
            _WORLD_DAG_PATH = om2.MDagPath.getAPathTo(mObject)
            return _WORLD_HANDLE
        iterator.next()


def _getWorldDagPath():
    """Get the world `MDagPath`."""
    global _WORLD_DAG_PATH
    if _WORLD_DAG_PATH is None:
        _getWorldHandle()
    return _WORLD_DAG_PATH


def _getShadingGroups(mobj):
    """Get all the shading group nodes for a given node.

    Equivalent:
        `mc.listConnections(self, type='shadingEngine')
    """
    if not om2.MObjectHandle(mobj).isValid():
        return

    iterator = om2.MItDependencyGraph(
        mobj,
        om2.MFn.kShadingEngine,
        om2.MItDependencyGraph.kDownstream,
        om2.MItDependencyGraph.kDepthFirst,
        om2.MItDependencyGraph.kPlugLevel,
    )
    for _ in iterator:
        node = iterator.currentNode()
        if not node.isNull():
            yield node


class Ancestors(types.LazyList):
    """Only load the ancestor nodes when needed.

    This is very fast when requesting the first or last ancestor or a
    node. When iterating over every ancestor, the overhead cost of
    wrapping the list in this class is minimal.
    """

    __slots__ = ['_node', '_ancestors', '_loadedAllAncestors']

    def __init__(self, node):
        self._node = node
        self._ancestors = []
        self._loadedAllAncestors = False
        super(Ancestors, self).__init__()

    @property
    def node(self):
        return self._node

    def __bool__(self):
        dagPath = self.node.api.dagPath
        if dagPath is None:
            return False
        return dagPath.length() > 1
    __nonzero__ = __bool__

    def __len__(self):
        """Get the number of ancestors."""
        # If already loaded then the length is correct
        if self._loadedAllAncestors or self._ancestors:
            return len(self._ancestors)

        # Get the DAG path length
        dagPath = self.node.api.dagPath
        if dagPath is None:
            self._loadedAllAncestors = True
            return 0
        ancestorLength = dagPath.length() - 1

        # Populate the data lists
        self._ancestors.extend(None for _ in range(ancestorLength - len(self._ancestors)))
        self._data.extend(None for _ in range(ancestorLength - len(self._data)))
        return ancestorLength

    def _loadData(self, index=None):
        """Load the ancestor data.

        If a negative index is requested, then all the DAG paths will
        be loaded, but only the index will get an attached class
        instance. If no index is requested, then all DAG paths will be
        loaded, and all will get a class instance. If a positive index
        is requested, then it will find the latest known DAG path, jump
        ahead to the specified index, and create a node for that.

        Simple benchmark from fastest to slowest:
            `ancestors[0]`  # 18
            `ancestors[n]`  # 24
            `ancestors[-i]`  # 32
            `list(ancestors)`  # 59
            `[ancestors[i] for i in range(n)]`  # 67
            `[ancestors[i] for i in reversed(range(n))]`  # 74
        """
        if self.node.api.dagPath is None:
            return

        if not self._loadedAllAncestors:
            ancestorLength = self.__len__()

            # Load in all the missing data
            # If a negative index then not all data needs loading
            if index is None or index < 0:

                previousDagPath = self.node.api.dagPath
                for i, ancestor in enumerate(self._ancestors):
                    if ancestor is None:
                        self._ancestors[i] = previousDagPath = om2.MDagPath(previousDagPath).pop()
                    else:
                        previousDagPath = ancestor

                self._loadedAllAncestors = True

            # Load a single positive index
            elif 0 <= index < ancestorLength and self._ancestors[index] is None:

                # Find the closest child DAG path
                dagPath = None
                if index:
                    i = index - 1
                    while i >= 0:
                        if self._ancestors[i] is not None:
                            dagPath = om2.MDagPath(self._ancestors[i])
                            dagOffset = i
                            break
                        i -= 1

                # Use the nodes DAG path
                if dagPath is None:
                    dagPath = om2.MDagPath(self.node.api.dagPath)
                    dagOffset = -1

                # Jump down the required number of levels
                self._ancestors[index] = dagPath.pop(index - dagOffset)

        # Get the requested indexes
        indexes = []
        if index is None:
            indexes.extend(i for i, item in enumerate(self._data) if item is None)
        else:
            # Ignore any index error here as it's only loading the data
            try:
                if self._data[index] is None:
                    indexes = [index]
            except IndexError:
                pass

        # Map nodes to indexes
        for index in indexes:
            self._data[index] = Node(self._ancestors[index])


class _ApiData(object):
    """Hold the OpenMaya API objects for a node."""

    __slots__ = ['_object', '_handle', '_instanceNumber',
                 '_dagPaths', '_dependencyNode', '_dagNode',
                 '_transform', '_mesh', '_reference']

    def __init__(self, mObject, instanceNumber=-1):
        if mObject.isNull():
            raise exceptions.NullMObjectError

        self._object = mObject
        self._instanceNumber = instanceNumber
        self._handle = None
        self._dagNode = self._dagPaths = self._dependencyNode = None
        self._transform = self._mesh = self._reference = None

    def __bool__(self):
        """Determine if the node is valid."""
        return not self.object.isNull()
    __nonzero__ = __bool__

    def __eq__(self, other):
        if isinstance(other, _ApiData):
            return self.handle == other.handle
        return False

    def __hash__(self):
        dagPath = self.dagPath
        return self.handle.hashCode() + dagPath.instanceNumber() if dagPath is not None else 0

    @classmethod
    def fromName(cls, name):
        # pylint: disable=protected-access
        """Get API data from the name of a node."""
        selection = om2.MSelectionList()
        try:
            selection.add(name)
        except Exception as e:
            if str(e) == '(kInvalidParameter): Object does not exist':
                raise exceptions.NodeNotFoundError(name)
            raise

        mobject = selection.getDependNode(0)
        new = cls(mobject)
        if mobject.hasFn(om2.MFn.kDagNode):
            new._dagPaths = [selection.getDagPath(0)]
        else:
            new._dagPaths = []
        return new

    @classmethod
    def fromDagPath(cls, dagPath):
        # pylint: disable=protected-access
        """Get API data from an `MDagPath`."""
        instanceNumber = dagPath.instanceNumber()
        new = cls(dagPath.node(), instanceNumber=instanceNumber)
        new._dagPaths = [None for _ in range(instanceNumber)] + [dagPath]
        return new

    @classmethod
    def fromHandle(cls, handle):
        # pylint: disable=protected-access
        """Get API data from an `MObjectHandle`."""
        new = cls(handle.object())
        new._handle = handle
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
        new._mesh = self._mesh
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
            if self.object.hasFn(om2.MFn.kDagNode):
                self._dagNode = om2.MFnDagNode(self.object)
            else:
                self._dagNode = -1

        if self._dagNode == -1:
            return None
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
            if self.object.hasFn(om2.MFn.kDagNode):
                self._dagPaths = [om2.MDagPath.getAPathTo(self.object)]
            else:
                self._dagPaths = []

        if not self._dagPaths:
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
        if self.dagNode is not None:
            self._dagPaths = self.dagNode.getAllPaths()
        return self._instanceNumber

    def getTransformDagPath(self):
        """Get the transform dag path from a shape node."""
        if self.dagPath is None:
            return None

        transformDagPath = self.dagPath.transform()
        if self.handle == om2.MObjectHandle(transformDagPath):
            return None
        return transformDagPath

    def getShapeDagPath(self):
        """Get the shape dag path from a transform node."""
        if self.dagPath is None or not self.dagPath.numberOfShapesDirectlyBelow():
            return None

        shapeDagPath = om2.MDagPath(self.dagPath)
        shapeDagPath.extendToShape()
        if shapeDagPath == self.dagPath:
            return None
        return shapeDagPath

    def hasGeometry(self):
        """Determine if the object contains geometry.
        If not, then `MFnMesh` commands will fail.
        """
        return om2.MItGeometry(self.object).index() != -1

    @property
    def mesh(self):
        """Get the `MFnMesh`.

        Notable methods:
            `numVertices`
            `numEdges`
            `numPolygons`
            `numFaceVertices`
            `currentUVSetName()`
        """
        if self._mesh is None:
            if self.object.hasFn(om2.MFn.kMesh) and self.hasGeometry():
                self._mesh = om2.MFnMesh(self.object)
            else:
                self._mesh = -1

        if self._mesh == -1:
            return None
        return self._mesh

    def getShapeMesh(self):
        """Get the `MFnMesh` for a transform or shape.

        Only shapes have support for it, so if a transform is given
        then first get the shape and then get the mesh.
        This is not as efficient when running on a transform.
        """
        if self.mesh is not None:
            return self.mesh

        shapeDagPath = self.getShapeDagPath()
        if shapeDagPath is None:
            return None

        shapeObject = shapeDagPath.node()
        if shapeObject.hasFn(om2.MFn.kMesh):
            return om2.MFnMesh(shapeObject)
        return None

    @property
    def transform(self):
        """Get the `MFnTransform`

        Notable methods:
            `transformation()`
        """
        if self._transform is None:
            if self.object.hasFn(om2.MFn.kTransform):
                self._transform = om2.MFnTransform(self.object)
            else:
                self._transform = -1

        if self._transform == -1:
            return None
        return self._transform

    @property
    def reference(self):
        """Get the `MFnReference`.

        Notable methods:
            nodes()
            associatedNamespace(shortName: bool)
            filename(resolvedName: bool, includePath: bool, includeCopyNumber: bool)
        """
        if self._reference is None:
            if self.object.hasFn(om2.MFn.kReference):
                self._reference = om2.MFnReference(self.object)
            else:
                self._reference = -1

        if self._reference == -1:
            return None
        return self._reference


class Node(utils.StrMixin):
    """Pointer to a Maya node.

    OpenMaya code inspired by https://www.toadstorm.com/blog/?p=628.
    Note that when calling `maya.cmds`, if `__str__` raises an error,
    then it will raise `TypeError: Object  is invalid`.
    """

    __slots__ = ['api', '_attrs']

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
            self.api = _ApiData(name, instanceNumber=_instanceNumber)
        elif isinstance(name, om2.MDagPath):
            self.api = _ApiData.fromDagPath(name)
        elif isinstance(name, om2.MObjectHandle):
            self.api = _ApiData.fromHandle(name)
        else:
            self.api = _ApiData.fromName(name)

        self._attrs = NodeAttributes(self)

    def __new__(cls, name, *args, **kwargs):
        """Create a new class instance, or attribute proxy if an attribute was given."""
        if not isinstance(name, (Node, om2.MObject, om2.MDagPath, om2.MObjectHandle)) and name and '.' in name:
            node, attr = name.split('.', 1)
            return cls(node, *args, **kwargs).attrs[attr]
        return super(Node, cls).__new__(cls, name, *args, **kwargs)

    def __add__(self, attr):
        """Get a new object or attribute."""
        if attr[0] == '.':
            return self.attrs[attr[1:]]
        return type(self)(str(self) + attr)

    def __eq__(self, other):
        """Determine if two nodes are equal.

        Examples:
            >>> nodes = Node('|cube'), Node('|sphere'), Node('|parent|cube')]

            # Short name
            >>> 'sphere' in nodes
            True

            # Non-unique short name (the short name is actually "|cube")
            >>> 'cube' in nodes
            True

            # Long name
            >>> '|parent|cube' in nodes:
            True

            # Partial paths
            >>> 'parent|cube' in nodes:
            True
        """
        if isinstance(other, Node):
            return self.api.handle == other.api.handle
        other = str(other)

        # Comparing against a unique name
        if '|' in other:
            if other[0] == '|':
                return self.longName == other
            return self.longName.endswith(other)

        # Comparing against a potentially none unique name
        return self.name.rsplit('|', 1)[-1] == other

    def __hash__(self):
        return hash(self.api)

    @classmethod
    def ls(self, *args, **kwargs):
        """Shortcut to search the scene."""
        kwargs['objectsOnly'] = True
        result = utils.runAndLog(mc.ls, *args, **kwargs)
        return [Node(node) for node in result]

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
        if nodeType in NODE_TYPES['shader']:
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
        """Determine if the node exists.

        Preemptive tests barely add any overhead - 1,000,000 calls takes
        less than a second.
        """
        return self.api.handle.isValid()

    @property
    def uuid(self):
        """Get the node UUID.
        This will always work even when the node is deleted.

        Returns:
            UUID as a string.
        """
        api = self.api
        if not api:
            return ''
        return api.dependencyNode.uuid().asString()

    @property
    def name(self):
        """Get the node name.
        This will always work even when the node is deleted.

        Returns:
            Node name as a string.
        """
        api = self.api
        if not api:
            return ''
        if api.dagPath is not None and api.dagPath.isValid():
            return api.dagPath.partialPathName()
        return api.dependencyNode.name()

    @name.setter
    def name(self, name):
        """Set a new node name.

        Warnings:
            New name contains invalid characters. Illegal characters were converted to "_".

        Alternatives:  # Both don't work well with undo
            `om2.MDagModifier().renameNode(self.api.object, self.namespace + ':' + name).doIt()`
            `self.api.dependencyNode.setName(self.namespace + ':' + name)`

        Raises:
            RuntimeError: New name has no legal characters.
            NodeDeletedError
        """
        utils.logger.info('Renaming %r to %r', self, name)
        utils.raiseIfNodeNotFound(self)
        utils.runAndLog(mc.rename, self, self.namespace + ':' + name)

    @property
    def longName(self):
        """Get the node long name.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        if self.api.dagPath is not None and self.api.dagPath.isValid():
            return self.api.dagPath.fullPathName()
        return self.name

    @property
    def type(self):
        """Get the node type.

        Alternatives:
            `mc.nodeType(self)`

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        return self.api.dependencyNode.typeName

    @property
    def attrs(self):
        """Get the attr dict."""
        utils.raiseIfNodeNotFound(self)
        return self._attrs

    def translate(self, x, y, z):
        """Translate the node with relative coordinates.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        utils.runAndLog(mc.move, x, y, z, self, relative=True)

    @property
    def translation(self):
        """Get the translation of the node.

        Equivalent:
            `mc.xform(self, query=True, translation=True, worldSpace=True)`

        Raises:
            NodeDeletedError

        Returns:
            Named coordinate tuple of X, Y, Z.
        """
        utils.raiseIfNodeNotFound(self)
        if self.api.dagPath is None:
            return None
        matrix = om2.MTransformationMatrix(self.api.dagPath.inclusiveMatrix())
        vector = matrix.translation(om2.MSpace.kWorld)
        return types.Coordinate(vector.x, vector.y, vector.z)

    @translation.setter
    def translation(self, value):
        """Set a new node translation.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        utils.runAndLog(mc.xform, self, translation=value, worldSpace=True)

    def rotate(self, x, y, z):
        """Rotate the node with relative coordinates.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        utils.runAndLog(mc.rotate, x, y, z, self, relative=True)

    @property
    def rotation(self):
        """Get the rotation of the node.

        Equivalent:
            `mc.xform(self, query=True, rotation=True, worldSpace=True)`

        Raises:
            NodeDeletedError

        Returns:
            Named coordinate tuple of X, Y, Z.
        """
        utils.raiseIfNodeNotFound(self)
        if self.api.dagPath is None:
            return None
        matrix = om2.MTransformationMatrix(self.api.dagPath.inclusiveMatrix())
        euler = matrix.rotation()
        return types.Coordinate(math.degrees(euler.x), math.degrees(euler.y), math.degrees(euler.z))

    @rotation.setter
    def rotation(self, value):
        """Set a new node rotation.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        utils.runAndLog(mc.xform, self, rotation=value, worldSpace=True)

    def scale(self, x, y, z):
        """Rotate the node with relative coordinates.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        utils.runAndLog(mc.scale, x, y, z, self, relative=True)

    @property
    def scaling(self):
        """Get the scale of the node.

        Equivalent:
            `mc.xform(self, query=True, scale=True, worldSpace=True)`

        Raises:
            NodeDeletedError

        Returns:
            Named coordinate tuple of X, Y, Z.
        """
        utils.raiseIfNodeNotFound(self)
        if self.api.dagPath is None:
            return None
        matrix = om2.MTransformationMatrix(self.api.dagPath.inclusiveMatrix())
        scale = matrix.scale(om2.MSpace.kWorld)
        return types.Coordinate(*scale)

    @scaling.setter
    def scaling(self, value):
        """Set a new node scale.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        utils.runAndLog(mc.xform, self, scale=value, worldSpace=True)

    @property
    def namespace(self):
        """Get the node namespace.

        Raises:
            NodeDeletedError
            RuntimeError: Cannot rename a read only node.
        """
        utils.raiseIfNodeNotFound(self)
        return Namespace.fromNode(self)

    @namespace.setter
    def namespace(self, namespace):
        """Set a new namespace.
        It will be created if it doesn't exist. Any illegal characters
        will be automatically converted to underscores.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        if not namespace or namespace == ':':
            newName = self.name.rsplit(':', 1)[-1]
            utils.logger.info('Setting "%s" namespace to ":"', newName)
            utils.runAndLog(mc.rename, self.name, ':' + newName)

        else:
            utils.logger.info('Setting "%s" namespace to "%s"', self, namespace)
            namespace = Namespace(namespace)
            if not namespace.exists:
                namespace.create()
            utils.runAndLog(mc.rename, self.name, namespace + ':' + self.name.rsplit(':', 1)[-1])

    @property
    def parents(self):
        """Get the node parents."""
        if self.api.dagNode is None:
            return []

        result = []
        for parent in map(self.api.dagNode.parent, range(self.api.dagNode.parentCount())):
            if om2.MObjectHandle(parent) == _getWorldHandle():
                continue
            result.append(type(self)(parent))
        return result

    @property
    def parent(self):
        """Get the node parent."""
        if not self.exists:
            return None
        dagPath = self.api.dagPath
        if dagPath is None:
            return None

        parentDagPath = om2.MDagPath(dagPath).pop()
        if parentDagPath == _getWorldDagPath():
            return None
        return type(self)(parentDagPath)

    @parent.setter
    def parent(self, parent):
        """Set a new node parent.
        Note that Maya will error if setting the parent to the current parent.

        Warnings:
            Object, '{node}', skipped. It is already a child of the parent, '{parent}'.

        Raises:
            NodeDeletedError
            NodeNotFoundError
            AlreadyIsChildError: "{node}" is already a child of "{parent}"
        """
        utils.raiseIfNodeNotFound(self)
        if self.api.dagNode is None:
            raise exceptions.NotADagNodeError(self)
        try:
            if parent:
                utils.runAndLog(mc.parent, self, parent)
            else:
                utils.runAndLog(mc.parent, self, world=True)
        except RuntimeError as e:
            if str(e) == 'Maya command error':
                raise exceptions.AlreadyIsChildError(self, parent or 'world')
            raise
        except ValueError:
            if parent:
                raise exceptions.NodeNotFoundError(parent)
            raise

    @property
    def children(self):
        """Get all node children.

        TODO: Test correct instance.
        """
        if not self.exists or self.api.dagNode is None:
            return []
        apiChildren = map(self.api.dagNode.child, range(self.api.dagNode.childCount()))
        return list(map(type(self), apiChildren))

    @property
    def descendents(self):
        """Get all node descendents.
        Instances are deduplicated so this only returns unique nodes.

        Equivalent:
            `mc.listRelatives(self, allDescendents=True)`
        """
        if not self.exists or self.api.dagPath is None:
            return []

        cls = type(self)
        dag = om2.MItDag()
        dag.reset(self.api.dagPath, om2.MItDag.kBreadthFirst)
        dag.next()

        seen = set()
        result = []
        for _ in dag:
            item = dag.currentItem()

            if dag.isInstanced():
                handle = om2.MObjectHandle(item)
                if handle.hashCode() in seen:
                    continue
                seen.add(handle.hashCode())
                result.append(cls(handle))

            else:
                result.append(cls(item))
        return result

    @property
    def ancestors(self):
        """Get all node ancestors, starting with the parent.
        This does not get ancestors of other instances.

        Equivalent:
            >>> def ancestors(node):
            ...     parent = node.parent
            ...     while parent is not None:
            ...         yield parent
            ...         parent = parent.parent
        """
        return Ancestors(self)

    @property
    def connections(self):
        """Get the node connections as plugs."""
        if not self.exists:
            return []
        return NodeConnectionProxy(self)

    @property
    def shape(self):
        """Get the shape node."""
        if not self.exists:
            return None

        shapeDagPath = self.api.getShapeDagPath()
        if shapeDagPath is None:
            return None
        return Node(shapeDagPath)

    @property
    def transform(self):
        """Get the transform node."""
        if not self.exists:
            return None

        transformDagPath = self.api.getTransformDagPath()
        if transformDagPath is None:
            return None
        return Node(transformDagPath)

    def instance(self, **kwargs):
        """Create an instance of the object.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        inst = utils.runAndLog(mc.instance, self, **kwargs)[0]
        return type(self)(inst)

    @property
    def instanced(self):
        """Return if the node is instanced."""
        if not self.exists:
            return False
        return self.api.dagPath is not None and self.api.dagPath.isInstanced()

    @property
    def instances(self):
        """Get all the node instances including this."""
        if not self.exists:
            return []
        if not self.instanced:
            return [self]

        instanceNumber = self.api.recalculateDagPaths()
        return [self if instanceNumber == i else type(self)(self, _instanceNumber=i)
                for i, dagPath in enumerate(self.api.dagPaths) if dagPath.isValid()]

    @property
    def instanceNumber(self):
        """Get the index of the current index."""
        return self.api.recalculateDagPaths()

    @property
    def intermediate(self):
        """Return if the node is intermediate."""
        if not self.exists or self.api.dagNode is None:
            return False
        return self.api.dagNode.isIntermediateObject

    @property
    def default(self):
        """Return if the node is default."""
        utils.raiseIfNodeNotFound(self)
        return self.api.dependencyNode.isDefaultNode

    @property
    def shadingGroups(self):
        """Get all the shading groups assigned to this node.

        TODO:
            Test with instances
        """
        return [Node(sg) for sg in _getShadingGroups(self.api.object)]

    @property
    def shadingEngine(self):
        """Get the shading group assigned to the node.

        TODO:
            Rename to `shadingGroup`
            Test with instances
        """
        for sg in _getShadingGroups(self.api.object):
            return sg
        return None

    @shadingEngine.setter
    def shadingEngine(self, shadingEngine):
        """Set a new shading group on the current object instance.

        Warnings:
            No objects specified that can have connections.

        Raises:
            NodeDeletedError

        TODO:
            Test with instances
        """
        utils.logger.info('Setting %s shader to %s', self, shadingEngine)
        utils.raiseIfNodeNotFound(self)
        utils.runAndLog(mc.sets, self, edit=True, forceElement=shadingEngine)

    @property
    def visible(self):
        """Determine if the node is visible.

        First test the "visibility" attribute. If it is still set, then
        test it of the current parent. Other parents are not checked as
        they are only related to other instances of the node.
        If it does not exist, then fallback to the parent. If the parent
        also does not exist then its safe to say this is not visible.

        Note that if all children are hidden and the node is empty, then
        it will still be "visible" since the node itself is not hidden.
        """
        if not self.exists:
            return False

        # Attempt to check the attribute if it exists
        hasAttr = self.api.dependencyNode.hasAttribute('visibility')
        if hasAttr and not self.attrs['visibility'].value:
            return False

        # Check if a parent exists
        parent = self.parent
        if parent is None:
            return hasAttr

        # Recursively check if any parents are visible
        return parent.visible

    def delete(self):
        """Delete the node.

        Raises:
            NodeDeletedError
        """
        utils.logger.info('Deleting node: %s', self)
        try:
            utils.runAndLog(mc.delete, self)
        except ValueError as e:
            raise exceptions.NodeDeletedError(str(e))

    @property
    def uvSet(self):
        """Get the current UV set.

        Equivalent:
            `mc.polyUVSet(self, query=True, currentUVSet=True)[0]`
        """
        if not self.exists or self.api.mesh is None:
            return None
        return UVSet(self, self.api.mesh.currentUVSetName())

    @uvSet.setter
    def uvSet(self, uvSet):
        """Set the current UV set.
        This will be skipped if the requested UV set is the current one.

        Raises:
            UVSetNotFoundError
            NodeNotFoundError
        """
        utils.raiseIfNodeNotFound(self)

        mesh = self.api.mesh
        if mesh is None:
            raise exceptions.UVSetNotFoundError(self, uvSet)

        currentUVSet = mesh.currentUVSetName()
        if uvSet == currentUVSet:
            return

        utils.logger.info('Setting %s UV set to "%s" (was "%s")', self, uvSet, currentUVSet)
        if uvSet not in mesh.getUVSetNames():
            raise exceptions.UVSetNotFoundError(self, uvSet)
        return utils.runAndLog(mc.polyUVSet, self, currentUVSet=True, uvSet=uvSet)

    @property
    def uvSets(self):
        """Get a list of UV sets for the node.

        Equivalent:
            `mc.polyUVSet(self, query=True, allUVSets=True)`
        """
        if not self.exists or self.api.mesh is None:
            return []
        return [UVSet(self, uvSet) for uvSet in self.api.mesh.getUVSetNames()]

    @property
    def uvLinks(self):
        """Get any UV links pointing to the current node.

        TODO:
            Tests
            Return as `UvLink` object
        """
        if not self.exists:
            return []

        # Check if the object is able to receive UV links
        if not utils.runAndLog(mc.uvLink, isValid=True, texture=self):
            return []

        # Get the UV links
        # The returned list is like `['ns:node.uvSet[i].uvSetName']`
        # `MFnMesh.getAssociatedUVSetTextures()` is able to get all the
        # textures per UV set, but I found no way to do the reverse to
        # get the UV sets per texture. The current method of splitting
        # the string is messy and should be upgraded if possible.
        uvLinks = utils.runAndLog(mc.uvLink, query=True, texture=self)
        attributes = []
        for uvLink in uvLinks:
            node, attrs = uvLink.split('.', 1)
            for i, attr in enumerate(attrs.split('.')):
                for j, subattr in enumerate(attr.rstrip(']').split('[')):
                    if not i:
                        if not j:
                            attribute = Attribute(Node(node), subattr)
                        else:
                            attribute = attribute[int(subattr)]
                    else:
                        attribute = attribute[subattr]
            attributes.append(attribute)
        return attributes

    def _findUvChooser(self):
        """Walk backwards along the uvCoord attributes until a uvChooser is found."""
        node = self.api.object
        while node.apiType() != om2.MFn.kUvChooser:
            depNode = om2.MFnDependencyNode(node)
            plug = depNode.findPlug('uvCoord', False)
            if plug.isNull:
                return None

            connections = plug.connectedTo(True, False)
            if not connections:
                return None

            node = connections[0].node()
        return node

    @property
    def _uvLinks(self):
        """WIP Implementation using OpenMaya."""
        # Check if the object is able to receive UV links
        # TODO: Is this the same as `mc.uvLink(isValid=True, texture=self)`?
        if not self.api.dependencyNode.hasAttribute('uvCoord') or self.api.dependencyNode.typeName == 'uvChooser':
            return []

        uvChooser = self._findUvChooser()
        if uvChooser is None:
            return []

        depNode = om2.MFnDependencyNode(uvChooser)
        plug = depNode.findPlug('uvSets', False)
        if plug.isNull or not plug.isArray:
            return []

        # Get actual UV sets
        uvLinkPlugs = []
        for uvSetPlug in map(plug.elementByPhysicalIndex, range(plug.numElements())):
            if uvSetPlug.isNull or not uvSetPlug.isConnected:
                continue
            uvLinkPlugs.extend(uvSetPlug.connectedTo(True, False))

        # Get remaining default UV sets
        # TODO: Is this correct? If so rewrite to bypass the class overhead
        foundNodes = {om2.MObjectHandle(plug.node()).hashCode() for plug in uvLinkPlugs}
        for dagSetMember in self.shadingEngine.attrs['dagSetMembers']:
            for connectedNode in dagSetMember.connections.inputs.nodes:
                # Skip default nodes
                # For example "shaderBallGeomShape1" shows up here
                if connectedNode.default:
                    continue
                if connectedNode.api.handle.hashCode() in foundNodes:
                    continue

                # Find the correct UV set index
                currentUvSet = connectedNode.uvSet
                for attr in connectedNode.attrs['uvSet']:
                    setNameAttr = attr['uvSetName']
                    if setNameAttr.value == currentUvSet:
                        uvLinkPlugs.append(setNameAttr.api.plug)
                        break

        return [Attribute(self, plug) for plug in uvLinkPlugs]

    @property
    def colorSet(self):
        """Get the current color set.

        Equivalent:
            `mc.polyColorSet(self, query=True, currentColorSet=True)[0]`
        """
        if not self.exists or self.api.mesh is None:
            return None
        return ColorSet(self, self.api.mesh.currentColorSetName())

    @colorSet.setter
    def colorSet(self, colorSet):
        """Set a new color set.

        Raises:
            ColorSetNotFoundError
            NodeNotFoundError
        """
        utils.logger.info('Setting %s color set to %s', self, colorSet)
        utils.raiseIfNodeNotFound(self)
        try:
            return utils.runAndLog(mc.polyColorSet, self, currentColorSet=True, colorSet=colorSet)
        except RuntimeError:
            if colorSet not in self.colorSets:
                raise exceptions.ColorSetNotFoundError(self, colorSet)
            raise

    @property
    def colorSets(self):
        """Get a list of color sets for the node.

        Equivalent:
            `mc.polyColorSet(self, query=True, allColorSets=True)`
        """
        if not self.exists or self.api.mesh is None:
            return []
        return [ColorSet(self, colorSet) for colorSet in self.api.mesh.getColorSetNames()]

    @property
    def faces(self):
        """Get a list of faces."""
        return FaceList(self)

    @property
    def scene(self):
        """Get the current scene."""
        return Scene

    @property
    def referenced(self):
        """Get if the node is referenced.

        Equivalent:
            `mc.referenceQuery(self, isNodeReferenced=True)`
        """
        if not self.exists:
            return False
        depNode = self.api.dependencyNode
        if depNode is None:
            return False
        return depNode.isFromReferencedFile

    @property
    def reference(self):
        """Get the associated reference if the node is referenced."""
        return Reference.fromNode(self)

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


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .attributes import Attribute, NodeAttributes
from .face import FaceList
from ..reference import Reference
from ..bounding_box import BoundingBox
from ..color_set import ColorSet
from ..connection import NodeConnectionProxy
from ..namespace import Namespace
from ..scene import Scene
from ..uv_set import UVSet
