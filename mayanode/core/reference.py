import os

import maya.api.OpenMaya as om2
import maya.cmds as mc  # type: ignore

from .node import Node
from .. import exceptions, types, utils
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Iterable
    from ..type_hints import StrLike


class Reference(Node):
    """Handle reference nodes and their data.

    This is designed to work similiarly to the `Node` class, but on
    the references themselves. The reference node itself can be read
    from the `self.refNode` property.

    TODO:
        Remove Node inheritance to make it a standalone class
    """

    @classmethod
    def ls(cls, *args, **kwargs):
        # type: (*StrLike, **Any) -> list[Reference]
        """Get all valid references."""
        # Get all file references
        # Using `mc.ls` may return invalid references without files
        # (despite what the documentation says), and `mc.file` with
        # `mc.referenceQuery` is considerably slower
        if args:
            sl = utils.Ls(*args, type='reference')()
            if sl is None:
                return []
            refNodeGen = map(sl.getDependNode, range(sl.length()))  # type: Iterable[om2.MObject]

        # If no args, then it's faster just to do this
        else:
            refNodeGen = utils.iterDG(om2.MFn.kReference)

        refNodes = []  # type: list[Reference]
        for refNode in refNodeGen:
            # The second argument (includePath) is faster when True
            try:
                om2.MFnReference(refNode).fileName(True, True, True)
            except RuntimeError:
                continue
            refNodes.append(cls(refNode))

        # Filter by loaded refs
        loaded = kwargs.get('loaded')  # type: bool | None
        if loaded is not None:
            refNodes = [ref for ref in refNodes if ref.loaded == loaded]

        return refNodes

    @classmethod
    def fromFile(cls, filepath):
        # type: (StrLike) -> list[Reference]
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

    @classmethod
    def fromNamespace(cls, namespace):
        # type: (StrLike) -> Reference | None
        """Get the reference matching the namespace."""
        return Namespace(namespace).reference

    @property
    def refNode(self):
        # type: () -> Node
        """Get the associated reference node."""
        return Node(self)

    @property
    def name(self):
        # type: () -> str
        """Get the node name."""
        return super(Reference, self).name

    @name.setter
    def name(self, name):
        # type: (Any) -> None
        """Set a new reference node name.

        By default, reference nodes are locked and can't be renamed.
        This is a convenience method to automatically handle unlocking.
        """
        refNode = self.refNode
        isLocked = refNode.locked
        if isLocked:
            refNode.unlock()
        try:
            refNode.name = name
        finally:
            refNode.lock()

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
        mfnReference = self.api.reference
        assert mfnReference is not None

        # Get the associated namespace
        # If the namespace exists, it will return the namespace
        # If the namespace does not exist, it will return an empty string
        # If the reference has no namespace, it will return an empty string
        associatedNamespace = mfnReference.associatedNamespace(False)
        if associatedNamespace:
            return Namespace(associatedNamespace)

        # If an empty string, check that it is meant to be empty
        # If the namespace doesn't exist an error will be raised
        try:
            return Namespace(mc.referenceQuery(self, namespace=True))

        # Fallback to the slower method to get the correct namespace
        # All references here have namespaces that don't exist
        except RuntimeError:
            return Namespace(mc.file(self.refPath, query=True, namespace=True))

    @namespace.setter
    def namespace(self, namespace):
        # type: (Namespace | str) -> None
        """Set a new namespace for the reference.

        Raises:
            UnloadedReferenceNamespaceError
            ReferenceWithoutNamespaceError
        """
        utils.logger.info('Updating reference namespace for "%s": %s', self, namespace)
        utils.raiseIfNodeNotFound(self.refNode)

        if not self.loaded:
            raise exceptions.UnloadedReferenceNamespaceError(self)
        if not self.namespace:
            raise exceptions.ReferenceWithoutNamespaceError(self)
        mc.file(self.refPath, edit=True, namespace=namespace)

    @property
    def path(self):
        # type: () -> File | None
        """Get the raw unresolved reference file path.
        Use `.resolve()` to get the resolved path.

        Equivalent:
            `mc.referenceQuery(self, filename=True, unresolvedName=True, withoutCopyNumber=True)`

        Returns:
            The resolved filepath or None.
        """
        utils.raiseIfNodeNotFound(self.refNode)
        mfnReference = self.api.reference
        assert mfnReference is not None
        try:
            filepath = mfnReference.fileName(resolvedName=False, includePath=False, includeCopyNumber=False)
        except RuntimeError as e:
            if '(kFailure): Object does not exist' in str(e):
                return None
            raise
        return File(os.path.normpath(filepath))

    @path.setter
    def path(self, path):
        # type: (str) -> None
        """Update the reference path."""
        utils.logger.info('Setting new reference path for "%s": %s', self, path)
        utils.raiseIfNodeNotFound(self.refNode)
        mc.file(path, loadReference=self)

    @property
    def refPath(self):
        # type: () -> File | None
        """Get the unresolved reference file path with copy numbers.

        Equivalent:
            `mc.referenceQuery(self, filename=True, unresolvedName=True)`

        Returns:
            The unresolved filepath or None.
        """
        utils.raiseIfNodeNotFound(self.refNode)
        mfnReference = self.api.reference
        assert mfnReference is not None
        try:
            filepath = mfnReference.fileName(resolvedName=False, includePath=False, includeCopyNumber=True)
        except RuntimeError as e:
            if '(kFailure): Object does not exist' in str(e):
                return None
            raise
        return File(os.path.normpath(filepath))

    @property
    def filename(self):
        # type: () -> str | None
        """Get the reference filename.

        Equivalent:
            `mc.referenceQuery(self, filename=True, shortName=True, withoutCopyNumber=True)`

        Returns:
            The filename or None.
        """
        utils.raiseIfNodeNotFound(self.refNode)
        mfnReference = self.api.reference
        assert mfnReference is not None
        try:
            return mfnReference.fileName(resolvedName=False, includePath=True, includeCopyNumber=False)
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
        mfnReference = self.api.reference
        assert mfnReference is not None
        return mfnReference.isLoaded()

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
        mfnReference = self.api.reference
        assert mfnReference is not None

        namespacesToDelete = []
        if forceRemoveNamespaces:
            # Determine if the node is a reference with no namespace
            requiresExtraCleanup = False
            if not mfnReference.associatedNamespace(False):
                try:
                    if mc.referenceQuery(self, namespace=True) == ':':
                        requiresExtraCleanup = True
                except RuntimeError:
                    pass

            # Get the namespace from all child ref nodes
            if requiresExtraCleanup:
                for node in mfnReference.nodes():
                    if node.hasFn(om2.MFn.kReference):
                        namespacesToDelete.append(om2.MFnReference(node).associatedNamespace(False))

        # Delete the reference
        filename = mfnReference.fileName(resolvedName=True, includePath=True, includeCopyNumber=True)
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
        mfnReference = self.api.reference
        assert mfnReference is not None
        return mfnReference.isLocked()

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
        mObject = self.refNode.api.object
        assert mObject is not None
        for _ in depNodeIt:
            refNode = depNodeIt.thisNode()
            fnRefNode = om2.MFnReference(refNode)
            if fnRefNode.containsNode(mObject):
                depth += 1
        return depth

    @property
    def parent(self):
        # type: () -> Reference | None
        """Get the parent reference."""
        utils.raiseIfNodeNotFound(self.refNode)
        depNodeIt = om2.MItDependencyNodes(om2.MFn.kReference)
        mObject = self.refNode.api.object
        for _ in depNodeIt:
            refNode = om2.MFnReference(depNodeIt.thisNode())
            try:
                containsNode = refNode.containsNodeExactly(mObject)
            except RuntimeError:
                containsNode = False
            if containsNode:
                return Reference(refNode)
        return None

    @property
    def ancestors(self):
        # type: () -> list[Reference]
        """Get all parent references."""
        utils.raiseIfNodeNotFound(self.refNode)
        depNodeIt = om2.MItDependencyNodes(om2.MFn.kReference)
        mObject = self.refNode.api.object
        ancestors = []
        for _ in depNodeIt:
            refNode = om2.MFnReference(depNodeIt.thisNode())
            try:
                containsNode = refNode.containsNode(mObject)
            except RuntimeError:
                containsNode = False
            if containsNode:
                ancestors.append(Reference(refNode))
        return ancestors

    @property
    def children(self):
        # type: () -> list[Reference]
        """Get the nested child references."""
        utils.raiseIfNodeNotFound(self.refNode)
        depNodeIt = om2.MItDependencyNodes(om2.MFn.kReference)
        refNode = self.api.reference
        assert refNode is not None
        children = []
        for _ in depNodeIt:
            mObject = depNodeIt.thisNode()
            try:
                containsNode = refNode.containsNodeExactly(mObject)
            except RuntimeError:
                containsNode = False
            if containsNode:
                children.append(Reference(mObject))
        return children

    @property
    def descendents(self):
        # type: () -> list[Reference]
        """Get all nested child references and their children."""
        utils.raiseIfNodeNotFound(self.refNode)
        depNodeIt = om2.MItDependencyNodes(om2.MFn.kReference)
        refNode = self.api.reference
        assert refNode is not None
        children = []
        for _ in depNodeIt:
            mObject = depNodeIt.thisNode()
            try:
                containsNode = refNode.containsNode(mObject)
            except RuntimeError:
                containsNode = False
            if containsNode:
                children.append(Reference(mObject))
        return children

    def import_(self):
        # type: () -> None
        """Import the current reference.

        Raises:
            NotATopLevelReferenceImportError
            UnloadedReferenceImportError
        """
        utils.raiseIfNodeNotFound(self.refNode)
        if not self.topLevel:
            raise exceptions.NotATopLevelReferenceImportError(self)
        if not self.loaded:
            raise exceptions.UnloadedReferenceImportError(self)
        mc.file(self.refPath, importReference=True)

    @property
    def fileInfo(self):
        # type: () -> _FileInfo
        """Get the fileInfo data for the current reference."""
        return _FileInfo(self)


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
        mfnReference = self.reference.api.reference
        assert mfnReference is not None
        self._apiObjects = mfnReference.nodes()
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
        # type: (int | str | None) -> bool
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
        mfnReference = self.reference.api.reference
        assert mfnReference is not None
        self._apiObjects = mfnReference.nodes()
        super(ReferenceNodes, self).reload()


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .file import File
from .file_info import _FileInfo
from .namespace import Namespace
