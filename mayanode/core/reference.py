import maya.api.OpenMaya as om2
import maya.cmds as mc

from .node import Node
from .. import exceptions, utils


class Reference(Node):
    """Handle references.
    TODO: Tests
    """

    @classmethod
    def ls(cls, parent=None, namespace=None):
        if parent is None:
            refs = utils.runAndLog(mc.file, query=True, reference=True)
        else:
            refs = utils.runAndLog(mc.file, parent, query=True, reference=True)
        return [cls(utils.runAndLog(mc.referenceQuery, ref, referenceNode=True)) for ref in refs]

    @classmethod
    def fromNode(cls, node):
        """Get the reference from an individual node.
        All the references are searched for a matching namespace.
        Returns None if no reference was found.
        """
        ns = node.namespace
        if not ns:
            return None
        it = om2.MItDependencyNodes(om2.MFn.kReference)
        for _ in it:
            refNode = it.thisNode()
            if ns == om2.MFnReference(refNode).associatedNamespace(False):
                return cls(refNode)
        return None

    @property
    def refNode(self):
        return self

    @property
    def namespace(self):
        """Get the namespace of the reference.

        Note: It is possible to delete a namespace while a reference is
        unloaded. Upon reloading the reference, the associated namespace
        will be created only if the reference contains any nodes.

        Equivalent:
            `mc.referenceQuery(self, namespace=True)`
        """
        associatedNamespace = self.api.reference.associatedNamespace(False)
        if associatedNamespace:
            return Namespace(associatedNamespace)

        # If the namespace doesn't exist then fallback to the slower command
        return Namespace(utils.runAndLog(mc.file, self.filepath, query=True, namespace=True))

    @namespace.setter
    def namespace(self, namespace):
        """Set a new namespace for the reference.

        TODO:
            Should this rename the existing one?
        """
        utils.logger.info('Setting new reference namespace for "%s": %s', self, namespace)
        utils.runAndLog(mc.file, self.filepath, edit=True, namespace=namespace)

    @property
    def filepath(self):
        """Get the resolved reference file path.

        Equivalent:
            `mc.referenceQuery(self, filename=True, withoutCopyNumber=True)`

        TODO:
            `ref.filepath.unresolved`
        """
        return self.api.reference.fileName(resolvedName=True, includePath=False, includeCopyNumber=False)

    @filepath.setter
    def filepath(self, filepath):
        utils.logger.info('Setting new reference path for "%s": %s', self, filepath)
        utils.runAndLog(mc.file, filepath, loadReference=self)

    @property
    def filename(self):
        """Get the reference filename.

        Equivalent:
            `mc.referenceQuery(self, filename=True, shortName=True, withoutCopyNumber=True)`
        """
        return self.api.reference.fileName(resolvedName=False, includePath=True, includeCopyNumber=False)

    @property
    def loaded(self):
        """Determine if the reference is loaded.

        Equivalent:
            `mc.referenceQuery(self, isLoaded=True)`
        """
        return self.api.reference.isLoaded()

    @loaded.setter
    def loaded(self, loaded):
        """Load or unload the reference."""
        if loaded:
            self.load()
        else:
            self.unload()

    def load(self):
        """Load the reference."""
        utils.logger.info('Loading reference: %s', self)
        utils.runAndLog(mc.file, loadReference=self)

    def unload(self):
        utils.logger.info('Unloading reference: %s', self)
        utils.runAndLog(mc.file, unloadReference=self)

    @property
    def nodes(self):
        """Get a list of nodes in the reference.

        Equivalent:
            `mc.referenceQuery(self, nodes=True)`

        TODO:
            Use `self.api.reference.containsNodeExactly()` for `node in ref.nodes`
        """
        if self.api.reference is None:
            return []
        return [Node(node) for node in self.api.reference.nodes()]

    @property
    def locked(self):
        """Get if the reference is locked."""
        return self.api.reference.isLocked()

    @locked.setter
    def locked(self, locked):
        """Set the locked state of the reference."""
        if locked:
            self.lock()
        else:
            self.unlock()

    def lock(self):
        """Lock the reference."""
        self.attrs['locked'] = True

    def unlock(self):
        """Unlock the reference."""
        self.attrs['locked'] = False


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .namespace import Namespace
