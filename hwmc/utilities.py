"""Some utilities for the hwmc package"""

from hwmc.common import Config


def vprint(*args):
    """Print information only if in verbose mode

    Args:
        *args (object): Information to be printed. Same rules as 'print'.
    """
    if Config.VERBOSE is True:
        try:
            print(*args)
        except (TypeError, ValueError):
            pass
