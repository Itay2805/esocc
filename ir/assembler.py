from .ir import *
from typing import Dict
from copy import copy


class Assembler:
    """
    IR assembler.
    """

    class LabelUse:

        def __init__(self, lbl: IrLabelId, pos: int):
            self.lbl = lbl
            self.pos = pos

    def __init__(self):
        self._insts: List[IrInstruction] = []
        self._pos = 0

        self._next_lbl_id = 1
        self._lbl_fixes: Dict[IrLabelId, int] = {}
        self._lbl_uses: List[Assembler.LabelUse] = []

    def get_instructions(self):
        return self._insts

    def get_pos(self):
        return self._pos

    def set_pos(self, pos):
        self._pos = pos

    def clear(self):
        """
        Resets the state of the assembler.
        """
        self.__init__()

    def make_label(self):
        """
        Creates and returns a new unique label ID.
        """
        xid = self._next_lbl_id
        self._next_lbl_id += 1
        return xid

    def mark_label(self, xid: IrLabelId):
        """
        Sets the position of the specified label ID to the current position.
        """
        self._lbl_fixes[xid] = self._pos

    def make_and_mark_label(self):
        """
        Calls make_label() and mark_label() in succession.
        """
        lbl = self.make_label()
        self.mark_label(lbl)
        return lbl

    def fix_labels(self):
        """
        Updates label references where the label location is known.
        """
        for use in self._lbl_uses[:]:
            if use.lbl not in self._lbl_fixes:
                continue

            fix_pos = self._lbl_fixes[use.lbl]
            inst = self._insts[use.pos]
            delta = fix_pos - (use.pos + 1)
            inst.oprs[0] = IrOffset(delta)

            self._lbl_uses.remove(use)

    #
    # Emit methods:
    #

    def emit_assign_add(self, r: IrOperand, a: IrOperand, b: IrOperand):
        self._emit_basic3(IrOpcode.ASSIGN_ADD, r, a, b)

    def emit_assign_sub(self, r: IrOperand, a: IrOperand, b: IrOperand):
        self._emit_basic3(IrOpcode.ASSIGN_SUB, r, a, b)

    def emit_assign_mul(self, r: IrOperand, a: IrOperand, b: IrOperand):
        self._emit_basic3(IrOpcode.ASSIGN_MUL, r, a, b)

    def emit_assign_div(self, r: IrOperand, a: IrOperand, b: IrOperand):
        self._emit_basic3(IrOpcode.ASSIGN_DIV, r, a, b)

    def emit_assign_mod(self, r: IrOperand, a: IrOperand, b: IrOperand):
        self._emit_basic3(IrOpcode.ASSIGN_MOD, r, a, b)

    def emit_assign_read(self, r: IrOperand, a: IrOperand):
        self._emit_basic2(IrOpcode.ASSIGN_READ, r, a)

    def emit_write(self, r: IrOperand, a: IrOperand):
        self._emit_basic2(IrOpcode.WRITE, r, a)

    def emit_assign_addrof(self, r: IrOperand, a: IrOperand):
        self._emit_basic2(IrOpcode.ASSIGN_ADDROF, r, a)

    def emit_assign(self, a: IrOperand, b: IrOperand):
        self._emit_basic2(IrOpcode.ASSIGN, a, b)

    def emit_cmp(self, a: IrOperand, b: IrOperand):
        self._emit_basic2(IrOpcode.CMP, a, b)

    def emit_jmp(self, opr: IrOperand):
        self._emit_basic1(IrOpcode.JMP, opr)

    def emit_je(self, opr: IrOperand):
        self._emit_basic1(IrOpcode.JE, opr)

    def emit_jne(self, opr: IrOperand):
        self._emit_basic1(IrOpcode.JNE, opr)

    def emit_jl(self, opr: IrOperand):
        self._emit_basic1(IrOpcode.JL, opr)

    def emit_jle(self, opr: IrOperand):
        self._emit_basic1(IrOpcode.JLE, opr)

    def emit_jg(self, opr: IrOperand):
        self._emit_basic1(IrOpcode.JG, opr)

    def emit_jge(self, opr: IrOperand):
        self._emit_basic1(IrOpcode.JGE, opr)

    def emit_ret(self, opr: IrOperand):
        self._emit_basic1(IrOpcode.RET, opr)

    def emit_unload(self, opr: IrOperand):
        self._emit_basic1(IrOpcode.UNLOAD, opr)

    def emit_retn(self):
        self._emit_basic0(IrOpcode.RETN)

    def emit_call(self, target: IrOperand):
        inst = self._put_instruction()
        inst.op = IrOpcode.CALL
        inst.oprs[0] = copy(target)
        return inst

    def emit_assign_call(self, dest: IrOperand, target: IrOperand):
        inst = self._put_instruction()
        inst.op = IrOpcode.ASSIGN_CALL
        inst.oprs[0] = copy(dest)
        inst.oprs[1] = copy(target)
        return inst

    def emit_assign_phi(self, dest: IrOperand):
        inst = self._put_instruction()
        inst.op = IrOpcode.ASSIGN_PHI
        inst.oprs[0] = copy(dest)
        return inst

    def emit_store(self, opr: IrOperand):
        inst = self._put_instruction()
        inst.op = IrOpcode.STORE
        inst.oprs[0] = copy(opr)
        return inst

    def emit_load(self, dest: IrOperand):
        inst = self._put_instruction()
        inst.op = IrOpcode.LOAD
        inst.oprs[0] = copy(dest)
        return inst

    def _put_instruction(self):
        """
        Overwrites or inserts a new instruction and returns it.
        """
        if self._pos < len(self._insts):
            inst = self._insts[self._pos]
            self._pos += 1
            return inst

        self._pos += 1
        self._insts.append(IrInstruction())
        return self._insts[-1]

    def push_instruction(self, inst: IrInstruction):
        self._pos += 1
        self._insts.append(inst)

    def _emit_basic3(self, op: IrOpcode, r: IrOperand, a: IrOperand, b: IrOperand):
        """
        Emits a standard instruction in the form of: r = a <op> b
        """
        inst = self._put_instruction()
        inst.op = op
        inst.oprs[0] = copy(r)
        inst.oprs[1] = copy(a)
        inst.oprs[2] = copy(b)

    def _emit_basic2(self, op: IrOpcode, a: IrOperand, b: IrOperand):
        """
        Emits a binary instruction in the form of: a <op> b
        """
        inst = self._put_instruction()
        inst.op = op
        inst.oprs[0] = copy(a)
        inst.oprs[1] = copy(b)

    def _emit_basic1(self, op: IrOpcode, opr: IrOperand):
        """
        Emits an instruction that takes a single operand.
        """
        if isinstance(opr, IrLabel):
            self._lbl_uses.append(Assembler.LabelUse(opr.get_id(), self._pos))

        inst = self._put_instruction()
        inst.op = op
        inst.oprs[0] = copy(opr)

    def _emit_basic0(self, op: IrOpcode):
        """
        Emits an instruction that takes no operands.
        """
        inst = self._put_instruction()
        inst.op = op
