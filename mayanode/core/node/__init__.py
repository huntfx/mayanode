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


class _ApiData(object):
    """Hold the OpenMaya API objects for a node."""

    __slots__ = ['_object', '_handle', '_instanceNumber', '_transform',
                 '_dagPaths', '_dependencyNode', '_dagNode', '_mesh']

    def __init__(self, mObject, instanceNumber=-1):
        self._object = mObject
        self._handle = None
        self._instanceNumber = instanceNumber
        self._dependencyNode = self._dagNode = self._dagPaths = self._transform = self._mesh = None

    def __eq__(self, other):
        if isinstance(other, _ApiData):
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
            if self.object.hasFn(om2.MFn.kMesh):
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
        result = mc.ls(*args, **kwargs)
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
        return self.api.dependencyNode.uuid().asString()

    @property
    def name(self):
        """Get the node name.
        This will always work even when the node is deleted.

        Returns:
            Node name as a string.
        """
        if self.api.dagPath is not None and self.api.dagPath.isValid():
            return self.api.dagPath.partialPathName()
        return self.api.dependencyNode.name()

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
        """
        utils.raiseIfNodeNotFound(self)
        return self.api.dependencyNode.namespace

    @namespace.setter
    def namespace(self, namespace):
        """Set a new namespace.
        It will be created if it doesn't exist.

        Warnings:
            New name contains invalid characters. Illegal characters were converted to "_".

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        namespace = namespace.strip(':') if namespace else ''
        if namespace and not utils.runAndLog(mc.namespace, exists=namespace):
            utils.runAndLog(mc.namespace, add=namespace)
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
        dagPath = om2.MDagPath(self.api.dagPath).pop()
        if dagPath == _getWorldDagPath():
            return None
        return type(self)(dagPath)

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
        """Get all node ancestors."""
        if not self.exists:
            return []
        parents = self.parents
        ancestors = []

        for parent in parents:
            ancestors.append(parent)
            ancestors.extend(parent.ancestors)

        seen = set()
        return [ancestor for ancestor in ancestors
                if not (ancestor in seen or seen.add(ancestor))]

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
    def shadingEngine(self):
        """Get the shading engine assigned to the node.
        Note that this will be assigned to a shape.
        """
        if not self.exists:
            return None
        shapes = utils.runAndLog(mc.ls, self, dag=True, shapes=True)
        engines = utils.runAndLog(mc.listConnections, shapes, type='shadingEngine')
        return type(self)(engines[0]) if engines else None

    @shadingEngine.setter
    def shadingEngine(self, shadingEngine):
        """Set a new shadingEngine.

        Warnings:
            No objects specified that can have connections.

        Raises:
            NodeDeletedError
        """
        utils.logger.info('Setting %s shader to %s', self, shadingEngine)
        utils.raiseIfNodeNotFound(self)
        utils.runAndLog(mc.sets, self, edit=True, forceElement=shadingEngine)

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

        Raises:
            UVSetNotFoundError
            NodeNotFoundError
        """
        utils.raiseIfNodeNotFound(self)
        if uvSet not in self.uvSets:
            raise exceptions.UVSetNotFoundError(self, uvSet)
        utils.logger.info('Setting %s UV set to %s', self, uvSet)
        return utils.runAndLog(mc.polyUVSet, self, currentUVSet=True, uvSet=uvSet)

    @property
    def uvSets(self):
        """Get a list of UV sets for the node.

        Equivalent:
            `mc.polyUVSet(self, query=True, allUVSets=True)`
        """
        if not self.exists or self.api.mesh is None:
            return None
        return [UVSet(self, uvSet) for uvSet in self.api.mesh.getUVSetNames()]

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
            return None
        return [ColorSet(self, colorSet) for colorSet in self.api.mesh.getColorSetNames()]

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
from .attributes import NodeAttributes
from ..bounding_box import BoundingBox
from ..color_set import ColorSet
from ..connection import NodeConnectionProxy
from ..uv_set import UVSet
