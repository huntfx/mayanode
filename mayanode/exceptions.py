"""Custom exceptions for the module."""

import sys

from . import constants
from .type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List


if sys.version_info.major < 3:
    # pylint: disable=redefined-builtin
    class FileNotFoundError(OSError):
        """File not found."""


class BaseError(RuntimeError):
    MESSAGE = 'Error'

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        super(BaseError, self).__init__(self.MESSAGE.format(**self.kwargs))


class NullMObjectError(BaseError, TypeError):
    MESSAGE = 'This object is null'


class NodeError(BaseError):
    MESSAGE = 'Error: {node}'

    def __init__(self, node, **kwargs):
        super(NodeError, self).__init__(node=node, **kwargs)


class NodeNotFoundError(NodeError):
    MESSAGE = 'No node matches name: {node}'


class NodeDeletedError(NodeNotFoundError):
    MESSAGE = 'Node no longer exists: {node}'


class InvalidNodeError(NodeError):
    MESSAGE = '"{node}" is not valid'


class NotADagNodeError(NodeError):
    MESSAGE = '"{node}" is not a DAG node'


class NotACameraError(NodeError):
    MESSAGE = '"{node}" is not a camera'


class ReadOnlyNodeError(NodeError):
    MESSAGE = '"{node}" is read only'


class RenameReadOnlyNodeError(ReadOnlyNodeError):
    MESSAGE = 'Cannot rename "{node}" as it is read only'


class NodeAttributeError(NodeError):
    MESSAGE = 'Error: {node}.{attr}'

    def __init__(self, node, attr):
        super(NodeAttributeError, self).__init__(node, attr=attr)


class AttributeNotFoundError(NodeAttributeError):
    MESSAGE = 'The attribute "{node}.{attr}" was not found'


class AttributeLockedError(NodeAttributeError):
    MESSAGE = 'The attribute "{node}.{attr}" is locked and cannot be modified'


class AttributeConnectedError(NodeAttributeError):
    MESSAGE = 'The attribute "{node}.{attr}" is connected and cannot be modified'


class ConnectToSelfError(NodeAttributeError):
    MESSAGE = 'Cannot connect attribute "{node}.{attr}" to itself.'


class NoBoundingBoxError(NodeError):
    MESSAGE = '"{node}" has no bounding box'


class UVSetError(NodeError):
    MESSAGE = 'Error: {node}.uvSet[{uvSet}]'

    def __init__(self, node, uvSet):
        super(UVSetError, self).__init__(node, uvSet=uvSet)


class UVSetDeleteDefaultError(UVSetError):
    MESSAGE = 'The default UV set "{node}.{uvSet}" cannot be deleted.'


class UVSetNotFoundError(UVSetError):
    MESSAGE = 'The UV set "{node}.{uvSet}" was not found'


class ColorSetError(NodeError):
    MESSAGE = 'Error: {node}.colorSet[{colorSet}]'

    def __init__(self, node, colorSet):
        super(ColorSetError, self).__init__(node, colorSet=colorSet)


class ColorSetNotFoundError(ColorSetError):
    MESSAGE = 'The color set "{node}.{colorSet}" was not found'


class ZeroTexelDensityError(BaseError):
    MESSAGE = 'The texel density for "{faces}" is zero and cannot be updated.'

    def __init__(self, faces):
        super(ZeroTexelDensityError, self).__init__(faces=', '.join(faces))


class NamespaceError(BaseError):
    MESSAGE = 'Error: {namespace}'

    def __init__(self, namespace, **kwargs):
        super(NamespaceError, self).__init__(namespace=namespace, **kwargs)


class NamespaceNotFoundError(NamespaceError):
    MESSAGE = 'No namespace matches name: {namespace}'


class NamespaceNotEmptyError(NamespaceError):
    MESSAGE = 'The namespace "{namespace}" is not empty.'

    def __init__(self, namespace, **kwargs):
        super(NamespaceNotEmptyError, self).__init__(namespace=namespace, **kwargs)


class InvalidUuidError(BaseError):
    MESSAGE = '"{uuid}" is not a valid UUID'

    def __init__(self, uuid, **kwargs):
        super(NamespaceNotEmptyError, self).__init__(uuid=uuid, **kwargs)


class InvalidTimeUnitError(BaseError):
    MESSAGE = '"{unit}" is not a valid time unit'

    def __init__(self, unit, **kwargs):
        super(InvalidTimeUnitError, self).__init__(unit=unit, **kwargs)

    @property
    def allowed(self):
        # type: () -> List[str]
        """Get the allowed time units.."""
        return list(constants.TIME_UNITS)


class RequiresInteractiveError(BaseError):
    MESSAGE = 'this operation is not supported in batch mode'


class ReferenceError(BaseError):
    MESSAGE = 'error with reference "{reference}"'

    def __init__(self, reference, **kwargs):
        super(ReferenceError, self).__init__(reference=reference, **kwargs)


class ReferenceImportError(ReferenceError):
    MESSAGE = '"{reference}" cannot be imported'


class ReferenceNotTopLevelError(ReferenceImportError):
    MESSAGE = '"{reference}" cannot be imported as it is not a top level reference'


class ReferenceNotLoadedError(ReferenceImportError):
    MESSAGE = '"{reference}" cannot be imported as it is unloaded'


class FileInfoError(BaseError):
    MESSAGE = 'error with fileInfo'


class ReadOnlyFileInfoError(FileInfoError):
    MESSAGE = 'fileInfo {reason} and cannot be edited'

    def __init__(self, reason, **kwargs):
        super(ReadOnlyFileInfoError, self).__init__(reason=reason, **kwargs)


class MultipleFileInfoResultsError(FileInfoError):
    MESSAGE = 'more than one fileInfo value returned for "{key}"'

    def __init__(self, key, **kwargs):
        super(MultipleFileInfoResultsError, self).__init__(key=key, **kwargs)


class FileExtensionError(BaseError):
    MESSAGE = 'unexpected file extension (expected "ma" or "mb", got "{ext}")'

    def __init__(self, ext, **kwargs):
        super(FileExtensionError, self).__init__(ext=ext, **kwargs)
