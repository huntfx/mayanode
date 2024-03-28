import maya.cmds as mc

from .. import exceptions, types, utils


class UVSet(utils.StrMixin):
    """Handle UV sets."""

    __slots__ = ['_node', '_name']

    def __init__(self, node, name):
        self._node = node
        self._name = name

    def __repr__(self):
        return "<{}('{}.{}')>".format(type(self).__name__, self.node, self.name)

    @property
    def name(self):
        """Get the name of the color set."""
        return self._name

    @name.setter
    def name(self, name):
        """Rename a color set.
        This does not update the UI window.

        Raises:
            RuntimeError: Cannot rename color set to an existing color set name.
        """
        utils.logger.info("Renaming '%s' UV set '%s' to '%s'", self.node, self.name, name)
        utils.runAndLog(mc.polyUVSet, self.node, rename=True, uvSet=self.name, newUVSet=name)
        self._name = name

    @property
    def node(self):
        """Get the node."""
        return self._node

    @property
    def attr(self):
        """Get the UV set attribute.

        Raises:
            UVSetNotFoundError

        Returns:
            Attribute('node.uvSet[i].uvSetName')

        TODO:
            Tests
        """
        physicalIndex = self.physicalIndex
        for i, uvSet in enumerate(self.node.attrs['uvSet'].children):
            if i == physicalIndex:
                return uvSet.children['uvSetName']
        raise exceptions.UVSetNotFoundError(self.node, self)

    @property
    def physicalIndex(self):
        """Get the physical index of the UV set.

        TODO:
            Tests
        """
        mfnMesh = self.node.api.mesh
        return mfnMesh.getUVSetNames().index(self.name)

    @property
    def logicalIndex(self):
        """Get the logical index of the UV set.

        TODO:
            Tests
        """
        return self.attr.api.plug.parent().logicalIndex()

    def delete(self):
        """Delete a color set.

        Raises:
            UVSetNotFoundError(UVSetError): If deleting one that doesn't exist.
            UVSetDeleteDefaultError(UVSetError): If deleting the default UV set.
        """
        utils.logger.info('Deleting UV set: %s.%s', self.node, self.name)
        try:
            utils.runAndLog(mc.polyUVSet, self.node, delete=True, uvSet=self.name)
        except RuntimeError as e:
            if 'The default uv set cannot be deleted.' in str(e):
                raise exceptions.UVSetDeleteDefaultError(self.node, self.name)
            if 'Specified color set does not exist on the polygonal object.' in str(e):
                raise exceptions.UVSetNotFoundError(self.node, self.name)
            raise

    @property
    def textures(self):
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
        textures = self.node.api.mesh.getAssociatedUVSetTextures(self.name)
        return [Node(texture) for texture in textures]


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .node import Node
from .node.attributes import Attribute
