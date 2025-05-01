import maya.api.OpenMaya as om2
import maya.cmds as mc  # type: ignore

from .. import exceptions, types, utils
from ..type_hints import TYPE_CHECKING, Generic, TypeVar, overload

if TYPE_CHECKING:
    from typing import Any, Iterator
    from ..type_hints import StrLike


T = TypeVar('T')


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
        """
        # TODO: Add tests
        # TODO: `textures.append(texture)` (with `mc.uvLink`)
        # TODO: `textures.remove(texture)` (with `mc.uvLink`)
        # TODO: `textures = [texture]` (with `mc.uvLink`)
        mesh = self.node.api.mesh
        if mesh is None:
            return []
        textures = mesh.getAssociatedUVSetTextures(self.name)
        return [Node(texture) for texture in textures]


class UVSetCollection(object):
    """Store a list of UV sets."""

    __slots__ = ['_node', '_faceIndex', '_apiObjects', '_mappedObjects']

    def __init__(self, node, faceIndex=None):
        # type: (Node, int | None) -> None
        """Store the origin mesh and optionally the index of the mesh face."""
        self._node = node
        self._faceIndex = faceIndex

        self._apiObjects = None  # type: list[str] | None
        self._mappedObjects = []  # type: list[UVSet | None]

    @property
    def node(self):
        # type: () -> Node
        """Get the node."""
        return self._node

    @property
    def faceIndex(self):
        # type: () -> int | None
        """Get the node."""
        return self._faceIndex

    def __repr__(self):
        # type: () -> str
        return repr(self.apiObjects)

    def __str__(self):
        # type: () -> str
        return str(self.apiObjects)

    def __eq__(self, other):
        # type: (Any) -> bool
        if isinstance(other, UVSetCollection):
            return self._node == other._node and self._faceIndex == other._faceIndex
        if isinstance(other, list):
            return self.apiObjects == other
        return False

    def __bool__(self):
        # type: () -> bool
        """Determine if any UV sets are present."""
        if self._apiObjects is not None:
            return bool(self._apiObjects)

        mesh = self.node.api.mesh
        if mesh is None:
            return False
        return mesh.numUVSets > 0
    __nonzero__ = __bool__

    def __len__(self):
        # type: () -> int
        """Get the number of UV sets."""
        if self._apiObjects is not None:
            return len(self._apiObjects)

        mesh = self.node.api.mesh
        if mesh is None:
            return 0
        return mesh.numUVSets

    def __iter__(self):
        # type: () -> Iterator[UVSet]
        """Iterate through each node within the reference."""
        return iter(self._getUVSet(i) for i in range(len(self)))

    def __contains__(self, uvSet):
        # type: (StrLike) -> bool
        """Check if a particular uvSet is in the collection."""
        return str(uvSet) in self.apiObjects

    @overload
    def __getitem__(self, index):
        # type: (int | StrLike) -> UVSet
        pass
    @overload
    def __getitem__(self, index):
        # type: (slice) -> UVSetList[UVSet]
        pass
    def __getitem__(self, index):
        # type: (int | slice | StrLike) -> UVSet | UVSetList[UVSet]
        """Get a node from an index, name or slice."""
        # Get a list of nodes from a slice
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            return UVSetList(self._getUVSet(i) for i in range(start, stop, step))

        # Get the node at an index
        if isinstance(index, int):
            return self._getUVSet(index)

        # Get the node from its name
        for item in self:
            if item == index:
                return item

        raise IndexError(index)

    def __delitem__(self, index):
        # type: (int | slice | StrLike) -> None
        """Delete a UV set using an index, name or slice."""
        result = self.__getitem__(index)
        if isinstance(result, UVSet):
            result.delete()
        else:
            for uvSet in result:
                uvSet.delete()

    @property
    def apiObjects(self):
        """Get the list of UV names."""
        if self._apiObjects is None:
            if self._faceIndex is None:
                self._apiObjects = list(self.node.api.mesh.getUVSetNames())
            else:
                self._apiObjects = list(self.node.api.mesh.getFaceUVSetNames(self._faceIndex))
            self._mappedObjects = [None for _ in self._apiObjects]
        return self._apiObjects

    @apiObjects.deleter
    def apiObjects(self):
        """Refresh the list of UV names."""
        self._apiObjects = None

    def _getUVSet(self, index):
        # type: (int) -> UVSet
        """Get an individual node at an index.
        Creates a mapping if one doesn't exist.
        """
        if self._apiObjects is None:
            uvSet = None
        else:
            uvSet = self._mappedObjects[index]
        if uvSet is None:
            uvSet = UVSet(self.node, self.apiObjects[index])
            self._mappedObjects[index] = uvSet
        return uvSet

    def create(self, name):
        # type: (str) -> UVSet
        """Add a new UV set to the node."""
        uvSetName = mc.polyUVSet(self.node, create=True, uvSet=name)[0]
        self.apiObjects.append(uvSetName)
        uvSet = UVSet(self.node, uvSetName)
        self._mappedObjects.append(uvSet)
        return uvSet

    def refresh(self):
        # type (bool) -> None
        """Refresh all the data."""
        self.apiObjects = None


class UVSetList(list, Generic[T]):
    """Add extra methods to a sublist of UV Sets."""

    def textures(self):
        # type: () -> list[Node]
        """Get a list of texture nodes which are using the UV set.
        If the texture has a 2D texture placement, then the texture and
        not the placement will be returned."""
        result = []
        for uvSet in self:
            result.extend(uvSet.textures)
        return result


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .attribute import Attribute
from .mayanode import MayaNode
from .node import Node
