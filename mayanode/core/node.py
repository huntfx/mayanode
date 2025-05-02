import math
from uuid import UUID

import maya.api.OpenMaya as om2
import maya.cmds as mc  # type: ignore

from .. import constants, exceptions, types, utils
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from ..type_hints import StrLike


class Ancestors(types.MappedLazyList):
    """Only load the ancestor nodes when needed.

    This is very fast when requesting the first or last ancestor or a
    node. When iterating over every ancestor, the overhead cost of
    wrapping the list in this class is minimal.

    Optimisation:
        If using this to test that the top level node matches something
        then it is quite a bit faster to completely skip this and just
        use `node.longName.startswith('|topLevelNode|')`.
    """

    __slots__ = ['_node', '_ancestors', '_loadedAllAncestors']

    def __init__(self, node):
        # type: (Node) -> None
        self._node = node
        self._ancestors = []  # type: list[om2.MDagPath | None]
        self._loadedAllAncestors = False
        super(Ancestors, self).__init__(None if node.api.dagPath.isValid() else [])

    @property
    def node(self):
        # type: () -> Node
        return self._node

    def __bool__(self):
        # type: () -> bool
        """Determine if there are any ancestors."""
        dagPath = self.node.api.dagPath
        if not dagPath.isValid():
            return False
        return dagPath.length() > 1
    __nonzero__ = __bool__

    def __len__(self):
        # type: () -> int
        """Get the number of ancestors."""
        if self._expectedLength is not None:
            return self._expectedLength

        # Get the DAG path length
        dagPath = self.node.api.dagPath
        if not dagPath.isValid():
            self._loadedAllAncestors = True
            return 0
        ancestorLength = dagPath.length() - 1

        # Populate the data lists
        self._ancestors.extend(None for _ in range(ancestorLength - len(self._ancestors)))
        self._set(None for _ in range(ancestorLength))
        return ancestorLength

    def loadData(self, key=None):
        # type: (int | str | None) -> bool
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
        if not self.node.api.dagPath.isValid():
            return True

        if not self._loadedAllAncestors:
            ancestorLength = self.__len__()

            # Load in all the missing data
            # If a negative index then not all data needs loading
            if not isinstance(key, int) or key < 0:

                previousDagPath = self.node.api.dagPath
                for i, ancestor in enumerate(self._ancestors):
                    if ancestor is None:
                        self._ancestors[i] = previousDagPath = om2.MDagPath(previousDagPath).pop()
                    else:
                        previousDagPath = ancestor

                self._loadedAllAncestors = True

            # Load a single positive index
            elif 0 <= key < ancestorLength and self._ancestors[key] is None:

                # Find the closest child DAG path
                dagPath = None
                if key:
                    i = key - 1
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
                self._ancestors[key] = dagPath.pop(key - dagOffset)

        # Get the requested indexes
        indexes = []  # type: list[int]
        if isinstance(key, int):
            # Ignore any index error here as it's only loading the data
            try:
                if self._data[key] is None:
                    indexes = [key]
            except IndexError:
                pass
        else:
            indexes.extend(i for i, item in enumerate(self._data) if item is None)

        # Map nodes to indexes
        for index in indexes:
            self._setitem(index, Node(self._ancestors[index]))

        return not isinstance(key, int)


