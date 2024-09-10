import maya.api.OpenMaya as om2  # type: ignore
import maya.cmds as mc  # type: ignore
import maya.mel as mel  # type: ignore


# Mapping of MEL to API types
MEL_API_TYPE = dict(
    transform=om2.MFn.kTransform,
    mesh=om2.MFn.kMesh,
    objectSet=om2.MFn.kSet,
    creaseSet=om2.MFn.kCreaseSet,
    animCurve=om2.MFn.kAnimCurve,
    shadingEngine=om2.MFn.kShadingEngine,
    light=om2.MFn.kLight,
    camera=om2.MFn.kCamera,
    reference=om2.MFn.kReference,
)

# MEL types that are valid DAG objects
DAG_TYPES = set(mc.nodeType('dagNode', derived=True, isTypeName=True))

# Startup cameras can't be renamed so just grab them once
STARTUP_CAMERAS = [cam for cam in mc.ls(type='camera') if mc.camera(cam, query=True, startupCamera=True)]
STARTUP_CAMERAS.extend(mc.listRelatives(STARTUP_CAMERAS, parent=True))

TIME_UNITS = {
    'game': 15,
    'film': 24,
    'pal': 25,
    '29.97df': 29.97,
    'ntsc': 30,
    'show': 48,
    'palf': 50,
    'ntscf': 60,
}
