from enum import Enum, auto
from typing import List


BasicBlockId = int
"""
Used to identify basic blocks.
"""


class IrOpcodeClass(Enum):
    # anything else
    NONE = auto()

    # dest = op? a
    ASSIGN2 = auto()

    # dest = a op b
    ASSIGN3 = auto()

    # op a
    USE1 = auto()

    # op a, b
    USE2 = auto()

    # dest = call a (extra...)
    ASSIGN_CALL = auto()

    # dest = op a (extra...)
    ASSIGN_FIXED_CALL = auto()

    # call a (extra...)
    CALL = auto()


class IrOpcode(Enum):
    """
    Enumeration of IR instruction opcodes.
    """

    UNDEF = auto()

    # assign
    ASSIGN = auto()

    # unsigned arith operations
    ASSIGN_ADD = auto()
    ASSIGN_SUB = auto()
    ASSIGN_MUL = auto()
    ASSIGN_DIV = auto()
    ASSIGN_MOD = auto()

    # signed arith operations
    ASSIGN_SIGNED_ADD = auto()
    ASSIGN_SIGNED_SUB = auto()
    ASSIGN_SIGNED_MUL = auto()
    ASSIGN_SIGNED_DIV = auto()
    ASSIGN_SIGNED_MOD = auto()

    # bitwise instructions
    ASSIGN_OR = auto()
    ASSIGN_AND = auto()
    ASSIGN_XOR = auto()

    # function instructions
    ASSIGN_CALL = auto()
    ASSIGN_CALL_PTR = auto()
    CALL = auto()
    CALL_PTR = auto()
    RETN = auto()
    RET = auto()

    # memory instructions
    WRITE = auto()
    ASSIGN_READ = auto()
    ASSIGN_ADDROF = auto()

    # branch instructions
    CMP = auto()
    JMP = auto()
    JE = auto()
    JNE = auto()
    JL = auto()
    JLE = auto()
    JG = auto()
    JGE = auto()

    # special instructions
    ASSIGN_PHI = auto()
    LOAD = auto()
    STORE = auto()
    UNLOAD = auto()

    def is_opcode_assign(self) -> bool:
        """
        Returns true if the opcode described an instruction of the form: X = Y.
        """
        return self in [
            IrOpcode.ASSIGN,

            IrOpcode.ASSIGN_ADD,
            IrOpcode.ASSIGN_SUB,
            IrOpcode.ASSIGN_MUL,
            IrOpcode.ASSIGN_DIV,
            IrOpcode.ASSIGN_MOD,

            IrOpcode.ASSIGN_SIGNED_ADD,
            IrOpcode.ASSIGN_SIGNED_SUB,
            IrOpcode.ASSIGN_SIGNED_MUL,
            IrOpcode.ASSIGN_SIGNED_DIV,
            IrOpcode.ASSIGN_SIGNED_MOD,

            IrOpcode.ASSIGN_OR,
            IrOpcode.ASSIGN_AND,
            IrOpcode.ASSIGN_XOR,

            IrOpcode.ASSIGN_READ,
            IrOpcode.ASSIGN_ADDROF,

            IrOpcode.ASSIGN_CALL,
            IrOpcode.ASSIGN_PHI,
        ]

    def get_opcode_class(self) -> IrOpcodeClass:
        """
        Returns the class of the specified opcode.
        """
        return {
            IrOpcode.UNDEF: IrOpcodeClass.NONE,
            IrOpcode.RETN: IrOpcodeClass.NONE,

            # intentionally done so that these instructions don't get handled the
            # usual way.
            IrOpcode.LOAD: IrOpcodeClass.NONE,
            IrOpcode.STORE: IrOpcodeClass.NONE,
            IrOpcode.UNLOAD: IrOpcodeClass.NONE,

            IrOpcode.ASSIGN: IrOpcodeClass.ASSIGN2,

            IrOpcode.ASSIGN_READ: IrOpcodeClass.ASSIGN2,
            IrOpcode.ASSIGN_ADDROF: IrOpcodeClass.ASSIGN2,

            IrOpcode.ASSIGN_ADD: IrOpcodeClass.ASSIGN3,
            IrOpcode.ASSIGN_SUB: IrOpcodeClass.ASSIGN3,
            IrOpcode.ASSIGN_MUL: IrOpcodeClass.ASSIGN3,
            IrOpcode.ASSIGN_DIV: IrOpcodeClass.ASSIGN3,
            IrOpcode.ASSIGN_MOD: IrOpcodeClass.ASSIGN3,

            IrOpcode.ASSIGN_SIGNED_ADD: IrOpcodeClass.ASSIGN3,
            IrOpcode.ASSIGN_SIGNED_SUB: IrOpcodeClass.ASSIGN3,
            IrOpcode.ASSIGN_SIGNED_MUL: IrOpcodeClass.ASSIGN3,
            IrOpcode.ASSIGN_SIGNED_DIV: IrOpcodeClass.ASSIGN3,
            IrOpcode.ASSIGN_SIGNED_MOD: IrOpcodeClass.ASSIGN3,

            IrOpcode.ASSIGN_OR: IrOpcodeClass.ASSIGN3,
            IrOpcode.ASSIGN_AND: IrOpcodeClass.ASSIGN3,
            IrOpcode.ASSIGN_XOR: IrOpcodeClass.ASSIGN3,

            IrOpcode.RET: IrOpcodeClass.USE1,
            IrOpcode.JMP: IrOpcodeClass.USE1,
            IrOpcode.JE: IrOpcodeClass.USE1,
            IrOpcode.JNE: IrOpcodeClass.USE1,
            IrOpcode.JL: IrOpcodeClass.USE1,
            IrOpcode.JLE: IrOpcodeClass.USE1,
            IrOpcode.JG: IrOpcodeClass.USE1,
            IrOpcode.JGE: IrOpcodeClass.USE1,

            IrOpcode.CMP: IrOpcodeClass.USE2,
            IrOpcode.WRITE: IrOpcodeClass.USE2,

            IrOpcode.ASSIGN_CALL: IrOpcodeClass.ASSIGN_CALL,

            IrOpcode.ASSIGN_PHI: IrOpcodeClass.ASSIGN_FIXED_CALL,

            IrOpcode.CALL: IrOpcodeClass.CALL,
        }[self]

    def get_operand_count(self) -> int:
        """
        Returns the number of operands used by the specified opcode.
        """
        return {
            IrOpcodeClass.ASSIGN_CALL: 2,
            IrOpcodeClass.ASSIGN_FIXED_CALL: 1,
            IrOpcodeClass.NONE: 0,
            IrOpcodeClass.USE1: 1,
            IrOpcodeClass.USE2: 2,
            IrOpcodeClass.ASSIGN2: 2,
            IrOpcodeClass.ASSIGN3: 3,
            IrOpcodeClass.CALL: 1,
        }[self.get_opcode_class()]

    def has_extra_operands(self) -> bool:
        """
        Checks whether the specified opcode requires extra operands.
        """
        return self.get_opcode_class() in [
            IrOpcodeClass.ASSIGN_CALL,
            IrOpcodeClass.ASSIGN_FIXED_CALL,
            IrOpcodeClass.CALL,
        ]


