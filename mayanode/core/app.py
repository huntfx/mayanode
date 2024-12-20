import operator

import maya.api.OpenMaya as om2  # type: ignore
import maya.cmds as mc  # type: ignore

from ..version import Version


VERSION = '{}.{}.{}'.format(mc.about(majorVersion=True), mc.about(minorVersion=True), mc.about(patchVersion=True))


class _Maya(object):
    """Singleton for accessing Maya application data."""

    @property
    def version(self):
        # type: () -> Version
        """Get the current Maya version."""
        return Version(VERSION)

    @property
    def batch(self):
        # type: () -> bool
        """Determine if Maya is running in batch mode.

        Equivelant:
            `mc.about(batch=True)`
        """
        return om2.MGlobal.mayaState() == om2.MGlobal.kBatch

    @property
    def interactive(self):
        # type: () -> bool
        """Determine if Maya  is running in interactive mode.

        Equivelant:
            `not mc.about(batch=True)`
        """
        return om2.MGlobal.mayaState() == om2.MGlobal.kInteractive

    @property
    def time(self):
        # type: () -> _Time
        """Get the value of time."""
        return Time

    @property
    def viewport(self):
        # type: () -> Viewport
        """Get the active viewport."""
        return Viewport.active


Maya = _Maya()


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .time import Time, _Time
from .viewport import Viewport
