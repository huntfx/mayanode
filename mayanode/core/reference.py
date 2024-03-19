import os

import maya.cmds as mc

from .node import Node
from .. import utils


class Reference(Node):
    """Handle references.
    TODO: Tests
    """

    @classmethod
    def ls(cls, parent=None):
        if parent is None:
            refs = utils.runAndLog(mc.file, query=True, reference=True)
        else:
            refs = utils.runAndLog(mc.file, parent, query=True, reference=True)
        return [cls(utils.runAndLog(mc.referenceQuery, ref, referenceNode=True)) for ref in refs]

    @property
    def refNode(self):
        return self

    @property
    def namespace(self):
        """Get the namespace of the reference.

        It is possible to delete a namespace while a reference is
        unloaded. Upon reloading the reference, the namespace will be
        created only if the reference contains any nodes. If not then
        the namespace query will fail, and the slower fallback will be
        used to read it from the `file` command.
        """
        try:
            return Namespace(utils.runAndLog(mc.referenceQuery, self, namespace=True))

        # If it fails, then the namespace doesn't exist in the scene
        except RuntimeError as e:
            if str(e) == 'Cannot find the associated namespace.\n':
                return Namespace(utils.runAndLog(mc.file, self.filepath, query=True, namespace=True))
            raise

    @namespace.setter
    def namespace(self, namespace):
        utils.runAndLog(mc.file, self.filepath, edit=True, namespace=namespace)

    @property
    def filepath(self):
        return utils.runAndLog(mc.referenceQuery, self, filename=True, withoutCopyNumber=True)

    @filepath.setter
    def filepath(self, filepath):
        utils.runAndLog(mc.file, filepath, loadReference=self)

    @property
    def filename(self):
        return utils.runAndLog(mc.referenceQuery, self, filename=True, shortName=True, withoutCopyNumber=True)

    @property
    def nodes(self):
        return list(map(Node, utils.runAndLog(mc.referenceQuery, self, nodes=True)))

    @property
    def loaded(self):
        return utils.runAndLog(mc.referenceQuery, self, isLoaded=True)

    @loaded.setter
    def loaded(self, loaded):
        if loaded:
            self.load()
        else:
            self.unload()

    def load(self):
        utils.runAndLog(mc.file, loadReference=self)

    def unload(self):
        utils.runAndLog(mc.file, unloadReference=self)


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .namespace import Namespace
