from collections import namedtuple
from typing import *


GlobalReloc = namedtuple('GlobalReloc', ['name', 'pos'])


class Object:

    def __init__(self, bytes, global_relocs, local_relocs, globals):
        self._bytes: bytearray = bytes
        self._global_relocs: List[GlobalReloc] = global_relocs
        self._local_relocs: List[int] = local_relocs
        self._globals: Dict[str, int] = globals

    def get_bytes(self):
        """
        The actual code of the object file
        """
        return self._bytes

    def get_global_relocs(self):
        """
        A list of all the global relocations in this file

        when linking the value should be filled with the
        """
        return self._global_relocs

    def get_local_relocs(self):
        return self._local_relocs

    def get_globals(self):
        return self._globals
