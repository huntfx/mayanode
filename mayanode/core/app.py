import maya.api.OpenMaya as om2  # type: ignore


class _Maya(object):
    """Singleton for accessing Maya application data."""

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


Maya = _Maya()
