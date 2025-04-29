import re

from .type_hints import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, TypeVar, Union

    Token = Union[int, '_StrCmp']
    TokenisedVersion = list[Token]
    StandardisedToken = TypeVar('StandardisedToken', Token, TokenisedVersion)
    StandardisedVersion = tuple[StandardisedToken, StandardisedToken]


class _StrCmp(str):
    """Python 2 compatibility class to allow string comparisons."""

    def __gt__(self, other):
        # type: (Any) -> bool
        if isinstance(other, (int, float)):
            return True
        return super(_StrCmp, self).__gt__(str(other))

    def __ge__(self, other):
        # type: (Any) -> bool
        if isinstance(other, (int, float)):
            return True
        return super(_StrCmp, self).__ge__(str(other))

    def __lt__(self, other):
        # type: (Any) -> bool
        if isinstance(other, (int, float)):
            return False
        return super(_StrCmp, self).__lt__(str(other))

    def __le__(self, other):
        # type: (Any) -> bool
        if isinstance(other, (int, float)):
            return False
        return super(_StrCmp, self).__le__(str(other))


def tokeniseVersion(version, ignoreV=True):
    # type: (Any, bool) -> TokenisedVersion
    """Take a version string and split it into tokens of ints and strings.

    Parameters:
        version: Application version number.
        ignoreV: Ignore `v` if it is the first letter.
            This means `v1.2` will be tokenised as `[1, 2]` rather than
            `['v', 1, 2]`.
    """
    result = []  # type: TokenisedVersion
    for i, token in enumerate(re.split(r'(\.+)', str(version))[::2]):
        if token.isdigit():
            result.append(int(token))
            continue

        subtokens = re.split(r'(\d+)', token)

        # If any token but the first starts with letter then treat as a word
        if i and subtokens[0]:
            result.append(_StrCmp(token))
            continue

        numTokens = len(subtokens)

        # Single letter
        if numTokens == 1:
            result.append(_StrCmp(token))
            continue

        # If the first token starts with a letter that isn't "v"
        if not i and subtokens[0] and (not ignoreV or subtokens[0].lower() != 'v'):
            result.append(_StrCmp(subtokens[0]))

        # Get all integers
        result.extend(int(t) for t in subtokens[1::2])

        # Add on final letter if applicable
        if subtokens[-1]:
            result.append(_StrCmp(subtokens[-1]))
    return result


def standardiseVersions(a, b):
    # type: (Any, Any) -> StandardisedVersion
    """Take two versions and return their standardised values.
    These should only be used for comparison operations, as the return
    types are varied and the implementation may be subject to change.

    Note that varied version separators such as `1.5v2` are treated like
    `1.5.2` for the sake of simplicity.
    """
    # Do a check on int/float only to map all else to str
    aIsStr = not isinstance(a, (int, float))
    bIsStr = not isinstance(b, (int, float))

    if aIsStr:
        a = _StrCmp(a)
        if a.isdigit():
            a = int(a)
            aIsStr = False
        elif re.match(r'-?\d+\.\d+$', a):
            a = float(a)
            aIsStr = False

    if bIsStr:
        b = _StrCmp(b)
        if b.isdigit():
            b = int(b)
            bIsStr = False
        elif re.match(r'-?\d+\.\d+$', b):
            b = float(b)
            bIsStr = False

    # Types match
    if not aIsStr and not bIsStr:
        if type(a) == type(b):
            return a, b
        return int(a), int(b)

    # Split any text into tokens
    # This will result in [prefix, num, separator, ..., suffix], so length 5 for a float
    aTokens = [] if not aIsStr else tokeniseVersion(str(a))  # type: TokenisedVersion
    aTokenInts = [token for token in aTokens if isinstance(token, int)]  # type: TokenisedVersion
    bTokens = [] if not bIsStr else tokeniseVersion(str(b))  # type: TokenisedVersion
    bTokenInts = [token for token in bTokens if isinstance(token, int)]  # type: TokenisedVersion

    # If inputs are both strings, then return tokens of the same length
    if aTokens and bTokens:
        tokenLen = min(len(aTokens), len(bTokens))
        return aTokens[:tokenLen], bTokens[:tokenLen]

    # Attempt to map both to float/int
    if isinstance(a, float):
        if not bTokenInts:
            return int(a), bTokens[0]
        if len(bTokenInts) >= 2:
            aTokenInts[:] = [int(x) for x in str(a).split('.')]
            return aTokenInts, bTokenInts[:2]
        return int(a), bTokenInts[0]
    if isinstance(a, int):
        if bTokenInts:
            return a, bTokenInts[0]
        if bTokens:
            return a, bTokens[0]
    if isinstance(b, float):
        if not aTokenInts:
            return aTokens[0], int(b)
        if len(aTokenInts) >= 2:
            bTokenInts[:] = [int(x) for x in str(b).split('.')]
            return aTokenInts[:2], bTokenInts
        return aTokenInts[0], int(b)
    if isinstance(b, int):
        if aTokenInts:
            return aTokenInts[0], b
        if aTokens:
            return aTokens[0], b

    raise ValueError('version mapping failed')


class Version(str):
    """Compare version data.
    Advanced comparisons are supported.
    """

    def __init__(self, version):
        # type: (str) -> None
        self.major, self.minor, self.patch = version.split('.')

    def __int__(self):
        # type: () -> int
        """Get the major version number."""
        return int(self.major)

    def __float__(self):
        # type: () -> float
        """Get the major and minor version number."""
        return float('{}.{}'.format(self.major, self.minor))

    def __eq__(self, other):
        # type: (Any) -> bool
        """Determine if two versions are equal."""
        a, b = standardiseVersions(self, other)
        return a == b

    def __ne__(self, other):
        # type: (Any) -> bool
        """Determine if two versions are not equal."""
        a, b = standardiseVersions(self, other)
        return a != b

    def __gt__(self, other):
        # type: (Any) -> bool
        """Determine if the current version is higher."""
        a, b = standardiseVersions(self, other)
        return a > b

    def __ge__(self, other):
        # type: (Any) -> bool
        """Determine if the current version is higher or equal."""
        a, b = standardiseVersions(self, other)
        return a >= b

    def __lt__(self, other):
        # type: (Any) -> bool
        """Determine if the current version is lower."""
        a, b = standardiseVersions(self, other)
        return a < b

    def __le__(self, other):
        # type: (Any) -> bool
        """Determine if the current version is lower or equal."""
        a, b = standardiseVersions(self, other)
        return a <= b
