"""Wrapper to safely use the Maya profiler."""

import maya.OpenMaya as om  # type: ignore

from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType
    from typing import List, Optional, Type


class Profiler(object):
    """Safe way to handle profilers."""

    __slots__ = ['_id', '_category', '_info', '_color']

    def __init__(self, category, color=om.MProfiler.kColorE_L2, _info=None):
        # type: (str, int, Optional[str]) -> None
        self._id = None  # type: Optional[int]
        self._category = category
        self._info = _info
        self._color = color
        self.create()

    @classmethod
    def ls(self):
        # type: () -> List[Profiler]
        """Get all profilers/categories."""
        categoryNames = []  # type: List[str]
        categoryInfo = []  # type: List[str]
        om.MProfiler.getAllCategories(categoryNames, categoryInfo)
        return [Profiler(name, _info=info) for name, info in zip(categoryNames, categoryInfo)]

    def __call__(self, name):
        # type: (str) -> Event
        """Create a profile event in a context manager."""
        return Event(self._id, self._color, name)

    @property
    def info(self):
        # type: () -> str
        """Get the profiler category information."""
        if self._info is None:
            self._info = om.MProfiler.getCategoryInfo(self._id)
        return self._info

    def create(self):
        # type: () -> None
        """Create the profiler category."""
        self._id = om.MProfiler.addCategory(self._category)

    def delete(self):
        # type: () -> bool
        """Delete the profiler category.

        Returns if the category was successfully deleted.
        Note that this does not do anything for me.
        """
        return om.MProfiler.removeCategory(self._id) > 0


class Event(object):
    """Context manager for a profiler event.

    Note that from a quick test, constructing this class is roughly
    twice as fast as using `contextlib.contextmanager`, with 800k calls
    per second. It is still about 5x slower than directly calling the
    `eventBegin` and `eventEnd` methods.
    """

    __slots__ = ['_id', '_category', '_color', '_name']

    def __init__(self, category, color, name):
        # type: (Optional[int], int, str) -> None
        self._id = None
        self._category = category
        self._color = color
        self._name = name

    def __enter__(self):
        # type: () -> Event
        self.begin()
        return self

    def __exit__(self, excType, excVal, excTraceback):
        # type: (Optional[Type[Exception]], Optional[Exception], Optional[TracebackType]) -> bool
        self.end()
        return excVal is None

    def begin(self):
        # type: () -> None
        """Start recording the event."""
        self._id = om.MProfiler.eventBegin(self._category, self._color, self._name)

    def end(self):
        # type: () -> None
        """End the event recording."""
        if self._id is not None:
            om.MProfiler.eventEnd(self._id)


profiler = Profiler('mayanode')
