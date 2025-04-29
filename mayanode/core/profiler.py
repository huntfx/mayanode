# pylint: disable=useless-object-inheritance
"""Wrapper to safely use the Maya profiler.

The access is provided through the `Profiler` singleton, rather than
the `Category` and `Event` classes.

Example:
    # To wrap blocks of code in the profiler
    >>> profiler = Profiler('mayanode')
    >>> with profiler('createCube') as event:
    ...     mc.polyCube()
    >>> profiler.signal('scriptFinished')

    To wrap a function
    >>> @profiler.attach
    ... def createCube():
    ...     mc.polyCube()

    # To automatically start and stop the profiler
    >>> with Profiler.category('mayanode') as profiler:
    ...     with profiler.event('createCube') as event
    ...         mc.polyCube()
    ...      profiler.signal('scriptFinished')

    # Class methods
    >>> Profiler.running
    False
    >>> Profiler.ls()
    [Category('Main'), Category('Evaluation'), Category('Qt'), ...]

    # Access data (WARNING: events must be in scope or it'll crash)
    >>> profiler.name
    'mayanode'
    >>> Profiler.category('Main').info
    'Catch-all for main thread events'
    >>> event.name
    'createCube'
    >>> event.description
    ''

TODO:
    Change `Profiler.category(name)` to `Profiler.categories[name]`
"""

from contextlib import contextmanager
from functools import wraps

import maya.cmds as mc  # type: ignore
import maya.OpenMaya as om  # type: ignore

from .. import types
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Callable, Iterator, Type
    from ..type_hints import StrLike


class _Profiler(object):
    # pylint: disable=no-self-use
    """Singleton base class for the profiler."""

    __slots__ = ['profiler']

    def ls(self):
        # type: () -> list[Category]
        """Get all profilers/categories."""
        categoryNames = []  # type: list[str]
        categoryInfo = []  # type: list[str]
        om.MProfiler.getAllCategories(categoryNames, categoryInfo)
        return [Category(name, _info=info) for name, info in zip(categoryNames, categoryInfo)]

    @property
    def running(self):
        # type: () -> bool
        """Determine if the profiler is running."""
        return mc.profiler(query=True, sampling=True)

    @running.setter
    def running(self, value):
        # type: (bool) -> None
        """Set a new profiler running state."""
        if value:
            self.start()
        else:
            self.stop()

    def start(self):
        # type: () -> None
        """Start the profiler."""
        mc.profiler(sampling=True)

    def stop(self):
        # type: () -> None
        """Stop the profiler."""
        mc.profiler(sampling=False)

    @contextmanager
    def record(self):
        # type: () -> Iterator[None]
        """Run the profiler on a block of code.
        If the profiler is already running then nothing will happen.
        """
        running = self.running
        if not running:
            self.running = True
        try:
            yield
        finally:
            if not running:
                self.running = False

    def category(self, name, color=om.MProfiler.kColorE_L2):
        # type: (str, int) -> Category
        return Category(name, color)


class Category(types.StrMixin):
    """Safe way to handle profilers."""

    __slots__ = ['_id', '_category', '_info', '_color']

    _RUNNING = False

    def __init__(self, name, color=om.MProfiler.kColorE_L2, _info=None):
        # type: (StrLike, int, str | None) -> None
        self._id = -1
        self._category = str(name)
        self._info = _info
        self._color = color
        self.create()

    def event(self, name, description=None):
        # type: (str, str | None) -> Event
        """Create a profile event."""
        return Event(self._id, self._color, name, description)

    def signal(self, name, description=None):
        # type: (str, str | None) -> None
        """Send out a profiling signal.
        This can be used when the duration does not matter.
        """
        om.MProfiler.signalEvent(self._id, self._color, name, description)

    @property
    def id(self):
        # type: () -> int | None
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

    def attach(self, func):
        # type: (Callable) -> Callable
        """Attach the profiler to a function."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self.event('{}::{}'.format(func.__module__, func.__name__)):
                return func(*args, **kwargs)
        return wrapper


class Event(types.StrMixin):
    """Context manager for a profiler event.

    Note that either making too many events or wrapping certain
    functions appears to result in the event names going a bit haywire.
    I tested `assert eventName == om.MProfiler.getEventName(event.id)`
    but it always passed, so it appears to be some sort of memory error.
    """

    __slots__ = ['_id', '_category', '_color', '_name', '_description']

    def __init__(self, category, color, name, description=None):
        # type: (int, int, str, str | None) -> None
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
        # type: (Type[Exception] | None, Exception | None, TracebackType | None) -> bool
        self.end()
        return excType is excVal is excTraceback is None

    @property
    def id(self):
        # type: () -> int | None
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
        # type: () -> str | None
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


Profiler = _Profiler()

profiler = Profiler.category('mayanode')
