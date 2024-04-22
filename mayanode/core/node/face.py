from __future__ import absolute_import

import maya.cmds as mc  # type: ignore

from ... import exceptions, types, utils

if utils.TYPE_CHECKING:
    from typing import List, Optional, Union


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

    def __len__(self):
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
        # type: (Optional[Union[int, str]]) -> bool
        """Load the `Face` objects when needed."""
        indexes = []
        if isinstance(key, int):
            indexes = [key]
        else:
            indexes = [i for i, item in enumerate(self._data) if item is None]

        for idx in indexes:
            self._data[idx] = Face(self.node, idx)

        return not isinstance(key, int)

    @property
    def texelDensity(self):
        # type: () -> float
        """Get the texel density value from the faces.
        Multiply the result to get it for a specific map size.

        Equivalent:
            `texGetTexelDensity(1)`

        TODO:
            Consider moving this to a UV shell class
                `.uvShells.texelDensity`
                `.uvShells[0].texelTensity`
            Add access for transforms nodes
        """
        return utils.calculateTexelDensity(self.name)

    @texelDensity.setter
    def texelDensity(self, density):
        # type: (float) -> None
        """Scale shells so they match a specific texel density value.

        The map size used is 1, so divide the density by the map size if
        required. For example, to set a density of 1024 for map size of
        4096, the density should be set to 0.25.

        Equivalent:
            `texSetTexelDensity(density, 1)`

        Raises:
            ZeroTexelDensityError: If texel density is zero.
        """
        utils.logger.info('Setting texel density of %s to %s', self, density)
        originalSelection = mc.ls(selection=True)
        mc.select(self.name)   # The `activeUVShells` flag doesn't work if node isn't selected

        for shell in mc.polyEvaluate(self.name, activeUVShells=True):  # [0, 1, 2, ...]
            uvs = mc.polyEvaluate(self.node, uvsInShell=shell)  # [node.map[0:100], ...]
            faces = mc.polyListComponentConversion(uvs, toFace=True, uvs=True)  # [node.f[0:100], ...]
            currentdensity = utils.calculateTexelDensity(faces)
            try:
                scale = density / currentdensity
            except ZeroDivisionError:
                raise exceptions.ZeroTexelDensityError(faces)

            (u1, u2), (v1, v2) = mc.polyEvaluate(uvs, boundingBoxComponent2d=True)
            pU = (u1 + u2) / 2
            pV = (v1 + v2) / 2
            mc.polyEditUV(uvs, pivotU=pU, pivotV=pV, scaleU=scale, scaleV=scale)
        mc.select(originalSelection)


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
        # type: () -> UVSetList
        """Get the UV sets assigned to the face.

        Optimisation:
            From a quick test, the overhead of constructing the classes
            is about 4x slower, with 0.08s vs 0.02s on 40k faces.
            If only the UV set names are needed, then consider using
            `map(mesh.getFaceUVSetNames, range(mesh.numPolygons))`.
        """
        return UVSetList(self.node, self.index)

    @property
    def _uvShellIDs(self):
        # type: () -> List[int]
        """UV shell IDs for the current face.

        TODO:
            Integrate with UV shell class
        """
        return mc.polyEvaluate(self, uvShellIds=True)


# Handle circular dependencies
# pylint: disable=wrong-import-position
from ..uv_set import UVSet, UVSetList
from . import Node
