import maya.cmds as mc  # type: ignore

from .. import utils
from ..exceptions import MultipleFileInfoResultsError, ReadOnlyFileInfoError
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, List, Iterator, Optional, Tuple
    from ..type_hints import StrLike


class _FileInfo(object):
    """Read and store information specific to this file.

    Parameters:
        refNode: Load the data of a reference node.
            Note that this will only work after the references has been
            loaded at least once.
            If empty, the current scene will be used.

    Examples:
        >>> from mayanode import Scene, Reference, FileInfo

        # For the current scene
        >>> FileInfo['application']
        'maya'
        >>> FileInfo['test']
        KeyError: test
        >>> FileInfo['test'] = 'testing'
        >>> FileInfo['test']
        'testing'
        >>> del FileInfo['test']
        >>> FileInfo['test']
        KeyError: test

        # For a reference
        >>> Reference('refNode').fileInfo['application']
        'maya'
        >>> Reference('refNode').fileInfo['test'] = 'testing'
        ReadOnlyFileInfoError: fileInfo is from "refNode" and cannot be edited

        # Equality checks are per file
        >>> Scene.fileInfo == FileInfo
        True
        >>> Reference('refNode').fileInfo == FileInfo
        False
    """

    __slots__ = ['_refNode']

    def __init__(self, refNode=None):
        # type: (Optional[StrLike]) -> None
        if refNode is None:
            refNode = ''
        self._refNode = refNode

    def __eq__(self, other):
        # type: (Any) -> bool
        if isinstance(other, dict):
            return dict(self.items()) == other
        if isinstance(other, _FileInfo):
            return self._refNode == other._refNode
        return False

    def __str__(self):
        # type: () -> str
        return str(dict(self.items()))

    def __repr__(self):
        # type: () -> str
        return '<FileInfo({})>'.format(', '.join(self.keys()))

    def __getitem__(self, item, index=None):
        # type: (str, Optional[int]) -> str
        """Get a fileInfo value.

        By default, multiple fileInfo keys will result in an error.
        Calling `__getitem__` directly allows for a specific index to be
        read.

        Raises:
            KeyError
            MultipleFileInfoResultsError
        """
        result = mc.fileInfo(item, query=True, referenceNode=self._refNode)
        if not result:
            raise KeyError(item)
        if index is None and len(result) > 1:
            raise MultipleFileInfoResultsError(item)
        if index is not None:
            return result[index]
        return result[0]

    def __setitem__(self, item, value):
        # type: (str, str) -> None
        """Set or update a fileInfo value.

        Raises:
            ReferenceFileInfoError
        """
        utils.logger.info('Setting data for fileInfo: %s', item)
        if self._refNode:
            raise ReadOnlyFileInfoError('is from "{}"'.format(self._refNode))
        mc.fileInfo(item, value)

    def __delitem__(self, item):
        # type: (str) -> None
        """Delete a fileInfo value.

        Raises:
            ReferenceFileInfoError
        """
        utils.logger.info('Deleting fileInfo: %s', item)
        if self._refNode:
            raise ReadOnlyFileInfoError('is from "{}"'.format(self._refNode))
        mc.fileInfo(remove=item)

    def keys(self):
        # type: () -> List[str]
        """Get all fileInfo keys."""
        return mc.fileInfo(query=True, referenceNode=self._refNode)[::2]

    def values(self):
        # type: () -> List[str]
        """Get all fileInfo values."""
        return mc.fileInfo(query=True, referenceNode=self._refNode)[1::2]

    def items(self):
        # type: () -> List[Tuple[str, str]]
        """Get all fileInfo items."""
        result = mc.fileInfo(query=True, referenceNode=self._refNode)
        return list(zip(result[::2], result[1::2]))

    def __iter__(self):
        # type: () -> Iterator[str]
        """Iterate over the fileInfo keys."""
        return iter(self.keys())

    def __len__(self):
        # type: () -> int
        """Get the number of fileInfo values."""
        return len(mc.fileInfo(query=True, referenceNode=self._refNode)) // 2

    @property
    def reference(self):
        # type: () -> Optional[Reference]
        """Get the associated reference."""
        if self._refNode:
            return Reference(self._refNode)
        return None


FileInfo = _FileInfo()


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .reference import Reference
