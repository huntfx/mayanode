import maya.cmds as mc  # type: ignore

from .. import constants, exceptions, utils
from ..type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional, Tuple


class _Time(object):
    @property
    def current(self):
        # type: () -> float
        """Get the current time of the scene."""
        return mc.currentTime(query=True)

    @current.setter
    def current(self, frame):
        # type: (float) -> None
        """Set the current time of the scene."""
        mc.currentTime(frame)

    @property
    def unit(self):
        # type: () -> str
        """Get the current time unit."""
        return mc.currentUnit(query=True, time=True)

    @unit.setter
    def unit(self, unit):
        # type: (str) -> None
        """Set the current time unit.

        Raises:
            InvalidTimeUnitError
        """
        try:
            mc.currentUnit(time=unit)
        except RuntimeError:
            raise exceptions.InvalidTimeUnitError(unit)

    @property
    def fps(self):
        # type: () -> float
        """Get the scene framerate.
        If the framerate has a relative override, then the correct offset
        can be calculated with "offset *= framerate/6000".
        """
        unit = self.unit
        if unit in constants.TIME_UNITS:
            return constants.TIME_UNITS[unit]
        return float(unit[:-3])

    @property
    def playbackStart(self):
        # type: () -> float
        """Get the playback start time."""
        return mc.playbackOptions(query=True, minTime=True)

    @playbackStart.setter
    def playbackStart(self, minTime):
        # type: (float) -> None
        """Set the playback start time."""
        utils.logger.info('Setting playback start time to %s', minTime)
        mc.playbackOptions(minTime=minTime)

    @property
    def playbackEnd(self):
        # type: () -> float
        """Get the playback end time."""
        return mc.playbackOptions(query=True, maxTime=True)

    @playbackEnd.setter
    def playbackEnd(self, maxTime):
        # type: (float) -> None
        """Set the playback end time."""
        utils.logger.info('Setting playback end time to %s', maxTime)
        mc.playbackOptions(maxTime=maxTime)

    @property
    def animationStart(self):
        # type: () -> float
        """Get the animation start time."""
        return mc.playbackOptions(query=True, animationStartTime=True)

    @animationStart.setter
    def animationStart(self, animationStartTime):
        # type: (float) -> None
        """Set the animation start time."""
        utils.logger.info('Setting animation start time to %s', animationStartTime)
        mc.playbackOptions(animationStartTime=animationStartTime)

    @property
    def animationEnd(self):
        # type: () -> float
        """Get the animation end time."""
        return mc.playbackOptions(query=True, animationEndTime=True)

    @animationEnd.setter
    def animationEnd(self, animationEndTime):
        # type: (float) -> None
        """Set the animation end time."""
        utils.logger.info('Setting animation end time to %s', animationEndTime)
        mc.playbackOptions(animationEndTime=animationEndTime)

    @property
    def start(self):
        # type: () -> float
        """Get the animation start time."""
        return self.animationStart

    @start.setter
    def start(self, startTime):
        # type: (float) -> None
        """Set both the minimum time and animation start time."""
        utils.logger.info('Setting start time to %s', startTime)
        mc.playbackOptions(minTime=startTime, animationStartTime=startTime)

    @property
    def end(self):
        # type: () -> float
        """Get the animation end time."""
        return self.animationEnd

    @end.setter
    def end(self, endTime):
        # type: (float) -> None
        """Set both the maximum time and and animation end time."""
        utils.logger.info('Setting end time to %s', endTime)
        mc.playbackOptions(maxTime=endTime, animationEndTime=endTime)

    @property
    def playing(self):
        # type: () -> bool
        """Determine if the scene is playing back."""
        return mc.play(query=True, state=True)

    @playing.setter
    def playing(self, state):
        # type: (bool) -> None
        """Set the playback state."""
        utils.logger.info('Setting playback state to %s', state)
        mc.play(state=state)

    def play(self):
        # type: () -> None
        """Start the playback."""
        mc.play(state=True)

    def stop(self):
        # type: () -> None
        """Start the playback."""
        mc.play(state=False)

    @property
    def selection(self):
        # type: () -> Optional[Tuple[float, float]]
        """Get the selected time range."""
        if mc.timeControl(constants.gPlayBackSlider, rangeVisible=True, query=True):
            return mc.timeControl(constants.gPlayBackSlider, rangeArray=True, query=True)
        return None


Time = _Time()
