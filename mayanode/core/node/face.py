from __future__ import absolute_import

from ... import types, utils

if utils.TYPE_CHECKING:
    from typing import List


class FaceList(types.LazyList, types.StrMixin):
    """Hold a list of all the faces on a mesh.

    The data is of the correct size, but lazily populated when needed.

    TODO: Test
    """

    __slots__ = ['_node']

    def __init__(self, node):
        # type: (Node) -> None
        """Initialise the data from a node."""
        self._node = node
        mesh = node.api.mesh
        if mesh is not None:
            numPolygons = mesh.numPolygons
        else:
            numPolygons = 0
        super(FaceList, self).__init__(None for _ in range(numPolygons))

    @property
    def name(self):
        # type: () -> str
        """Get the attribute for all faces.

        TODO: `self.node.attrs['f'][0:len(self)]`
        """
        return '{}.f[0:{}]'.format(self.node, len(self))

    @property
    def node(self):
        # type: () -> Node
        """Get the node."""
        return self._node

    def _loadData(self, index=None):
        # type: (int) -> None
        """Load the `Face` objects when needed."""
        if index is None:
            indexes = [i for i, item in enumerate(self._data) if item is None]
        else:
            indexes = [index]

        for index in indexes:
            self._data[index] = Face(self.node, index)

    def reload(self):
        # type: () -> None
        """Refresh the data."""
        mesh = self.node.api.mesh
        if mesh is not None:
            numPolygons = mesh.numPolygons
        else:
            numPolygons = 0
        self._data[:] = [None for _ in range(numPolygons)]


class Face(utils.StrMixin):
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
        # type: (Node) -> List[Face]
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
        # type: () -> List[UVSet]
        """Get the UV sets assigned to the face.

        Optimisation:
            From a quick test, the overhead of constructing the classes
            is about 4x slower, with 0.08s vs 0.02s on 40k faces.
            If only the UV set names are needed, then consider using
            `map(mesh.getFaceUVSetNames, range(mesh.numPolygons))`.
        """
        mesh = self.node.api.mesh
        if mesh is None:
            return []
        uvSetNames = mesh.getFaceUVSetNames(self.index)
        return [UVSet(self.node, uvSet) for uvSet in uvSetNames]


# Handle circular dependencies
# pylint: disable=wrong-import-position
from ..uv_set import UVSet
from . import Node
