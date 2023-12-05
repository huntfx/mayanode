import maya.api.OpenMaya as om2
import maya.cmds as mc

from .attributes import NodeAttributes
from ..bounding_box import BoundingBox
from .. import exceptions, types, utils


class _Flags:
    """Flags for the Node class to query.

    LoadedInstances: Determine if all the DAG paths been loaded.
        This is slower than just getting one DAG path, so it's lazily
        loaded when needed. Tests were done to determine which method
        is fastest.

        Given the OpenMaya selection:
            >>> selection = om2.MSelectionList()
            >>> selection.add(node)
        By default the DAG path is read like this:
            >>> selection.getDagPath(0)
            <OpenMaya.MDagPath object at *>
        To get multiple, these methods can be used:
            >>> om2.MFnDagNode(selection.getDagPath(0)).getAllPaths()[0]
            [<OpenMaya.MDagPath object at *>, <OpenMaya.MDagPath object at *>]
            >>> mobj = selection.getDependNode(0)
            >>> om2.MFnDagNode(mobj).getAllPaths()
            [<OpenMaya.MDagPath object at *>, <OpenMaya.MDagPath object at *>]
            >>> om2.MDagPath.getAllPathsTo(mobj)
            [<OpenMaya.MDagPath object at *>, <OpenMaya.MDagPath object at *>]
        These are the ordered speed results from a large scene:
            selection.getDagPath(0): 0.6 seconds
            om2.MDagPath.getAllPathsTo(mobj): 3.8 seconds
            om2.MFnDagNode(mobj).getAllPaths(): 4.9 seconds
            om2.MFnDagNode(dagPath).getAllPaths(): 5.9 seconds
    """

    LoadedInstances = 0x1


class Node(utils.StrMixin):
    """Pointer to a Maya node.
    OpenMaya code adapted from https://www.toadstorm.com/blog/?p=628.
    """

    __slots__ = ['_mObject', '_dagPaths', '_dependencyNode', '_attrs', '_flags']

    NODE_TYPES = {
        'shader': set(mc.listNodeTypes('shader')),
    }

    def __init__(self, name):
        """Get the handles to the API objects."""
        if isinstance(name, Node):
            self._mObject = name._mObject
            self._dependencyNode = name._dependencyNode
            self._dagPaths = name._dagPaths
            self._flags = name._flags

        else:
            selection = om2.MSelectionList()
            try:
                selection.add(name)
            except Exception as e:
                if 'kInvalidParameter' in e.message:
                    raise exceptions.NodeNotFoundError(name)
                raise
            else:
                self._flags = 0
                self._mObject = selection.getDependNode(0)
                self._dependencyNode = om2.MFnDependencyNode(self._mObject)
                try:
                    self._dagPaths = [selection.getDagPath(0)]
                except TypeError:
                    self._dagPaths = []

        self._attrs = NodeAttributes(self)

    def __new__(cls, name):
        """Create a new class instance, or attribute proxy if an attribute was given."""
        if not isinstance(name, cls) and name and '.' in name:
            node, attr = name.split('.', 1)
            return cls(node).attrs[attr]
        return super(Node, cls).__new__(cls, name)

    def __add__(self, attr):
        """Get a new object or attribute."""
        if attr[0] == '.':
            return self.attrs[attr[1:]]
        return type(self)(str(self) + attr)

    def __eq__(self, other):
        if isinstance(other, Node):
            return self.uuid == other.uuid and self.namespace == other.namespace
        return super(Node, self).__eq__(other)

    def __hash__(self):
        return hash((self.uuid, self.namespace))

    def _ensureDagLoaded(self):
        """Lazily load all DAG paths.
        The instance number is used to make sure they remain in order.
        """
        if self._flags & _Flags.LoadedInstances:
            return
        if self._dagPaths:
            currentInstNum = self._dagPaths[0].instanceNumber()
            self._dagPaths = list(om2.MDagPath.getAllPathsTo(self._mObject))
            if currentInstNum:
                self._dagPaths.insert(0, self._dagPaths.pop(currentInstNum))
        self._flags |= _Flags.LoadedInstances

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
        if self._dagPaths and self._dagPaths[0].isValid():
            return self._dagPaths[0].partialPathName()
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
    def names(self):
        """Get all the node instance names."""
        self._ensureDagLoaded()
        result = [dagPath.partialPathName() for dagPath in self._dagPaths if dagPath.isValid()]
        if result:
            return result
        return [self.name]

    @property
    def longName(self):
        """Get the node long name."""
        if self._dagPaths and self._dagPaths[0].isValid():
            return self._dagPaths[0].fullPathName()
        return self.name

    @property
    def longNames(self):
        """Get all the node instance long names."""
        self._ensureDagLoaded()
        result = [dagPath.fullPathName() for dagPath in self._dagPaths if dagPath.isValid()]
        if result:
            return result
        return [self.longName]

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
        """Get the node parents as a generator."""
        return map(type(self), utils.runAndLog(mc.listRelatives, self, allParents=True, fullPath=True) or [])

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
            return self._dagPaths[0].isInstanced()
        return False

    @property
    def instances(self):
        """Get all the node instances including this."""
        shape = self.shape
        if shape is None:
            return [self]
        else:
            return shape.parents

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
