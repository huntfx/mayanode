"""Wrapper to safely use the Maya profiler."""

import maya.cmds as mc  # type: ignore
import maya.OpenMaya as om  # type: ignore

from .. import types
from ..ext import classutilities
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType
    from typing import List, Optional, Type
    from ..type_hints import StrLike


class Profiler(types.StrMixin):
    """Safe way to handle profilers."""

    __slots__ = ['_id', '_category', '_info', '_color']

    def __init__(self, category, color=om.MProfiler.kColorE_L2, _info=None):
        # type: (StrLike, int, Optional[str]) -> None
        self._id = None  # type: Optional[int]
        self._category = str(category)
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

    @classutilities.classproperty
    def start(self):
        # type: () -> None
        """Start the profiler."""
        mc.profiler(sampling=True)

    @classutilities.classproperty
    def stop(self):
        # type: () -> None
        """Stop the profiler."""
        mc.profiler(sampling=False)

    def __call__(self, name, description=None):
        # type: (str, Optional[str]) -> Event
        """Create a profile event in a context manager.

        From a quick test, constructing a class is roughly twice as
        fast as using `contextlib.contextmanager`, with 800k calls per
        second. It is still about 5x slower than directly calling the
        `eventBegin` and `eventEnd` methods.
        """
        return Event(self._id, self._color, name, description)

    def signal(self, name, description=None):
        # type: (str, Optional[str]) -> None
        """Send out a profiling signal.
        This can be used when the duration does not matter.
        """
        om.MProfiler.signalEvent(self._id, self._color, name, description)

    @property
    def id(self):
        # type: () -> Optional[int]
        """Get the category ID."""
        if self._id < 0:
            return None
        return self._id

    @property
    def name(self):
        # type: () -> str
        """Get the category name."""
        return self._category

    @property
    def info(self):
        # type: () -> str
        """Get the category information."""
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


class Event(types.StrMixin):
    """Context manager for a profiler event.

    Note that either making too many events or wrapping certain
    functions appears to result in the event names going a bit haywire.
    I tested `assert eventName == om.MProfiler.getEventName(event.id)`
    but it always passed, so it appears to be some sort of memory error.
    """

    __slots__ = ['_id', '_category', '_color', '_name', '_description']

    def __init__(self, category, color, name, description=None):
        # type: (int, int, str, Optional[str]) -> None
        self._id = -1
        self._category = category
        self._color = color
        self._name = str(name)
        self._description = str(description) if description else None

    def __bool__(self):
        # type: () -> bool
        """Determine if the event is valid."""
        return self._id >= 0
    __nonzero__ = __bool__

    def __enter__(self):
        # type: () -> Event
        self.begin()
        return self

    def __exit__(self, excType, excVal, excTraceback):
        # type: (Optional[Type[Exception]], Optional[Exception], Optional[TracebackType]) -> bool
        self.end()
        return excType is excVal is excTraceback is None

    @property
    def id(self):
        # type: () -> Optional[int]
        """Get the event ID."""
        if self._id < 0:
            return None
        return self._id

    @property
    def name(self):
        # type: () -> str
        """Get the event name."""
        eventID = self.id
        if eventID is None:
            return self._name
        return om.MProfiler.getEventName(eventID)

    @property
    def description(self):
        # type: () -> Optional[str]
        """Get the event name."""
        eventID = self.id
        if eventID is None:
            return self._description
        return om.MProfiler.getDescription(eventID) or None

    def begin(self):
        # type: () -> None
        """Start recording the event."""
        self._id = om.MProfiler.eventBegin(self._category, self._color, self._name, self._description)

    def end(self):
        # type: () -> None
        """End the event recording."""
        eventID = self.id
        if eventID is not None:
            om.MProfiler.eventEnd(eventID)


profiler = Profiler('mayanode')
