from functools import wraps

import maya.cmds as mc  # type: ignore

from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable, Type


class UndoChunk(object):
    """Batch commands together in an undo chunk.
    Works as both a wrapper and context manager.
    """

    def __call__(self, fn):
        # type: (Callable) -> Callable
        """Add as a function wrapper."""
        @wraps(fn)
        def wrapper(*args, **kwargs):
            with type(self)():
                return fn(*args, **kwargs)
        return wrapper

    def __enter__(self):
        # type: () -> UndoChunk
        """Open the chunk."""
        mc.undoInfo(openChunk=True)
        return self

    def __exit__(self, *args):
        # type: (*Any) -> bool
        """Close the chunk."""
        mc.undoInfo(closeChunk=True)
        return not any(args)


class _Undo(object):
    """Singleton for accessing undo related commands.

    TODO: Tests
    """

    @property
    def chunk(self):
        # type: () -> Type[UndoChunk]
        """Open an undo chunk or wrap a function."""
        return UndoChunk

    @property
    def enabled(self):
        # type: () -> bool
        """Determine if the undo queue is enabled."""
        return mc.undoInfo(query=True, state=True)

    @enabled.setter
    def enabled(self, enable):
        # type: (bool) -> None
        """Enable or disable the undo queue."""
        if enable:
            self.enable()
        else:
            self.disable()

    def enable(self):
        # type: () -> None
        """Enable the undo queue."""
        mc.undoInfo(query=True, state=True)

    def disable(self):
        # type: () -> None
        """Disable the undo queue."""
        mc.undoInfo(query=True, state=False)

    @property
    def length(self):
        # type: () -> int
        """Get the length of the undo queue.
        If infinite then -1 will be returned.
        """
        if mc.undoInfo(query=True, infinity=True):
            return -1
        return mc.undoInfo(query=True, length=True)

    @length.setter
    def length(self, length):
        # type: (int) -> None
        """Set the new undo queue length.
        Set to a negative number for infinite length.
        """
        if length < 0:
            mc.undoInfo(infinity=True)
        else:
            mc.undoInfo(infinity=False, length=length)

    def undo(self):
        # type: () -> bool
        """Undo the last command."""
        if mc.undoInfo(undoQueueEmpty=True):
            return False
        mc.undo()
        return True

    def redo(self):
        # type: () -> bool
        """Redo the last command."""
        if mc.undoInfo(redoQueueEmpty=True):
            return False
        mc.redo()
        return True

    def clear(self):
        # type: () -> None
        """Clear the undo queue."""
        mc.flushUndo()


Undo = _Undo()
