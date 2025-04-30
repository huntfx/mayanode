from .. import types


class FaceList(types.MappedLazyList, types.StrMixin):
    """Hold a list of all the faces on a mesh.

    The data is of the correct size, but lazily populated when needed.

    TODO: Test
    """

    __slots__ = ['_node']

    def __init__(self, node):
        # type: (Node) -> None
        """Initialise the data from a node."""
        self._node = node
        super(FaceList, self).__init__(None for _ in range(self.__len__()))

    def __bool__(self):
        # type: () -> bool
        return not len(self)
    __nonzero__ = __bool__

    def __len__(self):
        # type: () -> int
        mesh = self.node.api.mesh
        if mesh is None:
            return 0
        return mesh.numPolygons

    @property
    def name(self):
        # type: () -> str
        """Get the attribute for all faces.

        TODO: `self.node.attrs['f'][0:len(self)]`
        """
        return '{}.f[0:{}]'.format(self.node, max(0, self.__len__() - 1))

    @property
    def node(self):
        # type: () -> Node
        """Get the node."""
        return self._node

    def _loadData(self, key=None):
        # type: (int | str | None) -> bool
        """Load the `Face` objects when needed."""
        indexes = []
        if isinstance(key, int):
            indexes = [key]
        else:
            indexes = [i for i, item in enumerate(self._data) if item is None]

        for idx in indexes:
            self._data[idx] = Face(self.node, idx)

        return not isinstance(key, int)


class Face(types.StrMixin):
    """Handle a face of a mesh.

    TODO: Test
    TODO: Should this inherit `Attribute`?
    """

    __all__ = ['_node', '_index']

    def __init__(self, node, index):
        # type: (Node, int) -> None
        self._node = node
        self._index = index

    @classmethod
    def fromNode(cls, node):
        # type: (Node) -> list[Face]
        """Get a list of faces for a node."""
        mesh = node.api.mesh
        if mesh is None:
            return []
        return [Face(node, i) for i in range(mesh.numPolygons)]

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
