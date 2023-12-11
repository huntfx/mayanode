import maya.cmds as mc

from .node import Node
from .. import utils


class Reference(Node):
    """Handle references.
    TODO: Tests
    """

    @classmethod
    def getAll(cls, parent=None):
        if parent is None:
            refs = utils.runAndLog(mc.file, query=True, reference=True)
        else:
            refs = utils.runAndLog(mc.file, parent, query=True, reference=True)

        for ref in refs:
            refNode = utils.runAndLog(mc.referenceQuery, ref, referenceNode=True)
            yield cls(refNode)

    @classmethod
    def listAll(cls, parent=None):
        return list(cls.getAll(parent=parent))

    @property
    def refNode(self):
        return self

    @property
    def namespace(self):
        return utils.runAndLog(mc.referenceQuery, self, namespace=True).strip(':')

    @namespace.setter
    def namespace(self, namespace):
        utils.runAndLog(mc.file, self.path, edit=True, namespace=namespace)

    @property
    def path(self):
        return utils.runAndLog(mc.referenceQuery, self, filename=True)

    @path.setter
    def path(self, path):
        utils.runAndLog(mc.file, path, loadReference=self)

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
