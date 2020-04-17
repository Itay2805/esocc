from typing import *
from enum import Enum, auto


class StorageClass(Enum):
    AUTO = auto()
    STATIC = auto()
    REGISTER = auto()
    EXTERN = auto()


class CType:

    def __init__(self):
        pass

    def __ne__(self, other):
        return not (self == other)

    def is_complete(self):
        return NotImplemented

    def sizeof(self):
        return NotImplemented


class CInteger(CType):

    def __init__(self, bits: int, signed: bool):
        super(CInteger, self).__init__()
        self.bits = bits
        self.signed = signed

    def __eq__(self, other):
        if isinstance(other, CInteger):
            return self.signed == other.signed and self.bits == other.bits
        return False

    def sizeof(self):
        return self.bits // 16

    def __str__(self):
        if not self.signed:
            if self.bits == 16:
                return 'unsigned int'
            else:
                assert False
        else:
            if self.bits == 16:
                return 'int'
            else:
                assert False

    def is_complete(self):
        return True


class CPointer(CType):

    def __init__(self, typ: CType):
        super(CPointer, self).__init__()
        self.type = typ

    def sizeof(self):
        return 1

    def __eq__(self, other):
        if isinstance(other, CPointer):
            return other.type == self.type
        return False

    def __str__(self):
        # TODO: show the pointer type properly for functions
        return str(self.type) + '*'

    def is_complete(self):
        return True


class CVoid(CType):

    def __init__(self):
        super(CVoid, self).__init__()

    def __eq__(self, other):
        return isinstance(other, CVoid)

    def sizeof(self):
        assert False

    def __str__(self):
        return 'void'

    def is_complete(self):
        return False


class CallConv(Enum):
    STACKCALL = auto()
    REGCALL = auto()
    INTERRUPT = auto()


class CFunction(CType):

    def __init__(self):
        super(CFunction, self).__init__()
        self.callconv = None
        self.ret_type = CVoid()  # type: CType
        self.param_types = []  # type: List[CType]

    def sizeof(self):
        return 1

    def __str__(self):
        args = ', '.join(map(str, self.param_types))
        return f'{self.ret_type} (*)({args})'

    def is_complete(self):
        return True


class CArray(CType):

    def __init__(self, typ: CType, len: int or None):
        super(CArray, self).__init__()
        self.type = typ
        self.len = len

    def sizeof(self):
        assert self.is_complete()
        return self.len * self.type.sizeof()

    def is_complete(self):
        return self.len is not None and self.type.is_complete()

    def __str__(self):
        if self.len is None:
            return f'{self.type}[]'
        else:
            return f'{self.type}[{self.len}]'


def _align(base, size):
    if base % size != 0:
        base += size - base % size
    return base


class CStruct(CType):

    def __init__(self, name: str, name_pos):
        super(CStruct, self).__init__()
        self.name = name
        self.packed = 0
        self.union = False
        self.pos = name_pos
        self.items = {}  # type: Dict[str, CType]

    def offsetof(self, name):
        if self.union:
            return 0
        else:
            offset = 0
            for item in self.items:
                if item == name:
                    return offset

                if self.packed:
                    offset += self.items[item].sizeof()
                else:
                    offset += _align(offset, self.items[item].sizeof()) + self.items[item].sizeof()

            return None

    def sizeof(self):
        s = 0
        if self.union:
            # For union the size is the max size
            for name in self.items:
                s = max(self.items[name].sizeof(), s)
        else:
            # For struct the size is the su
            for name in self.items:
                s += self.items[name].sizeof()
        return s

    def is_complete(self):
        return self.items is not None

    def __str__(self):
        name = self.name
        if name is None:
            name = ''
        else:
            name = ' ' + name
        return f'struct{name}'
