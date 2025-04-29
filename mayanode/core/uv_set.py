import maya.api.OpenMaya as om2
import maya.cmds as mc  # type: ignore

from .. import exceptions, types, utils


class UVSetList(types.MappedLazyList):
    """Hold multiple UV sets.

    TODO:
        Allow uvSets[:].textures
    """
    __slots__ = ['_node', '_faceIndex', '_uvSetNames']

    def __init__(self, node, faceIndex=None):
        # type: (Node, int | None) -> None
        """Store the origin mesh and optionally the index of the mesh face."""
        self._node = node
        self._faceIndex = faceIndex
        self._uvSetNames = None  # type: list[str] | None
        super(UVSetList, self).__init__()

    def __bool__(self):
        # type: () -> bool
        """Determine if any UV sets are present."""
        if self._uvSetNames is not None:
            return bool(self._uvSetNames)

        mesh = self.node.api.mesh
        if mesh is None:
            return False
        return mesh.numUVSets > 0
    __nonzero__ = __bool__

    def __len__(self):
        # type: () -> int
        """Get the number of UV sets."""
        if self._uvSetNames is not None:
            return super(UVSetList, self).__len__()

        mesh = self.node.api.mesh
        if mesh is None:
            return 0
        return mesh.numUVSets

    def __delitem__(self, item):
        # type: (int | str) -> None
        """Delete a UV set."""
        self.__getitem__(item).delete()

    @property
    def node(self):
        # type: () -> Node
        """Get the node."""
        return self._node

    def loadData(self, key=None):
        # type: (int | str | None) -> bool
        """Load all data or for a specific index."""
        if self._uvSetNames is None:
            if self.node.exists and self.node.api.mesh is not None:
                if self._faceIndex is None:
                    self._uvSetNames = list(self.node.api.mesh.getUVSetNames())
                else:
                    self._uvSetNames = list(self.node.api.mesh.getFaceUVSetNames(self._faceIndex))
            else:
                self._uvSetNames = []
            self._set(None for _ in self._uvSetNames)

        indexes = []  # type: list[int]
        loadedAll = False

        # Load all
        if key is None:
            indexes.extend(i for i, item in enumerate(self._data) if item is None)
            loadedAll = True

        # Load at index
        elif isinstance(key, int):
            # Ignore any index error here as it's only loading the data
            try:
                if self._data[key] is None:
                    indexes = [key]
            except IndexError:
                pass

        # Load all data if the UV set name isn't in the mapping
        elif self._mapping is not None:
            if key not in self._mapping:
                indexes.extend(i for i, item in enumerate(self._data) if item is None)
                loadedAll = True

        # Load specific data if the UV set name was found
        # TODO: Test performance
        elif key in self._uvSetNames:
            idx = self._uvSetNames.index(key)
            if self._data[idx] is None:
                indexes.append(idx)

        for idx in indexes:
            self._setitem(idx, UVSet(self.node, self._uvSetNames[idx]))

        return loadedAll

    def create(self, name):
        # type: (str) -> UVSet
        """Add a new UV set to the node."""
        uvSetName = mc.polyUVSet(self.node, create=True, uvSet=name)[0]
        if self._uvSetNames is not None:
            self._uvSetNames.append(uvSetName)
        uvSet = UVSet(self.node, uvSetName)
        self._append(uvSet)
        return uvSet


