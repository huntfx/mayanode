import operator

import maya.api.OpenMaya as om2  # type: ignore
import maya.cmds as mc  # type: ignore

from ..type_hints import TYPE_CHECKING
from ..utils import standardiseVersions

if TYPE_CHECKING:
    from typing import Any, cast
    from ..utils import standardiseVersions, Token, TokenisedVersion


VERSION = '{}.{}.{}'.format(mc.about(majorVersion=True), mc.about(minorVersion=True), mc.about(patchVersion=True))


class Version(str):
    """Singleton for accessing Maya version data.

    Advanced comparisons are supported, but a `TypeError` will get
    raised if comparing to strings.
    """

    def __init__(self, version):
        # type: (str) -> None
        self.major, self.minor, self.patch = version.split('.')

    def __int__(self):
        # type: () -> int
        """Get the major version number."""
        return int(self.major)

    def __float__(self):
        # type: () -> float
        """Get the major and minor version number."""
        return float('{}.{}'.format(self.major, self.minor))

    def __eq__(self, other):
        # type: (Any) -> bool
        """Determine if two versions are equal."""
        a, b = standardiseVersions(self, other)
        return a == b

    def __ne__(self, other):
        # type: (Any) -> bool
        """Determine if two versions are not equal."""
        a, b = standardiseVersions(self, other)
        return a != b

    def __gt__(self, other):
        # type: (Any) -> bool
        """Determine if the current version is higher."""
        a, b = standardiseVersions(self, other)
        return a > b

    def __ge__(self, other):
        # type: (Any) -> bool
        """Determine if the current version is higher or equal."""
        a, b = standardiseVersions(self, other)
        return a >= b

    def __lt__(self, other):
        # type: (Any) -> bool
        """Determine if the current version is lower."""
        a, b = standardiseVersions(self, other)
        return a < b

    def __le__(self, other):
        # type: (Any) -> bool
        """Determine if the current version is lower or equal."""
        a, b = standardiseVersions(self, other)
        return a <= b


class _Maya(object):
    """Singleton for accessing Maya application data."""

    @property
    def version(self):
        # type: () -> Version
        """Get the current Maya version."""
        return MayaVersion

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


Maya = _Maya()

MayaVersion = Version(VERSION)


# Handle circular dependencies
# pylint: disable=wrong-import-position
from .time import Time, _Time
