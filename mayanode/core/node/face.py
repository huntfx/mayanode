from __future__ import absolute_import

from ... import types, utils


class FaceList(types.LazyList, types.StrMixin):
    """Hold a list of all the faces on a mesh.

    The data is of the correct size, but lazily populated when needed.

    TODO: Test
    """

    __slots__ = ['_node']

    def __init__(self, node):
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
        """Get the attribute for all faces.

        TODO: `self.node.attrs['f'][0:len(self)]`
        """
        return '{}.f[0:{}]'.format(self.node, len(self))

    @property
    def node(self):
        """Get the node."""
        return self._node

    def _loadData(self, index=None):
        """Load the `Face` objects when needed."""
        if index is None:
            indexes = [i for i, item in enumerate(self._data) if item is None]
        else:
            indexes = [index]

        for index in indexes:
            self._data[index] = Face(self.node, index)

    def reload(self):
        """Refresh the data."""
        self._data[:] = [None for _ in range(self.node.api.mesh.numPolygons)]


class Face(utils.StrMixin):
    """Handle a face of a mesh.

    TODO: Test
    TODO: Should this inherit `Attribute`?
    """

    __all__ = ['_node', '_index']

    def __init__(self, node, index):
        self._node = node
        self._index = index

    @classmethod
    def fromNode(cls, node):
        """Get a list of faces for a node."""
        mesh = node.api.mesh
        if mesh is None:
            return []
        return [cls(node, i) for i in range(mesh.numPolygons)]

    @property
    def name(self):
        """Get the face attribute name."""
        return '{}.f[{}]'.format(self.node, self.index)

    @property
    def node(self):
        """Get the node."""
        return self._node

    @property
    def index(self):
        """Get the polygon ID / index."""
        return self._index

    @property
    def uvSets(self):
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
