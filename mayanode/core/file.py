import errno
import os

import maya.cmds as mc  # type: ignore
import maya.mel as mel  # type: ignore

from .. import exceptions, utils
from ..types import StrMixin
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List, Optional
    from ..type_hints import StrLike


class File(StrMixin):
    """Handle individual filepaths."""

    def __init__(self, path):
        self._path = os.path.normpath(path)

    @property
    def name(self):
        # type: () -> str
        return self._path

    @property
    def filepath(self):
        # type: () -> str
        """Get the full path."""
        return self._path

    @property
    def filename(self):
        # type: () -> str
        """Get the filename of the path."""
        return os.path.basename(self._path)

    @property
    def extension(self):
        # type: () -> str
        """Get the file extension."""
        return os.path.splitext(self._path)[1][1:].lower()

    @property
    def exists(self):
        # type: () -> bool
        """Determine if the path exists."""
        return os.path.exists(self.filepath)

    def checkExists(self):
        # type: () -> None
        """Raise an error if the file does not exist."""
        if not self.exists:
            raise exceptions.FileNotFoundError(errno.ENOENT, 'No such file', self.filepath)

    @classmethod
    def currentScene(cls):
        # type: () -> Optional[File]
        """Get the path to the current scene."""
        path = mc.file(query=True, sceneName=True)
        if path:
            return cls(path)
        return None

    def open(self, force=False, selectivePreload=None):
        # type: (bool, Optional[bool]) -> None
        """Open the file as a Maya scene.

        Raises:
            IOError: If the scene failed to open.
            FileNotFoundError: If the file doesn't exist.
        """
        self.checkExists()

        if selectivePreload is None:
            if force:
                selectivePreload = False
            else:
                selectivePreload = mc.optionVar(query='fileSelPreload')
        try:
            mc.file(self, open=True, force=True, buildLoadSettings=selectivePreload)
        except RuntimeError as e:
            raise IOError('failed to open {} (error: {})'.format(self, e))

        # Selective reference preload
        if selectivePreload:
            mc.optionVar(stringValue=('preloadRefEdTopLevelFile', self.replace('\\', '/')))
            mel.eval('PreloadReferenceEditor;')
        else:
            utils.addToRecentFiles(self.filepath)

    def import_(self, namespace=None):
        # type: (StrLike) -> Optional[Namespace]
        """Import a file into the scene.

        A namespace will be returned which can be used to get a list of
        all the imported nodes.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        self.checkExists()

        # Find unique namespace
        if namespace is None:
            namespace = os.path.splitext(self.filename)[0]
        namespace = Namespace.findUnique(namespace)

        # Import the file
        params = {
            'i': True,
            'ignoreVersion': True,
            'preserveReferences': True,
            'importFrameRate': False,
            'namespace': namespace,
            'mergeNamespacesOnClash': True,
        }
        utils.logger.info('Importing file "%s" to namespace "%s"', self, namespace)
        mc.file(self, **params)
        return namespace

    def reference(self, namespace=None, group=None, defer=False):
        # type: (StrLike, str, bool) -> Optional[Reference]
        """Reference a file into the scene.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        self.checkExists()

        # Find unique namespace
        if namespace is None:
            namespace = os.path.splitext(self.filename)[0]
        namespace = Namespace.findUnique(namespace)

        # Reference the file
        params = {
            'reference': True,
            'ignoreVersion': True,
            'namespace': namespace,
            'mergeNamespacesOnClash': True,
            'force': True,
        }
        if group:
            params['groupReference'] = True
            params['groupName'] = True
        if defer:
            params['deferReference'] = True
        refFile = mc.file(self, **params)
        refNode = mc.referenceQuery(refFile, referenceNode=True)
        return Reference(refNode)

    @property
    def references(self):
        # type: () -> List[Reference]
        """Get all references matching a file path."""
        return Reference.fromFile(self)


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .namespace import Namespace
from .reference import Reference