class IrOperand:
    """
    Base class for IR operands.
    """
    pass


class IrConst(IrOperand):
    """
    Constant operand.
    """

    def __init__(self, val: int = 0):
        self._val = val

    def get_value(self) -> int:
        return self._val

    def set_value(self, value: int):
        self._val = value

    def __eq__(self, other):
        if isinstance(other, IrConst):
            return self._val == other._val
        return False

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return f'IrConst({repr(self._val)})'


IrVarId = int
"""
Variable identifier.
"""


def make_var_id(base: int, subscript: int = 0, special: int = 0):
    return base | (subscript << 16) | (special << 32)


def var_base(xid: IrVarId):
    return xid & 0xFFFF


def var_subscript(xid: IrVarId):
    return (xid >> 16) & 0xFFFF


def var_special(xid: IrVarId):
    return xid >> 32


class IrVar(IrOperand):
    """
    Variable operand.
    """

    def __init__(self, xid: IrVarId = 0):
        self._id = xid

    def get_id(self) -> IrVarId:
        return self._id

    def set_id(self, xid: IrVarId):
        self._id = xid

    def __eq__(self, other):
        if isinstance(other, IrVar):
            return self._id == other._id
        return False

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        # TODO: use make_var
        s = f'{var_base(self._id)}'
        if var_special(self._id) != 0:
            s += f'<{var_special(self._id)}>'
        if var_subscript(self._id) != 0:
            s += f'_{var_subscript(self._id)}'
        return f'IrVar({s})'


IrLabelId = int
"""
Label identifier.
"""


class IrLabel(IrOperand):
    """
    Label operand (used in branch instructions).
    """

    def __init__(self, xid: IrLabelId = 0):
        self._id = xid

    def get_id(self) -> IrLabelId:
        return self._id

    def set_id(self, xid: IrLabelId):
        self._id = xid

    def __eq__(self, other):
        if isinstance(other, IrLabel):
            return self._id == other._id
        return False

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return f'IrLabel({repr(self._id)})'


class IrOffset(IrOperand):
    """
    Constant displacement operand.
    """

    def __init__(self, off: int = 0):
        self._off = off

    def get_offset(self) -> int:
        return self._off

    def set_offset(self, off: int):
        self._off = off

    def __eq__(self, other):
        if isinstance(other, IrOffset):
            return self._off == other._off
        return False

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return f'IrOffset({repr(self._off)})'


class IrName(IrOperand):
    """
    Known name operand.
    """

    def __init__(self, name: str = 0):
        self._name = name

    def get_name(self) -> str:
        return self._name

    def set_name(self, xid: str):
        self._name = xid

    def __eq__(self, other):
        if isinstance(other, IrName):
            return self._name == other._name
        return False

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return f'IrName({repr(self._name)})'


class IrBlockRef(IrOperand):
    """
    Basic block reference operand.

    Special operand type used by branch instructions inside control flow
    graphs. Since every branch instruction in a CFG points to the beginning
    of a basic block, it makes more sense to have those branch instructions
    encode their destination with a basic block operand.
    """

    def __init__(self, xid: BasicBlockId = 0):
        self._id = xid

    def get_id(self) -> BasicBlockId:
        return self._id

    def set_id(self, xid: BasicBlockId):
        self._id = xid

    def __eq__(self, other):
        if isinstance(other, IrBlockRef):
            return self._id == other._id
        return False

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return f'IrBlockRef({repr(self._id)})'


class IrInstruction:
    """
    Stores a single IR instruction.
    """

    def __init__(self):
        self.op: IrOpcode = IrOpcode.UNDEF
        self.oprs: List[IrOperand or None] = [None, None, None]
        self.extra: List[IrOperand] = []

    def push_extra(self, opr: IrOperand):
        """
        Inserts the specified operand into the instruction's "extra" list.
        """
        self.extra.append(opr)
        return self

    def __repr__(self):
        oprs = []
        for opr in self.oprs:
            if opr is not None:
                oprs.append(repr(opr))
        return f'IrInstruction({self.op}, oprs=[{", ".join(oprs)}], extra=[{", ".join(map(repr, self.extra))}])'
