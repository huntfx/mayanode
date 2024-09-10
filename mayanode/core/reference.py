import os

import maya.api.OpenMaya as om2  # type: ignore
import maya.cmds as mc  # type: ignore

from .node import Node
from .. import exceptions, types, utils
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, List, Union, Optional
    from ..type_hints import StrLike


class Reference(Node):
    """Handle references.
    TODO: Tests
    """

    @classmethod
    def ls(cls, *args, **kwargs):
        # type: (*StrLike, **Any)  -> List[Reference]
        """Get all valid references."""
        # Get all file references
        # Using `mc.ls` may return invalid references without files
        # (despite what the documentation says), and `mc.file` with
        # `mc.referenceQuery` is considerably slower
        if args:
            sl = utils.Ls(*args, type='reference')()
            refNodeGen = map(sl.getDependNode, range(sl.length()))

        # If no args, then it's faster just to do this
        else:
            refNodeGen = utils.iterDG(om2.MFn.kReference)

        refNodes = []
        for refNode in refNodeGen:
            # The second argument (includePath) is faster when True
            try:
                om2.MFnReference(refNode).fileName(True, True, True)
            except RuntimeError:
                continue
            refNodes.append(cls(refNode))

        # Filter by loaded refs
        loaded = kwargs.get('loaded')  # type: Optional[bool]
        if loaded is not None:
            refNodes = [ref for ref in refNodes if ref.loaded == loaded]

        return refNodes

    @classmethod
    def fromFile(cls, filepath):
        # type: (StrLike) -> List[Reference]
        """Get all references matching a file path."""
        filepath = os.path.normpath(str(filepath))
        matches = []
        for refNode in utils.iterDG(om2.MFn.kReference):
            try:
                refPath = om2.MFnReference(refNode).fileName(True, False, False)
            except RuntimeError:
                continue
            if os.path.normpath(refPath) == filepath:
                matches.append(cls(refNode))
        return matches

    @property
    def refNode(self):
        # type: () -> Reference
        return self

    @property
    def namespace(self):
        # type: () -> Namespace
        """Get the namespace of the reference.

        Note: It is possible to delete a namespace while a reference is
        unloaded. Upon reloading the reference, the associated namespace
        will be created only if the reference contains any nodes.

        Equivalent:
            `mc.referenceQuery(self, namespace=True)`
        """
        utils.raiseIfNodeNotFound(self.refNode)
        associatedNamespace = self.api.reference.associatedNamespace(False)
        if associatedNamespace:
            return Namespace(associatedNamespace)

        # If the reference was created without a namespace, it will have ":"
        try:
            return Namespace(mc.referenceQuery(self, namespace=True))

        # If the namespace doesn't exist then fallback to the slower command
        except RuntimeError:
            path = self.api.reference.fileName(resolvedName=True, includePath=False, includeCopyNumber=True)
            return Namespace(mc.file(path, query=True, namespace=True))

    @namespace.setter
    def namespace(self, namespace):
        # type: (Union[Namespace, str]) -> None
        """Set a new namespace for the reference.

        Raises:
            # RuntimeError: Cannot edit the namespace because the reference was not created using namespaces. #

        TODO:
            Should this rename the existing one?
        """
        utils.logger.info('Setting new reference namespace for "%s": %s', self, namespace)
        utils.raiseIfNodeNotFound(self.refNode)
        mc.file(self.filepath, edit=True, namespace=namespace)

    @property
    def filepath(self):
        # type: () -> Optional[File]
        """Get the resolved reference file path.

        Equivalent:
            `mc.referenceQuery(self, filename=True, withoutCopyNumber=True)`

        Returns:
            The filepath or None.

        TODO:
            `ref.filepath.unresolved`
        """
        utils.raiseIfNodeNotFound(self.refNode)
        try:
            filepath = self.api.reference.fileName(resolvedName=True, includePath=False, includeCopyNumber=False)
        except RuntimeError as e:
            if '(kFailure): Object does not exist' in str(e):
                return None
            raise
        return File(os.path.normpath(filepath))

    @filepath.setter
    def filepath(self, filepath):
        # type: (str) -> None
        utils.logger.info('Setting new reference path for "%s": %s', self, filepath)
        utils.raiseIfNodeNotFound(self.refNode)
        mc.file(filepath, loadReference=self)

    @property
    def filename(self):
        # type: () -> Optional[str]
        """Get the reference filename.

        Equivalent:
            `mc.referenceQuery(self, filename=True, shortName=True, withoutCopyNumber=True)`

        Returns:
            The filename or None.
        """
        utils.raiseIfNodeNotFound(self.refNode)
        try:
            return self.api.reference.fileName(resolvedName=False, includePath=True, includeCopyNumber=False)
        except RuntimeError as e:
            if '(kFailure): Object does not exist' in str(e):
                return None
            raise

    @property
    def loaded(self):
        # type: () -> bool
        """Determine if the reference is loaded.

        Equivalent:
            `mc.referenceQuery(self, isLoaded=True)`
        """
        utils.raiseIfNodeNotFound(self.refNode)
        return self.api.reference.isLoaded()

    @loaded.setter
    def loaded(self, loaded):
        # type: (bool) -> None
        """Load or unload the reference."""
        if loaded:
            self.load()
        else:
            self.unload(force=True)

    def load(self):
        # type: () -> None
        """Load the reference."""
        utils.logger.info('Loading reference: %s', self)
        utils.raiseIfNodeNotFound(self.refNode)
        mc.file(loadReference=self)

    def unload(self, force=False):
        # type: (bool) -> None
        """Unload a reference.
        If the force argument is not given, a popup may appear to warn
        about loss of reference edits.
        """
        utils.logger.info('Unloading reference: %s', self)
        utils.raiseIfNodeNotFound(self.refNode)
        mc.file(unloadReference=self, force=force)

    def delete(self, forceRemoveNamespaces=False):
        # type: (bool) -> bool
        """Delete the reference.

        If the reference has no namespace, then any child reference
        namespaces will not be removed on deletion. The parameter
        `forceRemoveNamespaces` has been added for this reason, but
        since those namespaces may contain other non-reference nodes,
        it is not enabled by default.

        Returns if the reference was deleted.
        """
        utils.logger.info('Deleting reference: %s', self)
        utils.raiseIfNodeNotFound(self.refNode)
        mfnRef = self.api.reference

        namespacesToDelete = []
        if forceRemoveNamespaces:
            # Determine if the node is a reference with no namespace
            requiresExtraCleanup = False
            if not mfnRef.associatedNamespace(False):
                try:
                    if mc.referenceQuery(self, namespace=True) == ':':
                        requiresExtraCleanup = True
                except RuntimeError:
                    pass

            # Get the namespace from all child ref nodes
            if requiresExtraCleanup:
                for node in mfnRef.nodes():
                    if node.hasFn(om2.MFn.kReference):
                        namespacesToDelete.append(om2.MFnReference(node).associatedNamespace(False))

        # Delete the reference
        filename = mfnRef.fileName(resolvedName=True, includePath=True, includeCopyNumber=True)
        mc.file(filename, removeReference=True)

        # If no namespace, then child refnode namespaces will be left behind
        for ns in namespacesToDelete:
            Namespace(ns).delete(recursive=True)

        return True

    @property
    def nodes(self):
        # type: () -> ReferenceNodes
        """Get a list of nodes in the reference.
        This is slightly faster than using `ls` to search by namespace.

        Equivalent:
            `mc.referenceQuery(self, nodes=True)`
            `mc.ls(self.namespace + ':*')`
        """
        utils.raiseIfNodeNotFound(self.refNode)
        return ReferenceNodes(self)

    @property
    def locked(self):
        # type: () -> bool
        """Get if the reference is locked."""
        utils.raiseIfNodeNotFound(self.refNode)
        return self.api.reference.isLocked()

    @locked.setter
    def locked(self, locked):
        # type: (bool) -> None
        """Set the locked state of the reference."""
        if locked:
            self.lock()
        else:
            self.unlock()

    def lock(self):
        # type: () -> None
        """Lock the reference."""
        utils.raiseIfNodeNotFound(self.refNode)
        loaded = self.loaded
        if loaded:
            self.unload(force=True)
        self.attrs['locked'].value = True
        if loaded:
            self.load()

    def unlock(self):
        # type: () -> None
        """Unlock the reference.

        Note that this requires reloading the reference, and Maya warns
        that reference edits will be lost.
        """
        utils.raiseIfNodeNotFound(self.refNode)
        loaded = self.loaded
        if loaded:
            self.unload(force=True)
        self.attrs['locked'].value = False
        if loaded:
            self.load()

    @property
    def topLevel(self):
        # type: () -> bool
        """Determine if the reference is a top level one."""
        utils.raiseIfNodeNotFound(self.refNode)
        return not self.refNode.api.dependencyNode.isFromReferencedFile

    @property
    def depth(self):
        # type: () -> int
        """Determine the depth of this reference.
        A top level reference will have a depth of 0.
        """
        utils.raiseIfNodeNotFound(self.refNode)
        depth = 0
        depNodeIt = om2.MItDependencyNodes(om2.MFn.kReference)
        mobject = self.refNode.api.object
        for _ in depNodeIt:
            refNode = depNodeIt.thisNode()
            fnRefNode = om2.MFnReference(refNode)
            if fnRefNode.containsNode(mobject):
                depth += 1
        return depth

    @property
    def parent(self):
        # type: () -> Optional[Reference]
        """Get the parent reference."""
        utils.raiseIfNodeNotFound(self.refNode)
        depNodeIt = om2.MItDependencyNodes(om2.MFn.kReference)
        currentObject = self.refNode.api.object
        for _ in depNodeIt:
            refNode = om2.MFnReference(depNodeIt.thisNode())
            # TODO: Test RuntimeError: (kFailure): Object does not exist
            if refNode.containsNodeExactly(currentObject):
                return Reference(refNode)
        return None

    @property
    def ancestors(self):
        # type: () -> List[Reference]
        """Get all parent references."""
        utils.raiseIfNodeNotFound(self.refNode)
        depNodeIt = om2.MItDependencyNodes(om2.MFn.kReference)
        currentObject = self.refNode.api.object
        ancestors = []
        for _ in depNodeIt:
            refNode = om2.MFnReference(depNodeIt.thisNode())
            if refNode.containsNode(currentObject):
                ancestors.append(Reference(refNode))
        return ancestors

    @property
    def children(self):
        # type: () -> List[Reference]
        """Get the nested child references."""
        utils.raiseIfNodeNotFound(self.refNode)
        depNodeIt = om2.MItDependencyNodes(om2.MFn.kReference)
        currentRefNode = self.api.reference
        children = []
        for _ in depNodeIt:
            refNode = depNodeIt.thisNode()
            if currentRefNode.containsNodeExactly(refNode):
                children.append(Reference(refNode))
        return children

    @property
    def descendents(self):
        # type: () -> List[Reference]
        """Get all nested child references and their children."""
        utils.raiseIfNodeNotFound(self.refNode)
        depNodeIt = om2.MItDependencyNodes(om2.MFn.kReference)
        currentRefNode = self.api.reference
        children = []
        for _ in depNodeIt:
            refNode = depNodeIt.thisNode()
            if currentRefNode.containsNode(refNode):
                children.append(Reference(refNode))
        return children

    def import_(self):
        # type: () -> None
        """Import the current reference.

        Raises:
            ReferenceNotTopLevelError
            ReferenceNotLoadedError
        """
        utils.raiseIfNodeNotFound(self.refNode)
        if not self.topLevel:
            raise exceptions.ReferenceNotTopLevelError(self)
        if not self.loaded:
            raise exceptions.ReferenceNotLoadedError(self)
        mc.file(self.filepath, importReference=True)


