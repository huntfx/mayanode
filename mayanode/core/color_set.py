import maya.cmds as mc

from .. import exceptions, utils


class ColorSet(utils.StrMixin):
    """Handle color sets."""

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
        utils.logger.info("Renaming '%s' color set '%s' to '%s'", self.node, self.name, name)
        utils.runAndLog(mc.polyColorSet, self.node, rename=True, colorSet=self.name, newColorSet=name)
        self._name = name

    @property
    def node(self):
        """Get the node."""
        return self._node

    def delete(self):
        """Delete a color set.

        Raises:
            ColorSetNotFoundError(ColorSetError): If deleting one that doesn't exist.
        """
        utils.logger.info('Deleting color set: %s.%s', self.node, self.name)
        try:
            utils.runAndLog(mc.polyColorSet, self.node, delete=True, colorSet=self.name)
        except RuntimeError as e:
            if str(e) == 'Specified color set does not exist on the polygonal object.':
                raise exceptions.ColorSetNotFoundError(self.node, self.name)
            raise
