import maya.api.OpenMaya as om2

from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Literal, Type


class _MayaNode(object):
    """Handle runtime global variables for the mayanode module.

    This allows temporary overrides using context managers, where the
    variables are resolved in a stack based hierarchy, and can be read
    by other classes.

    Example:
        >>> dgm1 = om2.MDGModifier()
        >>> dgm2 = om2.MDGModifier()
        >>> dgm3 = om2.MDGModifier()

        >>> MayaNode.dgModifier = om2.MDGModifier()
        >>> assert MayaNode.dgModifier == dgm1

        >>> with MayaNode() as context:
        ...     context.dgModifier = dgm2
        ...     with MayaNode() as subcontext:
        ...         subcontext.dgModifier = dgm3
        ...         assert MayaNode.dgModifier == dgm3
        ...         assert context.dgModifier == dgm2
        ...     assert MayaNode.dgModifier == dgm2
        >>> assert MayaNode.dgModifier == dgm1
    """

    __slots__ = ['_dgModifier', '_dagModifier']

    _Stack = []  # type: list[_MayaNode]

    def __init__(self):
        # type: () -> None
        self._dgModifier = None  # type: om2.MDGModifier | None
        self._dagModifier = None  # type: om2.MDagModifier | None

    @property
    def dgModifier(self):
        # type: () -> om2.MDGModifier | None
        """Get the DG modifier for the current context.
        If in the global context, then get the DG modifier of the
        latest context instead.
        """
        if self is self._Stack[0]:
            for item in reversed(self._Stack):
                if item._dgModifier is not None:
                    return item._dgModifier
        return self._dgModifier

    @dgModifier.setter
    def dgModifier(self, dgModifier):
        # type: (om2.MDGModifier | None) -> None
        """Set the DG modifier for this context.

        This is very efficient but does not work with undo, so it should
        be used with care.
        """
        self._dgModifier = dgModifier

    @property
    def dagModifier(self):
        # type: () -> om2.MDagModifier | None
        """Get the DAG modifier for the current context.
        If in the global context, then get the DAG modifier of the
        latest context instead.
        """
        if self is self._Stack[0]:
            for item in reversed(self._Stack):
                if item._dagModifier is not None:
                    return item._dagModifier
        return self._dagModifier

    @dagModifier.setter
    def dagModifier(self, dagModifier):
        # type: (om2.MDagModifier | None) -> None
        """Set the DAG modifier for this context.

        This is very efficient but does not work with undo, so it should
        be used with care.
        """
        self._dagModifier = dagModifier

    @property
    def modifier(self):
        # type: () -> om2.MDagModifier | om2.MDGModifier | None
        """Get the DG or DAG modifier for the current context.
        This should be used when either is valid, as it will prioritise
        the latest context.
        """
        if self is self._Stack[0]:
            for item in reversed(self._Stack):
                if item._dagModifier is not None:
                    return item._dagModifier
                if item._dgModifier is not None:
                    return item._dgModifier
        if self._dagModifier is not None:
            return self._dagModifier
        return self._dgModifier

    def __call__(self):
        # type: () -> _MayaNode
        """Create a new context manager."""
        return _MayaNode()

    def __enter__(self):
        # type: () -> _MayaNode
        """Enter a new context, pushing this instance onto the stack."""
        self._Stack.append(self)
        return self

    def __exit__(self, excType, excVal, excTraceback):
        # type: (Type[Exception] | None, Exception | None, TracebackType | None) -> Literal[False]
        """Exit the current context, removing this instance from the stack."""
        self._Stack.pop()
        return False


MayaNode = _MayaNode()
_MayaNode._Stack.append(MayaNode)