class _ApiData(object):
    """Hold the OpenMaya API objects for a node."""

    __slots__ = ['_handle', '_instanceNumber',
                 '_dagPaths', '_dependencyNode', '_dagNode', '_set',
                 '_transform', '_hasGeometry', '_reference', '_camera']

    def __init__(self, mObject, instanceNumber=-1):
        # type: (om2.MObject, int) -> None
        if mObject.isNull():
            raise exceptions.NullMObjectError

        self._instanceNumber = instanceNumber

        # The performance of constructing classes here is negligible
        self._handle = om2.MObjectHandle(mObject)
        self._dependencyNode = om2.MFnDependencyNode(mObject)

        self._transform = None  # type: om2.MFnTransform | None
        self._hasGeometry = None  # type: bool | None
        self._reference = None  # type: om2.MFnReference | None
        self._dagNode = None  # type: om2.MFnDagNode | None
        self._dagPaths = None  # type: list[om2.MDagPath] | None
        self._set = None  # type: om2.MFnSet | None
        self._camera = None  # type: om2.MFnCamera | None

    def __bool__(self):
        # type: () -> bool
        """Determine if the node is valid."""
        return self.handle.isValid()
    __nonzero__ = __bool__

    def __eq__(self, other):
        # type: (Any) -> bool
        if isinstance(other, _ApiData):
            if self.handle == other.handle:
                return self.dagPath == other.dagPath
        return False

    def __hash__(self):
        # type: () -> int
        dagPath = self.dagPath
        return self.handle.hashCode() + dagPath.instanceNumber() if dagPath.isValid() else 0

    @classmethod
    def fromName(cls, name, instanceNumber=-1):
        # type: (str, int) -> _ApiData
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
        new = cls(mobject, instanceNumber=instanceNumber)
        if mobject.hasFn(om2.MFn.kDagNode):
            new._dagPaths = [selection.getDagPath(0)] + [None] * instanceNumber
        else:
            new._dagPaths = []
        return new

    @classmethod
    def fromDagPath(cls, dagPath):
        # type: (om2.MDagPath) -> _ApiData
        # pylint: disable=protected-access
        """Get API data from an `MDagPath`."""
        instanceNumber = dagPath.instanceNumber()
        new = cls(dagPath.node(), instanceNumber=instanceNumber)
        new._dagPaths = [None] * instanceNumber + [dagPath]
        return new

    @classmethod
    def fromHandle(cls, handle, instanceNumber=-1):
        # type: (om2.MObjectHandle, int) -> _ApiData
        # pylint: disable=protected-access
        """Get API data from an `MObjectHandle`."""
        new = cls(handle.object(), instanceNumber=instanceNumber)
        new._handle = handle
        return new

    @classmethod
    def fromReference(cls, reference):
        # type: (om2.MFnReference) -> _ApiData
        # pylint: disable=protected-access
        """Get API data from an `MFnReference`."""
        new = cls(reference.object())
        new._reference = reference
        return new

    def copy(self, instanceNumber=-1):
        # type: (int) -> _ApiData
        # pylint: disable=protected-access
        """Create a new copy of the object."""
        new = type(self)(self.object, instanceNumber)
        new._handle = self._handle
        new._dependencyNode = self._dependencyNode
        new._dagNode = self._dagNode
        new._dagPaths = self._dagPaths
        new._hasGeometry = self._hasGeometry
        new._reference = self._reference
        new._set = self._set
        new._camera = self._camera
        return new

    @property
    def object(self):
        # type: () -> om2.MObject
        """Get the `MObject`.
        It will be null if the node has been deleted, even if it is
        still "alive".

        Notable methods:
            `isNull()`
        """
        return self.handle.object()

    @property
    def handle(self):
        # type: () -> om2.MObjectHandle
        """Get the `MObjectHandle`.

        Notable methods:
            `isValid()`
            `isAlive()`
            `hashCode()`
        """
        return self._handle

    @property
    def dependencyNode(self):
        # type: () -> om2.MFnDependencyNode
        """Get the `MFnDependencyNode`.

        Notable methods:
            `name()`
            `findPlug(attrName, isNetworked)`
        """
        return self._dependencyNode

    @property
    def dagNode(self):
        # type: () -> om2.MFnDagNode | None
        """Get the `MFnDagNode`.

        Notable methods:
            `parentCount()`
            `parent(idx)`
        """
        if self._dagNode is None:
            mobj = self.object

            # Intercept when loading on deleted nodes
            if mobj.isNull():
                return None

            if mobj.hasFn(om2.MFn.kDagNode):
                self._dagNode = om2.MFnDagNode(mobj)
            else:
                self._dagNode = -1

        if self._dagNode == -1:
            return None
        return self._dagNode

    @property
    def dagPath(self):
        # type: () -> om2.MDagPath
        """Get the `MDagPath` object, or None.

        Notable methods:
            `isValid()`
            `fullPathName()`
            `partialPathName()`

        If the class was created with an `MObject`, then the `MDagPath`
        may not be set yet. For now, just get any `MDagPath`, since
        `MObjects` can have multiple and don't specify which to use.
        """
        # Load for the first time
        if self._dagPaths is None or (self._instanceNumber > 0 and self._dagPaths[self._instanceNumber] is None):
            mobj = self.object

            # Intercept when loading on deleted nodes
            if not mobj.isNull() and mobj.hasFn(om2.MFn.kDagNode):
                if self._instanceNumber < 0:
                    self._dagPaths = [om2.MDagPath.getAPathTo(mobj)]
                else:
                    if TYPE_CHECKING:
                        assert self.dagNode is not None
                    self._dagPaths = self.dagNode.getAllPaths()
            else:
                self._dagPaths = []

        if not self._dagPaths:
            return om2.MDagPath()
        return self._dagPaths[self._instanceNumber]

    @property
    def dagPaths(self):
        # type: () -> list[om2.MDagPath]
        """Get all `MDagPath` objects to this node and instances.
        Because instances can be created and deleted, it is recommended
        to run `recalculateDagPaths()` first.
        """
        dagPaths = self._dagPaths
        if dagPaths is None or any(dagPath is None for dagPath in dagPaths):
            dagPaths = self.recalculateDagPaths()

        # Get the correct instance number before populating the paths
        if self.instanceNumber is None:
            return []

        return dagPaths

    def recalculateDagPaths(self):
        # type: () -> list[om2.MDagPath]
        """Recalculate all the `MDagPath` nodes.
        This should only be used when checking for instances, since they
        can be created or deleted at any time.

        Returns:
            The instance number of the current MDagPath.
            If -1 then there is no valid MDagPath.
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
        dagNode = self.dagNode
        if dagNode is None:
            dagPaths = self._dagPaths = []
        else:
            dagPaths = self._dagPaths = dagNode.getAllPaths()
        return dagPaths

    @property
    def instanceNumber(self):
        # type: () -> int | None
        """Get the current instance number."""
        instNum = self._instanceNumber

        if instNum < 0 or self._dagPaths is None or self._dagPaths[instNum] is None:
            self.recalculateDagPaths()

        if instNum == -1:
            return None
        return instNum

    def getTransformObject(self):
        # type: () -> om2.MObject | None
        """Get the transform dag path from a shape node."""
        dagPath = self.dagPath
        if not dagPath.isValid():
            return None
        transform = dagPath.transform()
        if om2.MObjectHandle(transform) == self.handle:
            return None
        return transform

    def getShapeDagPath(self):
        # type: () -> om2.MDagPath
        """Get the shape dag path from a transform node.
        If no shape then it will return the current DAG path.
        """
        dagPath = self.dagPath
        if not dagPath.isValid() or not dagPath.numberOfShapesDirectlyBelow():
            return dagPath

        shapeDagPath = om2.MDagPath(dagPath)
        shapeDagPath.extendToShape()
        return shapeDagPath

    @property
    def hasGeometry(self):
        # type: () -> bool
        """Determine if the object contains geometry.
        If not, then `MFnMesh` commands will fail.
        """
        if self._hasGeometry is None:
            # Intercept when loading on deleted nodes
            if self.object.isNull():
                return False

            dagPath = self.dagPath
            self._hasGeometry = (
                dagPath.isValid()
                and dagPath.hasFn(om2.MFn.kMesh)
                and om2.MItGeometry(dagPath).index() != -1
            )
        return self._hasGeometry

    @property
    def mesh(self):
        # type: () -> om2.MFnMesh | None
        """Get the `MFnMesh`.

        Note that the object has to be generated per call rather than
        being cached, as an existing mesh can become invalidated with
        certain operations such as `polyEditUV`, causing fatal errors
        and crashing Maya.

        Notable methods:
            `numVertices`
            `numEdges`
            `numPolygons`
            `numFaceVertices`
            `currentUVSetName()`
        """
        if self.hasGeometry:
            dagPath = self.getShapeDagPath()
            if dagPath.isValid():
                return om2.MFnMesh(dagPath)
            return om2.MFnMesh(self.object)
        return None

    @property
    def transform(self):
        # type: () -> om2.MFnTransform | None
        """Get the `MFnTransform`

        Notable methods:
            `transformation()`
        """
        if self._transform is None:
            mobj = self.object

            # Intercept when loading on deleted nodes
            if mobj.isNull():
                return None  # TODO: Add test

            # Load the MFnTransform if supported
            if mobj.hasFn(om2.MFn.kTransform):
                self._transform = om2.MFnTransform(mobj)
            else:
                self._transform = -1

        if self._transform == -1:
            return None
        return self._transform

    @property
    def reference(self):
        # type: () -> om2.MFnReference | None
        """Get the `MFnReference`.

        Notable methods:
            nodes()
            associatedNamespace(shortName: bool)
            filename(resolvedName: bool, includePath: bool, includeCopyNumber: bool)
        """
        if self._reference is None:
            mobj = self.object

            # Intercept when loading on deleted nodes
            if mobj.isNull():
                return None  # TODO: Add test

            # Load the MFnReference if supported
            if mobj.hasFn(om2.MFn.kReference):
                self._reference = om2.MFnReference(mobj)
            else:
                self._reference = -1

        if self._reference == -1:
            return None
        return self._reference

    @property
    def set(self):
        # type: () -> om2.MFnSet | None
        """Get the `MFnSet`.

        Notable methods:
            getMembers(flatten: bool)
        """
        if self._set is None:
            mobj = self.object

            # Intercept when loading on deleted nodes
            if mobj.isNull():
                return None  # TODO: Add test

            # Load the MFnSet if supported
            if mobj.hasFn(om2.MFn.kSet):
                self._set = om2.MFnSet(mobj)
            else:
                self._set = -1

        if self._set == -1:
            return None
        return self._set

    @property
    def camera(self):
        # type: () -> om2.MFnCamera | None
        """Get the `MFnCamera`"""
        if self._camera is None:
            # Intercept when loading on deleted nodes
            if self.object.isNull():
                return None  # TODO: Add test

            # Load the MFnTransform if supported
            dagPath = self.getShapeDagPath()
            if dagPath.isValid() and dagPath.hasFn(om2.MFn.kCamera):
                self._camera = om2.MFnCamera(dagPath)
            else:
                self._camera = -1

        if self._camera == -1:
            return None
        return self._camera


class Node(types._NodeType):
    """Pointer to a Maya node.

    OpenMaya code inspired by https://www.toadstorm.com/blog/?p=628.
    Note that when calling `maya.cmds`, if `__str__` raises an error,
    then it will raise `TypeError: Object  is invalid`.
    """

    __slots__ = ['api']

    def __init__(self, name, _instanceNumber=-1):
        # type: (Any, int) -> None
        """Setup the data.

        Parameters:
            name: Name of the node.
            _instanceNumber: MObject instance number.
                This should not be set manually. It only applies when
                loading with an MObject.
            """
        if isinstance(name, Node):
            self.api = name.api.copy(instanceNumber=_instanceNumber)  # type: _ApiData
        elif isinstance(name, om2.MObject):
            self.api = _ApiData(name, instanceNumber=_instanceNumber)
        elif isinstance(name, om2.MDagPath):
            self.api = _ApiData.fromDagPath(name)
        elif isinstance(name, om2.MObjectHandle):
            self.api = _ApiData.fromHandle(name, instanceNumber=_instanceNumber)
        elif isinstance(name, om2.MFnReference):
            self.api = _ApiData.fromReference(name)
        else:
            self.api = _ApiData.fromName(name, instanceNumber=_instanceNumber)

    def __eq__(self, other):
        # type: (Any) -> bool
        """Determine if two nodes are equal.
        Instances are treated as equal, but their hashes are different.

        Examples:
            >>> node = Node('|root|group|name')

            >>> assert node == 'name'  # Short name
            >>> assert node == 'group|name'  # Partial long name
            >>> assert node == '|root|group|name'  # Long name
            >>> assert node != '|group|name'  # Invalid long name

            >>> node = Node('|ns:root|ns:group|ns:name')
            >>> assert node == 'name'  # Namespace not required for short name
            >>> assert node == 'ns:name'
            >>> assert node == 'ns:group|ns:name'
            >>> assert node == ':ns:root|:ns:group|:ns:name'
            >>> assert node != 'group|name'
        """
        if isinstance(other, Node):
            return self.api.handle == other.api.handle
        other = str(other).rstrip('|')
        if not other:
            return False

        isLong = '|' in other
        isNamespace = ':' in other
        hasNamespace = self.api.dependencyNode.namespace

        # Use the Maya API when namespaces + long names are involved
        # It's a little slower than string operations
        if isLong and (isNamespace or hasNamespace):
            selection = om2.MSelectionList()
            try:
                selection.add(other)
            except RuntimeError:
                return False
            return om2.MObjectHandle(selection.getDependNode(0)) == self.api.handle

        # Comparing against a long name
        if isLong:
            # Matching `mc.ls` behaviour
            # It only works with `||` and not `|||` so presumably it does this
            other = other.replace('||', '|')

            if other[0] == '|':
                return self.longName == other
            return self.longName.endswith(other)

        partialName = self.name.rsplit('|', 1)[-1]
        if isNamespace:
            if other[0] == ':':
                return ':' + partialName == other
            return partialName == other
        return partialName.rsplit(':', 1)[-1] == other

    def __hash__(self):
        # type: () -> int
        return hash(self.api)

    @classmethod
    def ls(cls, *args, **kwargs):
        # type: (*Any, **Any) -> list[Node]
        """Shortcut to search the scene.

        This will use the API when possible.
        It will return the exact same results as `mc.ls`, but not
        necessarily in the same order.
        """
        useApi = kwargs.pop('_api', None)

        result = []
        sl = None
        if useApi in (None, True):
            ls = utils.Ls(*args, **kwargs)
            sl = ls()
            if sl is None and useApi:
                raise RuntimeError('failed to get nodes matching parameters: {} {}'.format(args, kwargs))

        if sl is not None:
            for i in range(sl.length()):
                try:
                    result.append(Node(sl.getDagPath(i)))
                except TypeError:
                    result.append(Node(sl.getDependNode(i)))

        # Fallback to standard `mc.ls`
        elif not useApi:
            kwargs['objectsOnly'] = True
            result.extend(map(Node, mc.ls(*args, **kwargs)))

        return result

    @classmethod
    def create(cls, nodeType, **kwargs):
        # type: (str, **Any) -> Node
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
        if nodeType in NodeType.ls('shader'):
            result = mc.shadingNode(nodeType, asShader=True, **kwargs)

        # Create shading engine
        elif nodeType == 'shadingEngine':
            kwargs.setdefault('renderable', True)
            kwargs.setdefault('noSurfaceShader', True)
            kwargs.setdefault('empty', True)
            result = mc.sets(**kwargs)

        # Create other
        else:
            result = mc.createNode(nodeType, **kwargs)

        # Get the top level node in the case multiple were created
        if isinstance(result, (list, tuple)):
            result = result[0]

        return cls(result)

    @property
    def exists(self):
        # type: () -> bool
        """Determine if the node exists.

        Preemptive tests barely add any overhead - 1,000,000 calls takes
        less than a second.
        """
        return self.api.handle.isValid()

    @property
    def uuid(self):
        # type: () -> str
        """Get the node UUID.
        This will always work even when the node is deleted.

        Returns:
            UUID as a string.
        """
        return self.api.dependencyNode.uuid().asString()

    @uuid.setter
    def uuid(self, uuid):
        # type: (str | UUID) -> None
        """Set a new UUID.

        Raises:
            RuntimeError: New name has no legal characters.
            NodeDeletedError
            RenameReadOnlyNodeError
        """
        utils.logger.info('Renaming %r UUID to %r', self, uuid)
        utils.raiseIfNodeNotFound(self)

        if self.referenced or self.default or self.name in constants.STARTUP_CAMERAS:
            raise exceptions.RenameReadOnlyNodeError(self)

        if not isinstance(uuid, UUID):
            try:
                uuid = UUID(uuid)
            except ValueError:
                raise exceptions.InvalidUuidError(uuid)

        mc.rename(self, uuid, uuid=True)

    @property
    def name(self):
        # type: () -> str
        """Get the node name.

        Raises:
            NodeDeletedError

        Returns:
            Node name as a string.
        """
        # While the name may be read after the node has deleted, if
        # `dependencyNode.name()` hasn't been called it will cause a
        # fatal error. Even if it has been called, it loses track of
        # the current node, indicating it is unintended behaviour.
        utils.raiseIfNodeNotFound(self)
        api = self.api

        # Even if the MObject is not valid (ie. the node was deleted),
        # the dagPath may still work so check it first
        dagPath = api.dagPath
        if dagPath.isValid():
            partialName = dagPath.partialPathName()
            if partialName:
                return partialName

        return self.api.dependencyNode.name()

    @name.setter
    def name(self, name):
        # type: (Any) -> None
        """Set a new node name.

        Warnings:
            New name contains invalid characters. Illegal characters were converted to "_".

        Alternatives:
            `self.api.dependencyNode.setName('{}:{}'.format(self.namespace, name)`

        Raises:
            RuntimeError: New name has no legal characters.
            NodeDeletedError
            RenameReadOnlyNodeError
            RenameReferencedNodeError
            RenameLockedNodeError
        """
        name = str(name)
        utils.logger.info('Renaming "%s" to "%s"', self, name)
        utils.raiseIfNodeNotFound(self)

        if self.default or self.name in constants.STARTUP_CAMERAS:
            raise exceptions.RenameReadOnlyNodeError(self)
        if self.referenced:
            raise exceptions.RenameReferencedNodeError(self)
        if self.locked:
            raise exceptions.RenameLockedNodeError(self)

        # Keep namespace if not defined
        if ':' not in name:
            name = '{}:{}'.format(self.namespace, name)
        elif not name.startswith(':'):
            name = ':' + name

        mod = MayaNode.dgModifier  # type: om2.MDGModifier | om2.MDagModifier | None
        if mod is None:
            mod = MayaNode.dagModifier

        if mod is None:
            mc.rename(self, name)
        else:
            Namespace.fromNode(name).create()
            mod.renameNode(self.api.object, name)

    @property
    def longName(self):
        # type: () -> str
        """Get the node long name.

        Raises:
            NodeDeletedError

        Returns:
            Node long name as a string.
        """
        utils.raiseIfNodeNotFound(self)
        dagPath = self.api.dagPath
        if dagPath.isValid():
            longName = dagPath.fullPathName()
            if longName:
                return longName
        return self.name

    @property
    def type(self):
        # type: () -> NodeType
        """Get the node type.

        Alternatives:
            `mc.nodeType(self)`
        """
        utils.raiseIfNodeNotFound(self)
        return NodeType(self.api.dependencyNode.typeName)

    @property
    def attrs(self):
        # type: () -> NodeAttributes
        """Get the attr dict."""
        utils.raiseIfNodeNotFound(self)
        return NodeAttributes(self)

    def select(self, add=None, replace=None):
        # type(bool | None, bool | None) -> None
        """Select the current node.

        Parameters:
            add: If the node should be added to the current selection.
                Defaults to False if `replace` not set.
            replace: If the node should replace the current selection.
                Defaults to True if `add` not set.

        TODO:
            Tests
        """
        if add is None and replace is None:
            add = False
            replace = True
        elif add is None:
            add = not replace
        elif replace is None:
            replace = not add
        kwargs = {'add': add, 'replace': replace}
        mc.select(self, noExpand=True, **kwargs)

    def deselect(self):
        # type: () -> None
        """Deselect the current node."""
        mc.select(self, noExpand=True, deselect=True)

    def translate(self, x, y, z):
        # type: (float, float, float) -> None
        """Translate the node with relative coordinates.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        mc.move(x, y, z, self, relative=True)

    @property
    def translation(self):
        # type: () -> types.Coordinate | None
        """Get the translation of the node.

        Equivalent:
            `mc.xform(self, query=True, translation=True, worldSpace=True)`

        Raises:
            NodeDeletedError

        Returns:
            Named coordinate tuple of X, Y, Z.
        """
        utils.raiseIfNodeNotFound(self)
        dagPath = self.api.dagPath
        if not dagPath.isValid():
            return None
        matrix = om2.MTransformationMatrix(dagPath.inclusiveMatrix())
        vector = matrix.translation(om2.MSpace.kWorld)
        return types.Coordinate(vector.x, vector.y, vector.z)

    @translation.setter
    def translation(self, value):
        # type: (tuple[float, float, float]) -> None
        """Set a new node translation.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        mc.xform(self, translation=value, worldSpace=True)

    def rotate(self, x, y, z):
        # type: (float, float, float) -> None
        """Rotate the node with relative coordinates.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        mc.rotate(x, y, z, self, relative=True)

    @property
    def rotation(self):
        # type: () -> types.Coordinate | None
        """Get the rotation of the node.

        Equivalent:
            `mc.xform(self, query=True, rotation=True, worldSpace=True)`

        Raises:
            NodeDeletedError

        Returns:
            Named coordinate tuple of X, Y, Z.
        """
        utils.raiseIfNodeNotFound(self)
        dagPath = self.api.dagPath
        if not dagPath.isValid():
            return None
        matrix = om2.MTransformationMatrix(self.api.dagPath.inclusiveMatrix())
        euler = matrix.rotation()
        return types.Coordinate(math.degrees(euler.x), math.degrees(euler.y), math.degrees(euler.z))

    @rotation.setter
    def rotation(self, value):
        # type: (tuple[float, float, float]) -> None
        """Set a new node rotation.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        mc.xform(self, rotation=value, worldSpace=True)

    def scale(self, x, y, z):
        # type: (float, float, float) -> None
        """Rotate the node with relative coordinates.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        mc.scale(x, y, z, self, relative=True)

    @property
    def scaling(self):
        # type: () -> types.Coordinate | None
        """Get the scale of the node.

        Equivalent:
            `mc.xform(self, query=True, scale=True, worldSpace=True)`

        Raises:
            NodeDeletedError

        Returns:
            Named coordinate tuple of X, Y, Z.
        """
        utils.raiseIfNodeNotFound(self)
        dagPath = self.api.dagPath
        if not dagPath.isValid():
            return None
        matrix = om2.MTransformationMatrix(self.api.dagPath.inclusiveMatrix())
        scale = matrix.scale(om2.MSpace.kWorld)
        return types.Coordinate(*scale)

    @scaling.setter
    def scaling(self, value):
        # type: (tuple[float, float, float]) -> None
        """Set a new node scale.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        mc.xform(self, scale=value, worldSpace=True)

    @property
    def matrix(self):
        # type: () -> types.Matrix4D | None
        """Get the matrix of the node.

        Equivalent:
            `mc.xform(self, query=True, matrix=True, worldSpace=True)`
        """
        utils.raiseIfNodeNotFound(self)
        dagPath = self.api.dagPath
        if not dagPath.isValid():
            return None
        return types.Matrix4D(self.api.dagPath.inclusiveMatrix())

    @matrix.setter
    def matrix(self, matrix):
        """Set a new node matrix."""
        mc.xform(self, matrix=matrix, worldSpace=True)

    @property
    def namespace(self):
        # type: () -> Namespace
        """Get the node namespace.

        Raises:
            NodeDeletedError
            RuntimeError: Cannot rename a read only node.
        """
        utils.raiseIfNodeNotFound(self)
        return Namespace.fromNode(self)

    @namespace.setter
    def namespace(self, namespace):
        # type: (str) -> None
        """Set a new namespace.
        It will be created if it doesn't exist. Any illegal characters
        will be automatically converted to underscores.

        Raises:
            NodeDeletedError

        TODO:
            Test giving a namespace object
        """
        utils.raiseIfNodeNotFound(self)
        if not namespace or namespace == ':':
            newName = self.name.rsplit(':', 1)[-1]
            utils.logger.info('Setting "%s" namespace to ":"', newName)
            mc.rename(self.name, ':' + newName)

        else:
            utils.logger.info('Setting "%s" namespace to "%s"', self, namespace)
            namespaceObj = Namespace(namespace)
            if not namespaceObj.exists:
                namespaceObj.create()
            stripped = self.name.rsplit('|', 1)[-1].split(':', 1)[-1]
            mc.rename(self.name, namespaceObj + ':' + stripped)

    @property
    def plugin(self):
        # type: () -> Plugin | None
        """Get the plugin this node is from."""
        nodeClass = om2.MNodeClass(self.api.dependencyNode.typeId)
        return Plugin.fromPath(nodeClass.pluginName)

    @property
    def parents(self):
        # type: () -> list[Node]
        """Get the node parents."""
        if self.api.dagNode is None:
            return []

        result = []
        for parent in map(self.api.dagNode.parent, range(self.api.dagNode.parentCount())):
            if om2.MObjectHandle(parent) == utils.getWorldHandle():
                continue
            result.append(Node(parent))
        return result

    @property
    def parent(self):
        # type: () -> Node | None
        """Get the node parent."""
        if not self.exists:
            return None
        dagPath = self.api.dagPath
        if not dagPath.isValid():
            return None

        parentDagPath = om2.MDagPath(dagPath).pop()
        if parentDagPath == utils.getWorldDagPath():
            return None
        return Node(parentDagPath)

    @parent.setter
    def parent(self, parent):
        # type: (StrLike) -> None
        """Set a new node parent.
        Note that Maya will error if setting the parent to the current parent.

        Warnings:
            "{node}" is already a child of "{parent}"

        Raises:
            NodeDeletedError
            NodeNotFoundError
        """
        utils.raiseIfNodeNotFound(self)
        if self.api.dagNode is None:
            raise exceptions.NotADagNodeError(self)

        targetMObj = None
        dagModifier = MayaNode.dagModifier
        if dagModifier is not None:
            targetMObj = utils.toMObject(parent)

        if targetMObj is None:
            try:
                if parent:
                    mc.parent(self, parent)
                else:
                    mc.parent(self, world=True)
            except RuntimeError as e:
                if str(e) == 'Maya command error':
                    utils.logger.warning('"%s" is already a child of "%s"', self, parent or 'world')
                    return
                raise
            except ValueError:
                if parent:
                    raise exceptions.NodeNotFoundError(parent)
                raise

        else:
            if TYPE_CHECKING: assert dagModifier is not None
            dagModifier.reparentNode(self.api.object, om2.MObject.kNullObj)

    @property
    def children(self):
        # type: () -> list[Node]
        """Get all node children.

        TODO:
            Use `MFnDagNode.hasChild` for `__contains__`.
        """
        if not self.exists or self.api.dagNode is None:
            return []

        dagNode = self.api.dagNode
        children = []
        for child in map(dagNode.child, range(dagNode.childCount())):

            # Get the correct instance if required
            if om2.MFnDagNode(child).isInstanced():
                for dagPath in om2.MDagPath.getAllPathsTo(child):
                    instNum = dagPath.instanceNumber()
                    if dagPath.pop().node() == self.api.object:
                        children.append(Node(child, _instanceNumber=instNum))

            else:
                children.append(Node(child))

        return children

    @property
    def descendents(self):
        # type: () -> list[Node]
        """Get all node descendents.
        Instances are deduplicated so this only returns unique nodes.

        Equivalent:
            `mc.listRelatives(self, allDescendents=True)`
        """
        if not self.exists or not self.api.dagPath.isValid():
            return []

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
                result.append(Node(handle))

            else:
                result.append(Node(item))
        return result

    @property
    def ancestors(self):
        # type: () -> Ancestors
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
        # type: () -> NodeConnectionProxy
        """Get the node connections as plugs."""
        return NodeConnectionProxy(self)

    @property
    def shape(self):
        # type: () -> Node | None
        """Get the shape node.

        Equivalent:
            `mc.listRelatives(self, shapes=True)[0]`
        """
        if not self.exists:
            return None

        api = self.api
        shapeDagPath = api.getShapeDagPath()
        if shapeDagPath == api.dagPath:
            return None
        return Node(shapeDagPath)

    @property
    def transform(self):
        # type: () -> Node | None
        """Get the transform node.

        Equivalent:
            `mc.listRelatives(self, parent=True)[0]`
        """
        if not self.exists:
            return None

        transform = self.api.getTransformObject()
        if transform is None:
            return None
        return Node(transform)

    @property
    def keyframes(self):
        # type: () -> NodeKeyframes
        """Get the keyframes on the node."""
        return NodeKeyframes(self)

    @keyframes.deleter
    def keyframes(self):
        # type: () -> None
        """Delete all keyframes on the node."""
        NodeKeyframes(self).delete()

    def instance(self, **kwargs):
        # type: (**Any) -> Node
        """Create an instance of the object.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        inst = mc.instance(self, **kwargs)[0]
        return Node(inst)

    @property
    def instanced(self):
        # type: () -> bool
        """Return if the node is instanced."""
        if not self.exists:
            return False
        dagNode = self.api.dagNode
        return dagNode is not None and dagNode.isInstanced()

    @property
    def instances(self):
        # type: () -> list[Node]
        """Get all the node instances including this."""
        if not self.exists:
            return []
        if not self.instanced:
            return [self]

        instanceNumber = self.instanceNumber
        return [self if instanceNumber == i else Node(self, _instanceNumber=i)
                for i, dagPath in enumerate(self.api.dagPaths) if dagPath.isValid()]

    @property
    def instanceNumber(self):
        # type: () -> int | None
        """Get the index of the current index."""
        self.api.recalculateDagPaths()
        return self.api.instanceNumber

    def duplicate(self, **kwargs):
        # type: (**Any) -> Node
        """Duplicate the node."""
        kwargs['returnRootsOnly'] = True
        return Node(mc.duplicate(self, **kwargs)[0])

    @property
    def intermediate(self):
        # type: () -> bool
        """Return if the node is intermediate."""
        if not self.exists or self.api.dagNode is None:
            return False
        return self.api.dagNode.isIntermediateObject

    @property
    def default(self):
        # type: () -> bool
        """Return if the node is default."""
        utils.raiseIfNodeNotFound(self)
        return self.api.dependencyNode.isDefaultNode

    @property
    def shadingGroups(self):
        # type: () -> list[Node]
        """Get all the shading groups assigned to this node.

        Equivalent:
            `mc.listConnections(self, type='shadingEngine')`
        """
        return [Node(sg) for sg in utils.iterShadingGroups(self.api.object)]

    @property
    def shadingGroup(self):
        # type: () -> Node | None
        """Get the shading group assigned to the node."""
        dagPath = self.api.dagPath
        if dagPath.isValid():
            sg = utils.getShadingGroup(dagPath)
        else:
            sg = utils.getShadingGroup(self.api.object)
        if sg is None:
            return None
        return Node(sg)

    @shadingGroup.setter
    def shadingGroup(self, shadingEngine):
        # type: (str | Node) -> None
        """Set a new shading group on the current object instance.

        Warnings:
            No objects specified that can have connections.

        Raises:
            NodeDeletedError
        """
        if shadingEngine is None:
            shadingEngine = 'initialShadingGroup'
        utils.logger.info('Setting %s shader to %s', self, shadingEngine)
        utils.raiseIfNodeNotFound(self)
        mc.sets(self, edit=True, forceElement=shadingEngine)

    @property
    def _material(self):
        # type: () -> Node | None
        """Get the default material assigned to the node.
        Note that materials are usually assigned to meshes.

        TODO:
            Finish WIP implementation
            Test different node types
        """
        shadingGroup = self.shadingGroup
        if shadingGroup is None:
            return None

        plug = shadingGroup.api.dependencyNode.findPlug('surfaceShader', False)
        connections = plug.connectedTo(True, False)
        if not connections:
            return None
        return Node(connections[0].node())

    @property
    def _texture(self):
        # type: () -> Node | None
        """Get the default texture assigned to the node.

        TODO:
            Finish WIP implementation
            Test different node types
        """
        material = self._material
        if material is None:
            return None

        plug = material.api.dependencyNode.findPlug('color', False)
        connections = plug.connectedTo(True, False)
        if not connections:
            return None
        return Node(connections[0].node())

    @property
    def visible(self):
        # type: () -> bool
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
        # type: () -> None
        """Delete the node.

        Raises:
            NodeDeletedError
        """
        utils.raiseIfNodeNotFound(self)
        utils.logger.info('Deleting node: %s', self)
        mc.delete(self)

    @property
    def locked(self):
        # type: () -> bool
        """Determine if the node is locked.

        Alternatives:
            `mc.lockNode(self, query=True, lock=True)[0]`
        """
        utils.raiseIfNodeNotFound(self)
        return self.api.dependencyNode.isLocked

    @locked.setter
    def locked(self, locked):
        # type: (bool) -> None
        """Set the locked state of the node.

        Raises:
            NodeDeletedError

        Alternatives:
            `mc.lockNode(self, lock=locked)`
        """
        if locked:
            self.lock()
        else:
            self.unlock()

    def lock(self):
        # type: () -> None
        """Lock the node.

        Raises:
            NodeDeletedError

        Alternatives:
            `mc.lockNode(self, lock=True)`
        """
        utils.raiseIfNodeNotFound(self)
        self.api.dependencyNode.isLocked = True

    def unlock(self):
        # type: () -> None
        """Unlock the node.

        Raises:
            NodeDeletedError

        Alternatives:
            `mc.lockNode(self, lock=False)`
        """
        utils.raiseIfNodeNotFound(self)
        self.api.dependencyNode.isLocked = False

    @property
    def uvSet(self):
        # type: () -> UVSet | None
        """Get the current UV set.

        Equivalent:
            `mc.polyUVSet(self, query=True, currentUVSet=True)[0]`
        """
        if not self.exists or self.api.mesh is None:
            return None
        return UVSet(self, self.api.mesh.currentUVSetName())

    @uvSet.setter
    def uvSet(self, uvSet):
        # type: (str | UVSet) -> None
        """Set the current UV set.
        This will be skipped if the requested UV set is the current one.

        Raises:
            UVSetNotFoundError
            NodeNotFoundError
        """
        utils.raiseIfNodeNotFound(self)
        uvSet = str(uvSet)

        # Checks
        mesh = self.api.mesh
        if mesh is None:
            raise exceptions.UVSetNotFoundError(self, uvSet)
        currentUVSet = mesh.currentUVSetName()
        if uvSet == currentUVSet:
            return

        utils.logger.info('Setting %s UV set to "%s" (was "%s")', self, uvSet, currentUVSet)

        # Validation
        if uvSet not in mesh.getUVSetNames():
            raise exceptions.UVSetNotFoundError(self, uvSet)

        # Set UV set
        dgModifier = MayaNode.dgModifier
        if dgModifier is None:
            mc.polyUVSet(self, currentUVSet=True, uvSet=uvSet)
        else:
            mesh.setCurrentUVSetName(uvSet, dgModifier)

    @property
    def uvSets(self):
        # type: () -> UVSetCollection
        """Get a list of UV sets for the node.

        Equivalent:
            `mc.polyUVSet(self, query=True, allUVSets=True)`
        """
        return UVSetCollection(self)

    @property
    def uvLinks(self):
        # type: () -> list[Attribute]
        """Get any UV links pointing to the current node.

        TODO:
            Tests
            Return as `UvLink` object
        """
        if not self.exists:
            return []

        # Check if the object is able to receive UV links
        if not mc.uvLink(isValid=True, texture=self):
            return []

        # Get the UV links
        # The returned list is like `['ns:node.uvSet[i].uvSetName']`
        # `MFnMesh.getAssociatedUVSetTextures()` is able to get all the
        # textures per UV set, but I found no way to do the reverse to
        # get the UV sets per texture. The current method of splitting
        # the string is messy and should be upgraded if possible.
        uvLinks = mc.uvLink(query=True, texture=self)
        attributes = []
        for uvLink in uvLinks:
            node, attrs = uvLink.split('.', 1)
            for i, attr in enumerate(attrs.split('.')):
                for j, subattr in enumerate(attr.rstrip(']').split('[')):
                    if not i:
                        if not j:
                            attribute = Attribute(Node(node), subattr)
                        else:
                            attribute = attribute.children[int(subattr)]
                    else:
                        attribute = attribute.children[subattr]
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
        # type: () -> list[Attribute]
        """WIP Implementation using OpenMaya.
        This is an attempt to understand what's going on under the hood
        as there's not a lot of information.
        """
        # pylint: disable=code-unreachable
        sg = _getShadingGroup(self.api.object, self.api.dagPath)
        if sg is None:
            return []

        result = []

        # Iterate over every connected member
        # This is slightly slower than using maya.cmds
        plug = om2.MFnDependencyNode(sg).findPlug('dagSetMembers', False)
        for member in map(plug.elementByPhysicalIndex, range(plug.numElements())):
            for connectedPlug in member.connectedTo(True, True):
                node = connectedPlug.node()

                depNode = om2.MFnDependencyNode(node)
                if depNode.isDefaultNode:
                    continue

                mesh = om2.MFnMesh(node)
                for physicalIndex, uvSetName in enumerate(mesh.getUVSetNames()):
                    textures = mesh.getAssociatedUVSetTextures(uvSetName)
                    if self.api.object not in textures:
                        continue

                    plugSets = depNode.findPlug('uvSet', False)
                    plugSet = plugSets.elementByPhysicalIndex(physicalIndex)
                    plugName = plugSet.child(0)
                    result.append(Attribute(Node(node), plugName))
        return result

        # Slower version of the above using the available methods
        result = []
        for dagSetMember in self.shadingGroup.attrs['dagSetMembers'].children:
            for connectedNode in dagSetMember.connections.source.nodes:
                if connectedNode.default:
                    continue
                for uvSet in connectedNode.uvSets:
                    if self in uvSet.textures:
                        result.append(uvSet.attr)
        return result

        # Faster way of walking through the connections from uvChoosers
        # However this ignores any "default" links

        # This might be the same as `mc.uvLink(isValid=True, texture=self)`?
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

        # TODO: Get remaining default UV sets

        return [Attribute(self, plug) for plug in uvLinkPlugs]

    @property
    def colorSet(self):
        # type: () -> ColorSet | None
        """Get the current color set.

        Equivalent:
            `mc.polyColorSet(self, query=True, currentColorSet=True)[0]`
        """
        if not self.exists or self.api.mesh is None:
            return None
        return ColorSet(self, self.api.mesh.currentColorSetName())

    @colorSet.setter
    def colorSet(self, colorSet):
        # type: (str | ColorSet) -> None
        """Set a new color set.

        Raises:
            ColorSetNotFoundError
            NodeNotFoundError

        TODO:
            Test using a ColourSet instance
        """
        utils.logger.info('Setting %s color set to %s', self, colorSet)
        utils.raiseIfNodeNotFound(self)
        try:
            return mc.polyColorSet(self, currentColorSet=True, colorSet=colorSet)
        except RuntimeError:
            if colorSet not in self.colorSets:
                raise exceptions.ColorSetNotFoundError(self, colorSet)
            raise

    @property
    def colorSets(self):
        # type: () -> list[ColorSet]
        """Get a list of color sets for the node.

        Equivalent:
            `mc.polyColorSet(self, query=True, allColorSets=True)`
        """
        if not self.exists or self.api.mesh is None:
            return []
        return [ColorSet(self, colorSet) for colorSet in self.api.mesh.getColorSetNames()]

    @property
    def faces(self):
        # type: () -> FaceList
        """Get a list of faces."""
        return FaceList(self)

    @property
    def constructionHistory(self):
        # type() -> ConstructionHistory
        """Get the construction history of the node."""
        return ConstructionHistory(self)

    @property
    def scene(self):
        # type: () -> _Scene
        """Get the current scene."""
        return Scene

    @property
    def referenced(self):
        # type: () -> bool
        """Get if the node is referenced.

        Equivalent:
            `mc.referenceQuery(self, isNodeReferenced=True)`
        """
        if not self.exists:
            return False
        return self.api.dependencyNode.isFromReferencedFile

    @property
    def reference(self):
        # type: () -> Reference | None
        """Get the associated reference if the node is referenced.

        Equivalent:
            `mc.referenceQuery(self, referenceNode=True)`
        """
        if not self.referenced:
            return None
        depNodeIt = om2.MItDependencyNodes(om2.MFn.kReference)
        for _ in depNodeIt:
            refNode = depNodeIt.thisNode()
            fnRefNode = om2.MFnReference(refNode)
            if fnRefNode.containsNodeExactly(self.api.object):
                return Reference(fnRefNode)
        return None

    @property
    def camera(self):
        # type: () -> Camera | None
        """Get the camera class if the current node is a camera."""
        dagPath = self.api.getShapeDagPath()
        if dagPath.hasFn(om2.MFn.kCamera):
            return Camera(self, _dagPath=dagPath)
        return None

    @property
    def boundingBox(self):
        # type: () -> BoundingBox
        """Get the bounding box of the node.

        Raises:
            NoBoundingBoxError: "{node}" has no bounding box
        """
        boundingBox = BoundingBox(self)

        # Raise an error for the original mc.exactWorldBoundingBox result
        if boundingBox in ((0, 0, 0, 0, 0, 0), (1e+20, 1e+20, 1e+20, -1e+20, -1e+20, -1e+20)):
            raise exceptions.NoBoundingBoxError(self)

        return boundingBox

    @property
    def texelDensity(self):
        # type: () -> float
        """Get the texel density value for the current UV set.
        Multiply the result to get it for a specific map size.

        Equivalent:
            `texGetTexelDensity(1)`
        """
        return utils.calculateTexelDensity(self.name + '.f[*]')

    @texelDensity.setter
    def texelDensity(self, density):
        # type: (float) -> None
        """Set the texel density value for the current UV set.

        The map size used is 1, so divide the density by the map size if
        required. For example, to set a density of 1024 for map size of
        4096, the density should be set to 0.25.

        Equivalent:
            `texSetTexelDensity(density, 1)`

        Raises:
            ZeroTexelDensityError: If texel density is zero.
        """
        utils.logger.info('Setting texel density of %s to %s', self, density)
        utils.setTexelDensity(self.name + '.f[*]', density)

    @property
    def members(self):
        # type: () -> list[Node]
        """Get the members of the set if the object is a set.
        In the case of instanced shapes, the correct instance will be
        returned.
        """
        mfnSet = self.api.set
        if mfnSet is None:
            return []
        members = mfnSet.getMembers(False)
        result = []
        for i in range(members.length()):
            depNode = members.getDependNode(i)
            if depNode.hasFn(om2.MFn.kDagNode):
                result.append(Node(members.getDagPath(i)))
            else:
                result.append(Node(depNode))
        return result


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .attribute import Attribute, NodeAttributes
from .construction_history import ConstructionHistory
from .bounding_box import BoundingBox
from .camera import Camera
from .color_set import ColorSet
from .connection import NodeConnectionProxy
from .face import FaceList
from .keyframes import NodeKeyframes
from .mayanode import MayaNode
from .namespace import Namespace
from .node_type import NodeType
from .plugin import Plugin
from .reference import Reference
from .scene import Scene, _Scene
from .uv_set import UVSet, UVSetCollection
