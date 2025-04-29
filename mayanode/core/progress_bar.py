"""Wrapper over Maya's main progress bar.

Example:
    >>> ProgressBar.interruptable = True
    >>> ProgressBar.maxValue = 1000
    >>> with ProgressBar:
    ...     ProgressBar.status = 'Starting...'
    ...     while not ProgressBar.interrupted and ProgressBar.value < ProgressBar.max:
    ...         if ProgressBar.value > 500:
    ...             ProgressBar.status = 'Halfway there!'
    ...         ProgressBar.value += 1
"""

import maya.cmds as mc  # type: ignore

from .. import exceptions, types, utils
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Iterator, Type, TypeVar
    T = TypeVar('T')


class _ProgressBar(types.StrMixin):

    __slots__ = ['_name']

    def __init__(self, name=None):
        # type: (str | None) -> None
        if name is None:
            try:
                name = utils.getMelGlobal('MainProgressBar')
            except exceptions.RequiresInteractiveError:
                name = ''
        self._name = name

    @property
    def name(self):
        # type: () -> str
        """Get the progress bar name."""
        return self._name

    def __enter__(self):
        # type: () -> _ProgressBar
        """Use the progress bar as a context manager."""
        self.show()
        return self

    def __exit__(self, excType, excVal, excTraceback):
        # type: (Type[Exception] | None, Exception | None, TracebackType | None) -> bool
        """Use the progress bar as a context manager."""
        self.hide()
        return excType is excVal is excTraceback is None

    def show(self):
        # type: () -> None
        """Show the progress bar.
        This will not set the current value to the minumum.
        """
        mc.progressBar(self, edit=True, beginProgress=True)

    def hide(self):
        # type: () -> None
        """Hide the progress bar once it is complete."""
        mc.progressBar(self, edit=True, endProgress=True)

    @property
    def status(self):
        # type: () -> str
        """Get the current progress bar status message."""
        return mc.progressBar(self, query=True, status=True)

    @status.setter
    def status(self, status):
        # type: (str) -> None
        """Set the progress bar status message."""
        mc.progressBar(self, edit=True, status=status)

    @property
    def interruptable(self):
        # type: () -> bool
        """Determine if the operation is interruptable."""
        return mc.progressBar(self, query=True, isInterruptable=True)

    @interruptable.setter
    def interruptable(self, interruptable):
        # type: (bool) -> None
        """Set if the operation should be interruptable."""
        mc.progressBar(self, edit=True, isInterruptable=interruptable)

    @property
    def interrupted(self):
        # type: () -> bool
        """Determine if the operation has been interrupted/cancelled."""
        return mc.progressBar(self, query=True, isCancelled=True)

    @property
    def min(self):
        # type: () -> int
        """Get the minimum progress bar value."""
        return mc.progressBar(self, query=True, minValue=True)

    @min.setter
    def min(self, value):
        # type: (int) -> None
        """Set the minimum progress bar value.

        Raises:
            RuntimeError: Maximum value must be greater than minimum value.
        """
        mc.progressBar(self, edit=True, minValue=value)

    @property
    def max(self):
        # type: () -> int
        """Get the maximum progress bar value."""
        return mc.progressBar(self, query=True, maxValue=True)

    @max.setter
    def max(self, value):
        # type: (int) -> None
        """Set the maximum progress bar value.

        Raises:
            RuntimeError: Maximum value must be greater than minimum value.
        """
        mc.progressBar(self, edit=True, maxValue=value)

    @property
    def limits(self):
        # type: () -> tuple[int, int]
        """Get the minimum and maximum progress bar values."""
        return (self.min, self.max)

    @limits.setter
    def limits(self, limits):
        # type: (tuple[int, int]) -> None
        """Set the minimum and maximum progress bar values."""
        minValue, maxValue = limits
        mc.progressBar(self, edit=True, minValue=minValue, maxValue=maxValue)

    @property
    def value(self):
        # type: () -> int
        """Get the progress value."""
        return mc.progressBar(self, query=True, progress=True)

    @value.setter
    def value(self, value):
        # type: (int) -> None
        """Set a new progress value."""
        mc.progressBar(self, edit=True, progress=value)

    def step(self, value=1):
        # type: (int) -> None
        """Move the progress value by a step."""
        self.value += value

    def range(self, start, end=None, step=1):
        # type: (int, int | None, int) -> Iterator[int]
        """Wrap the progress bar with a `range()` call."""
        if end is None:
            start, end = 0, start

        old = self.value, self.min, self.max

        try:
            self.limits = (start, end)
            self.value = start
            with self:
                for i in range(start, end, step):
                    self.value = i
                    yield i

        finally:
            self.value, self.min, self.max = old

    def enumerate(self, iterator, start=0):
        # type: (Iterator[T], int) -> Iterator[tuple[int, T]]
        """Wrap the progress bar with an `enumerate()` call."""
        old = self.value, self.min, self.max
        data = tuple(iterator)
        if not data:
            return

        try:
            self.limits = (start, len(data) + start)
            self.value = 0
            with self:
                for i, val in enumerate(data, start):
                    self.value = i
                    yield i, val

        finally:
            self.value, self.min, self.max = old


ProgressBar = _ProgressBar()
