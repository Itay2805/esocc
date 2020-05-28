from .control_flow import *


def _log10(n: int):
    return 0 if n < 10 else 1 + _log10(n // 10)


class Printer:
    """
    IR pretty printer.
    """

    def __init__(self):
        self._base = 0
        self._inst_idx = 0
        self._names: Dict[IrVarId, str] = {}

    def add_name(self, xid: IrVarId, name: str):
        self._names[xid] = name

    def print_mnemonic(self, op: IrOpcode) -> str:
        return {
            IrOpcode.UNDEF: '<undef>',
            IrOpcode.RETN: 'ret',

            # intentionally done so that these instructions don't get handled the
            # usual way.
            IrOpcode.LOAD: 'load',
            IrOpcode.STORE: 'store',
            IrOpcode.UNLOAD: 'unload',

            IrOpcode.ASSIGN: '=',

            IrOpcode.ASSIGN_ADD: '+',
            IrOpcode.ASSIGN_SUB: '-',
            IrOpcode.ASSIGN_MUL: '*',
            IrOpcode.ASSIGN_DIV: '/',
            IrOpcode.ASSIGN_MOD: '%',

            IrOpcode.ASSIGN_SIGNED_ADD: '+',
            IrOpcode.ASSIGN_SIGNED_SUB: '-',
            IrOpcode.ASSIGN_SIGNED_MUL: '*',
            IrOpcode.ASSIGN_SIGNED_DIV: '/',
            IrOpcode.ASSIGN_SIGNED_MOD: '%',

            IrOpcode.ASSIGN_OR: '|',
            IrOpcode.ASSIGN_AND: '&',
            IrOpcode.ASSIGN_XOR: '^',

            IrOpcode.RET: 'ret',
            IrOpcode.JMP: 'jmp',
            IrOpcode.JE: 'je',
            IrOpcode.JNE: 'jne',
            IrOpcode.JL: 'jl',
            IrOpcode.JLE: 'jle',
            IrOpcode.JG: 'jg',
            IrOpcode.JGE: 'jge',

            IrOpcode.ASSIGN_CALL: 'call',

            IrOpcode.ASSIGN_PHI: 'phi',

            IrOpcode.ASSIGN_ADDROF: 'addrof',
            IrOpcode.ASSIGN_READ: 'read',
            IrOpcode.WRITE: 'write',

            IrOpcode.CALL: 'call',
        }[op]

    def print_instruction(self, ins: IrInstruction) -> str:
        if ins.op == IrOpcode.UNDEF:
            return '<undef>'

        elif ins.op == IrOpcode.RETN:
            return self.print_mnemonic(ins.op)

        elif ins.op in [
            IrOpcode.ASSIGN_ADD,
            IrOpcode.ASSIGN_SUB,
            IrOpcode.ASSIGN_MUL,
            IrOpcode.ASSIGN_DIV,
            IrOpcode.ASSIGN_MOD,
        ]:
            return f'{self.print_operand(ins.oprs[0])} = {self.print_operand(ins.oprs[1])} {self.print_mnemonic(ins.op)} {self.print_operand(ins.oprs[2])}'

        elif ins.op == IrOpcode.ASSIGN:
            return f'{self.print_operand(ins.oprs[0])} = {self.print_operand(ins.oprs[1])}'

        elif ins.op == IrOpcode.ASSIGN_READ:
            return f'{self.print_operand(ins.oprs[0])} = {self.print_mnemonic(ins.op)} {self.print_operand(ins.oprs[1])}'

        elif ins.op in [
            IrOpcode.WRITE,
        ]:
            return f'{self.print_mnemonic(ins.op)} {self.print_operand(ins.oprs[0])}, {self.print_operand(ins.oprs[1])}'

        elif ins.op in [
            IrOpcode.JMP,
            IrOpcode.RET,
            IrOpcode.UNLOAD
        ]:
            return f'{self.print_mnemonic(ins.op)} {self.print_operand(ins.oprs[0])}'

        elif ins.op in [
            IrOpcode.JE,
            IrOpcode.JNE,
            IrOpcode.JL,
            IrOpcode.JLE,
            IrOpcode.JG,
            IrOpcode.JGE,
        ]:
            return f'{self.print_mnemonic(ins.op)} {self.print_operand(ins.oprs[0])}, {self.print_operand(ins.oprs[1])}, {self.print_operand(ins.oprs[2])}'

        elif ins.op == IrOpcode.ASSIGN_PHI:
            return f'{self.print_operand(ins.oprs[0])} = phi({", ".join(map(self.print_operand, ins.extra))})'

        elif ins.op == IrOpcode.ASSIGN_CALL:
            return f'{self.print_operand(ins.oprs[0])} = call {self.print_operand(ins.oprs[1])}({", ".join(map(self.print_operand, ins.extra))})'

        elif ins.op == IrOpcode.CALL:
            return f'call {self.print_operand(ins.oprs[0])}({", ".join(map(self.print_operand, ins.extra))})'

        elif ins.op == IrOpcode.LOAD:
            return f'{self.print_operand(ins.oprs[0])} = {self.print_mnemonic(ins.op)} LR<{", ".join(map(self.print_operand, ins.extra))}>'

        elif ins.op == IrOpcode.STORE:
            return f'LR<{", ".join(map(self.print_operand, ins.extra))}> = {self.print_mnemonic(ins.op)} {self.print_operand(ins.oprs[0])}'

        elif ins.op == IrOpcode.ASSIGN_ADDROF:
            if ins.oprs[1] is None:
                return f'{self.print_operand(ins.oprs[0])} = {self.print_mnemonic(ins.op)} LR<{", ".join(map(self.print_operand, ins.extra))}>'
            else:
                return f'{self.print_operand(ins.oprs[0])} = {self.print_mnemonic(ins.op)} {self.print_operand(ins.oprs[1])}'

        else:
            assert False, ins

    def print_basic_block(self, blk: BasicBlock):
        self._base = blk.get_base()

        insts = blk.get_instructions()
        lpad = _log10(len(insts)) + 1

        s = f'Basic Block #{blk.get_id()}\n'
        s += '-' * (14 + _log10(blk.get_id())) + '\n'

        for i in range(len(insts)):
            self._inst_idx = self._base + i
            s += str(self._inst_idx).zfill(lpad) + ": "
            s += self.print_instruction(insts[i])
            s += '\n'

        # print names of attached blocks
        s += '-' * (14 + _log10(blk.get_id())) + '\n'

        s += 'Prev:'
        if len(blk.get_prev()) != 0:
            for b in blk.get_prev():
                s += f' #{b.get_id()}'
        else:
            s += ' none'
        s += '\n'

        s += 'Next:'
        if len(blk.get_next()) != 0:
            for b in blk.get_next():
                s += f' #{b.get_id()}'
        else:
            s += ' none'
        s += '\n'

        return s

    def print_operand(self, opr: IrOperand) -> str:
        if isinstance(opr, IrConst):
            return str(opr.get_value())

        elif isinstance(opr, IrVar):
            var = opr.get_id()

            if var in self._names:
                s = self._names[var]
            else:
                if var_base(var) in self._names:
                    s = self._names[var_base(var)]
                else:
                    s = f't{var_base(var)}'

                if var_special(var) != 0:
                    s += f'<{var_special(var)}>'

                if var_subscript(var) != 0:
                    s += f'_{var_subscript(var)}'

            return s

        elif isinstance(opr, IrOffset):
            return str(self._inst_idx + 1 + opr.get_offset())

        elif isinstance(opr, IrLabel):
            return f'L{opr.get_id()}'

        elif isinstance(opr, IrName):
            return opr.get_name()

        elif isinstance(opr, IrBlockRef):
            return f'<block #{opr.get_id()}>'

        else:
            assert False, opr