class UVSet(types.StrMixin):
    """Handle UV sets."""

    __slots__ = ['_node', '_name']

    def __init__(self, node, name):
        # type: (Node, str) -> None
        self._node = node
        self._name = name

    def __repr__(self):
        # type: () -> str
        return '{}({!r})'.format(type(self).__name__, '{}.{}'.format(self.node, self.name))

    @property
    def name(self):
        # type: () -> str
        """Get the name of the uv set."""
        return self._name

    @name.setter
    def name(self, name):
        # type: (str) -> None
        """Rename a UV set.

        Raises:
            UVSetNotFoundError
            UVSetExistsError
        """
        utils.logger.info("Renaming '%s' UV set '%s' to '%s'", self.node, self.name, name)

        fnMesh = self.node.api.mesh
        if fnMesh is None:
            raise exceptions.UVSetNotFoundError(self.node, self.name)
        if name in fnMesh.getUVSetNames():
            raise exceptions.UVSetExistsError(self.node, self.name)

        dgMod = MayaNode.dgModifier
        if dgMod is None:
            mc.polyUVSet(self.node, rename=True, uvSet=self.name, newUVSet=name)
        else:
            fnMesh.renameUVSet(self.name, name, dgMod)
        self._name = name

    @property
    def node(self):
        # type: () -> Node
        """Get the node."""
        return self._node

    @property
    def attr(self):
        # type: () -> Attribute
        """Get the UV set attribute.

        Raises:
            UVSetNotFoundError

        Returns:
            Attribute('node.uvSet[i].uvSetName')
        """
        physicalIndex = self.physicalIndex
        isValid = lambda uvSet: uvSet.children['uvSetName'].value
        for i, uvSet in enumerate(filter(isValid, self.node.attrs['uvSet'].children)):
            if i == physicalIndex:
                return uvSet.children['uvSetName']
        raise exceptions.UVSetNotFoundError(self.node, self)

    @property
    def physicalIndex(self):
        # type: () -> int
        """Get the physical index of the UV set.

        Technically this is not the "real" internal index, that seems
        to match the logical index even after the UV sets have been
        deleted.

        Raises:
            UVSetNotFoundError
        """
        fnMesh = self.node.api.mesh
        if fnMesh is None:
            raise exceptions.UVSetNotFoundError(self.node, self.name)
        try:
            return fnMesh.getUVSetNames().index(self.name)
        except ValueError:
            raise exceptions.UVSetNotFoundError(self.node, self.name)

    @property
    def logicalIndex(self):
        # type: () -> int
        """Get the logical index of the UV set.

        Raises:
            UVSetNotFoundError
        """
        return self.attr.api.plug.parent().logicalIndex()

    @property
    def exists(self):
        # type: () -> bool
        """Determine if this UV set exists."""
        fnMesh = self.node.api.mesh
        if fnMesh is None:
            return False
        return self.name in fnMesh.getUVSetNames()

    @property
    def current(self):
        # type: () -> bool
        """Determine if this UV set is the current one."""
        fnMesh = self.node.api.mesh
        if fnMesh is None:
            return False
        return self.name == fnMesh.currentUVSetName()

    @current.setter
    def current(self, current):
        # type: (bool) -> None
        """Set this UV set as the current one."""
        if not current:
            raise ValueError('can only set a uv set to current')
        self.node.uvSet = self

    def delete(self):
        # type: () -> None
        """Delete a UV set.

        Raises:
            UVSetNotFoundError(UVSetError): If deleting one that doesn't exist.
            UVSetDeleteDefaultError(UVSetError): If deleting the default UV set.
        """
        utils.logger.info('Deleting UV set: %s.%s', self.node, self.name)

        dgMod = MayaNode.dgModifier
        if dgMod is None:
            try:
                mc.polyUVSet(self.node, delete=True, uvSet=self.name)
            except RuntimeError as e:
                if 'The default uv set cannot be deleted.' in str(e):
                    raise exceptions.UVSetDeleteDefaultError(self.node, self.name)
                if 'Specified uv set does not exist on the polygonal object.' in str(e):
                    raise exceptions.UVSetNotFoundError(self.node, self.name)
                raise

        else:
            fnMesh = self.node.api.mesh
            if fnMesh is None:
                raise exceptions.UVSetNotFoundError(self.node, self.name)
            allSets = fnMesh.getUVSetNames()
            if self.name not in allSets:
                raise exceptions.UVSetNotFoundError(self.node, self.name)
            if self.name == allSets[0]:
                raise exceptions.UVSetDeleteDefaultError(self.node, self.name)

            sl = om2.MSelectionList()
            sl.add(self.node.api.getShapeDagPath())
            fnMesh.deleteUVSet(self.name, dgMod, sl)

    @property
    def textures(self):
        # type: () -> list[Node]
        """Get a list of texture nodes which are using the UV set.
        If the texture has a 2D texture placement, then the texture and
        not the placement will be returned.

        Equivalent:
            `mc.uvLink(query=True, uvSet=self.attr)`

        TODO:
            `textures.append(texture)` (with `mc.uvLink`)
            `textures.remove(texture)` (with `mc.uvLink`)
            `textures = [texture]` (with `mc.uvLink`)
        """
        mesh = self.node.api.mesh
        if mesh is None:
            return []
        textures = mesh.getAssociatedUVSetTextures(self.name)
        return [Node(texture) for texture in textures]


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .attribute import Attribute
from .mayanode import MayaNode
from .node import Node
