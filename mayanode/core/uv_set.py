import maya.cmds as mc

from .. import exceptions, utils


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
