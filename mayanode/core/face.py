from .. import types
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Type
    from ..type_hints import StrLike


class FaceList(types.MappedLazyList['Face', int, str], types.StrMixin):
    """List all the faces on a mesh."""

    __slots__ = ['_node']

    @property
    def ItemType(self):  # type: () -> Type[Face]
        """Return the object this list contains."""
        return Face

    def __init__(self, node):
        # type: (StrLike) -> None
        """Initialise the data from a node."""
        self._node = Node(node)
        super(FaceList, self).__init__()

    def __str__(self):
        # type: () -> str
        return self.name

    def __bool__(self):
        # type: () -> bool
        mesh = self.node.api.mesh
        if mesh is None:
            return False
        return mesh.numPolygons > 0
    __nonzero__ = __bool__

    def __len__(self):
        # type: () -> int
        mesh = self.node.api.mesh
        if mesh is None:
            return 0
        return mesh.numPolygons

    def __eq__(self, other):
        # type: (Any) -> bool
        if isinstance(other, FaceList):
            return self.node == other.node
        if other == str(self):
            return True
        return super(FaceList, self).__eq__(other)

    @property
    def name(self):
        # type: () -> str
        """Get the name for all faces."""
        return '{}.f[0:{}]'.format(self.node, max(0, self.__len__() - 1))

    @property
    def node(self):
        # type: () -> Node
        """Get the node."""
        return self._node

    def _loadApiObjects(self):
        # type: () -> list[int]
        return list(range(len(self)))

    def _loadListItem(self, apiObject):
        # type: (int) -> Face
        return Face(self.node, apiObject)


class Face(types.StrMixin):
    """Handle a face of a mesh."""

    __all__ = ['_node', '_index']

    def __init__(self, node, index):
        # type: (StrLike, int) -> None
        self._node = Node(node)
        self._index = index

    @classmethod
    def fromNode(cls, node):
        # type: (StrLike) -> FaceList
        """Get a list of faces for a node."""
        return FaceList(node)

    @property
    def name(self):
        # type: () -> str
        """Get the face attribute name."""
        return '{}.f[{}]'.format(self.node, self.index)

    @property
    def node(self):
        # type: () -> Node
        """Get the node."""
        return self._node

    @property
    def index(self):
        # type: () -> int
        """Get the polygon ID / index."""
        return self._index

    @property
    def uvSets(self):
        # type: () -> UVSetCollection
        """Get the UV sets assigned to the face.

        Optimisation:
            From a quick test, the overhead of constructing the classes
            is about 4x slower, with 0.08s vs 0.02s on 40k faces.
            If only the UV set names are needed, then consider using
            `map(mesh.getFaceUVSetNames, range(mesh.numPolygons))`.
        """
        return UVSetCollection(self.node, self.index)


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .node import Node
from .uv_set import UVSetCollection