class ReferenceNodes(types.MappedLazyList):
    """Hold a list of all nodes in the reference.
    This also acts as a dict for the node names without their namespace.

    Example:
        >>> nodes = Reference('refNode').nodes
        >>> 'pCube1' in nodes
        True
        >>> nodes[0]
        Node('refNode:pCube1')
        >>> nodes['pCube1'] == nodes[0]
        True
        >>> len(nodes)
        1

    TODO:
        Tests
    """

    __slots__ = ['_reference', '_apiObjects']

    def __init__(self, reference):
        # type: (Reference) -> None
        self._reference = reference
        self._apiObjects = self.reference.api.reference.nodes()
        super(ReferenceNodes, self).__init__(None for _ in self._apiObjects)

    def __len__(self):
        return self._apiObjects.__len__()

    @property
    def reference(self):
        # type: () -> Reference
        """Get the associated reference."""
        return self._reference

    def __contains__(self, node):
        """If a particular node belongs to a reference."""
        if isinstance(node, Node):
            return self.reference.api.reference.containsNodeExactly(node.api.object)
        if isinstance(node, om2.MObject):
            return self.reference.api.reference.containsNodeExactly(node)
        return super(ReferenceNodes, self).__contains__(node)

    def generateKey(self, value):
        # type: (Any) -> str
        """Override this to get the dict keys for each item."""
        return str(value).split(':')[-1]

    def loadData(self, key=None):
        # type: (Optional[Union[int, str]]) -> bool
        """Get the node objects."""
        if self._apiObjects is None:
            self._apiObjects = self.reference.api.reference.nodes()

        # Load an index
        if isinstance(key, int):
            if self._data[key] is None:
                self._setitem(key, Node(self._apiObjects[key]))
            return False

        # Load all
        self._set(map(Node, self._apiObjects))
        return True

    def reload(self):
        # type: () -> None
        self._apiObjects = self.reference.api.reference.nodes()
        super(ReferenceNodes, self).reload()


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .file import File
from .namespace import Namespace
