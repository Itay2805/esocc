from ir.control_flow import ControlFlowGraph, make_cfg
from ir.allocation.basic import BasicRegisterAllocator
from ir.allocation.allocator import RegisterAllocation
from ir.program import Procedure
from ir.printer import Printer
from ir.ssa import SsaBuilder
from ir.ir import *
from typing import *


class Dcpu16Procedure:
    pass


class Dcpu16Translator:
    """
    IR to Dcpu16 code translator

    Calling convetion is stackcall:
        * A, B, C, X, Y, Z, I - gp
        * J - base pointer
        * SP - stack pointer

    saving:
        * A, B, C, EX - caller saved
        * X, Y, Z, I, J, SP - caller saved
    """

    DCPU16_NUM_GP_REGISTERS = 7

    def __init__(self):
        self._proc: Procedure = None
        self._cfg: ControlFlowGraph = None
        self._reg_res: RegisterAllocation = None
        self._to_store_on_call = []
        self._to_restore_on_exit = []
        self._stored_lrs = []
        self._loaded_lrs = {}
        self._need_prologue = False
        self._copied_params = {}
        self._register_mapping = ''
        self._generated_asm = ''

    def get_asm(self):
        return self._generated_asm

    def _append(self, text):
        self._generated_asm += text + '\n'

    def translate_procedure(self, proc: Procedure):
        """
        Translates the specified procedure into DCPU16.
        """
        self._proc = proc

        if self._proc.is_exported():
            self._append(f'.global {self._proc.get_name()}')

        # build control flow graph
        self._cfg = make_cfg(proc.get_body())

        # transform into SSA form
        ssab = SsaBuilder()
        ssab.transform(self._cfg)

        # perform register allocation
        reg_alloc = BasicRegisterAllocator()
        self._reg_res = reg_alloc.allocate(self._cfg, Dcpu16Translator.DCPU16_NUM_GP_REGISTERS)

        # This is the color -> register map
        self._register_mapping = 'ABCXYZI'

        #
        # check if we need a prologue
        # we only need one if we ever have anything on the stack that
        # we may need to access directly, which only happen if we spill
        # variables on the stack (or have stack allocated structures)
        #
        for blk in self._cfg.get_blocks():
            for inst in blk.get_instructions():
                if inst.op == IrOpcode.STORE:
                    self._need_prologue = True
                    self._stored_lrs.append(tuple(inst.extra))
        
        # This is filled out as we go
        # TODO: we should fill it out better so we only
        #       store and restore whatever that will be
        #       used afterwards without a reassignment
        self._to_store_on_call = []

        # these registers need to be restored when we exit from the function
        # TODO: this is kinda ugly
        self._to_restore_on_exit = []
        for color in self._reg_res._color_map.values():
            reg = self._register_mapping[color]
            if reg in 'XYZI' and reg not in self._to_restore_on_exit:
                self._to_restore_on_exit.append(reg)

        # Print prologue
        self._append(f'{proc.get_name()}:')
        if self._need_prologue:
            self._append(f'\tSET PUSH, J')
            self._append(f'\tSET J, SP')

            if len(self._stored_lrs) > 0:
                self._append(f'\tSUB SP, {len(self._stored_lrs)}')

        # start converting code
        for blk in self._cfg.get_blocks():
            # add a local label for the block
            # if anyone jumps to it
            if len(blk.get_prev()) != 0:
                self._append(f'.blk{blk.get_id()}')

            # Translate the block's instructions
            last_cmp_in_block = None
            for inst in blk.get_instructions():
                # self._append(f'  # {Printer().print_instruction(inst)}')

                dest = self._translate_operand(inst.oprs[0], True)
                opr1 = self._translate_operand(inst.oprs[1], True)
                opr2 = self._translate_operand(inst.oprs[2], True)

                if inst.op == IrOpcode.ASSIGN_ADD or inst.op == IrOpcode.ASSIGN_SIGNED_ADD:
                    if opr2 == dest:
                        tmp = opr1
                        opr1 = opr2
                        opr2 = tmp
                    if dest != opr1:
                        self._append(f'\tSET {dest}, {opr1}')
                    self._append(f'\tADD {dest}, {opr2}')

                elif inst.op == IrOpcode.ASSIGN_SUB or inst.op == IrOpcode.ASSIGN_SIGNED_SUB:
                    assert opr2 != dest, "TODO: handle this case"
                    if dest != opr1:
                        self._append(f'\tSET {dest}, {opr1}')
                    self._append(f'\tSUB {dest}, {opr2}')

                elif inst.op == IrOpcode.ASSIGN_MUL:
                    if opr2 == dest:
                        tmp = opr1
                        opr1 = opr2
                        opr2 = tmp
                    if dest != opr1:
                        self._append(f'\tSET {dest}, {opr1}')
                    self._append(f'\tMUL {dest}, {opr2}')

                elif inst.op == IrOpcode.ASSIGN_SIGNED_MUL:
                    if opr2 != 1 and opr1 != 1:
                        if opr2 == dest:
                            tmp = opr1
                            opr1 = opr2
                            opr2 = tmp
                        if dest != opr1:
                            self._append(f'\tSET {dest}, {opr1}')
                        self._append(f'\tMLI {dest}, {opr2}')

                elif inst.op == IrOpcode.ASSIGN_DIV:
                    assert opr2 != dest, "TODO: handle this case"
                    if dest != opr1:
                        self._append(f'\tSET {dest}, {opr1}')
                    self._append(f'\tDIV {dest}, {opr2}')

                elif inst.op == IrOpcode.ASSIGN_SIGNED_DIV:
                    assert opr2 != dest, "TODO: handle this case"
                    if dest != opr1:
                        self._append(f'\tSET {dest}, {opr1}')
                    self._append(f'\tDIV {dest}, {opr2}')

                elif inst.op == IrOpcode.ASSIGN_MOD:
                    assert opr2 != dest, "TODO: handle this case"
                    if dest != opr1:
                        self._append(f'\tSET {dest}, {opr1}')
                    self._append(f'\tMOD {dest}, {opr2}')

                elif inst.op == IrOpcode.ASSIGN_SIGNED_MOD:
                    assert opr2 != dest, "TODO: handle this case"
                    if dest != opr1:
                        self._append(f'\tSET {dest}, {opr1}')
                    self._append(f'\tMDI {dest}, {opr2}')

                elif inst.op == IrOpcode.ASSIGN_OR:
                    if opr2 == dest:
                        tmp = opr1
                        opr1 = opr2
                        opr2 = tmp
                    if dest != opr1:
                        self._append(f'\tSET {dest}, {opr1}')
                    self._append(f'\tBOR {dest}, {opr2}')

                elif inst.op == IrOpcode.ASSIGN_AND:
                    if opr2 == dest:
                        tmp = opr1
                        opr1 = opr2
                        opr2 = tmp
                    if dest != opr1:
                        self._append(f'\tSET {dest}, {opr1}')
                    self._append(f'\tAND {dest}, {opr2}')

                elif inst.op == IrOpcode.ASSIGN_XOR:
                    if opr2 == dest:
                        tmp = opr1
                        opr1 = opr2
                        opr2 = tmp
                    if dest != opr1:
                        self._append(f'\tSET {dest}, {opr1}')
                    self._append(f'\tXOR {dest}, {opr2}')

                elif inst.op == IrOpcode.ASSIGN:
                    if dest != opr1:
                        self._append(f'\tSET {dest}, {opr1}')

                elif inst.op == IrOpcode.ASSIGN_READ:
                    self._append(f'\tSET {dest}, [{opr1}]')

                elif inst.op == IrOpcode.WRITE:
                    self._append(f'\tSET [{dest}], {opr1}')

                elif inst.op == IrOpcode.RET:
                    if dest != 'A':
                        self._append(f'\tSET A, {dest}')

                    for rest in reversed(self._to_restore_on_exit):
                        self._append(f'\tSET {rest}, POP')

                    if self._need_prologue:
                        self._append('\tSET SP, J')
                        self._append('\tSET J, POP')
                    self._append('\tSET PC, POP')

                elif inst.op == IrOpcode.RETN:

                    for rest in reversed(self._to_restore_on_exit):
                        self._append(f'\tSET {rest}, POP')

                    if self._need_prologue:
                        self._append('\tSET SP, J')
                        self._append('\tSET J, POP')
                    self._append('\tSET PC, POP')

                elif inst.op == IrOpcode.JMP:
                    self._append(f'\tSET PC, {dest}')

                elif inst.op == IrOpcode.JE:
                    self._append(f'\tIFE {self._translate_operand(inst.oprs[1], True)}, {self._translate_operand(inst.oprs[2], True)}')
                    self._append(f'\t\tSET PC, {dest}')

                elif inst.op == IrOpcode.JNE:
                    self._append(f'\tIFN {self._translate_operand(inst.oprs[1], True)}, {self._translate_operand(inst.oprs[2], True)}')
                    self._append(f'\t\tSET PC, {dest}')

                elif inst.op == IrOpcode.JL:
                    self._append(f'\tIFL {self._translate_operand(inst.oprs[1], True)}, {self._translate_operand(inst.oprs[2], True)}')
                    self._append(f'\t\tSET PC, {dest}')

                elif inst.op == IrOpcode.JG:
                    self._append(f'\tIFG {self._translate_operand(inst.oprs[1], True)}, {self._translate_operand(inst.oprs[2], True)}')
                    self._append(f'\t\tSET PC, {dest}')

                elif inst.op == IrOpcode.JGE:
                    self._append(f'\tIFE {self._translate_operand(inst.oprs[1], True)}, {self._translate_operand(inst.oprs[2], True)}')
                    self._append(f'\t\tSET PC, {dest}')
                    self._append(f'\tIFG {self._translate_operand(inst.oprs[1], True)}, {self._translate_operand(inst.oprs[2], True)}')
                    self._append(f'\t\tSET PC, {dest}')

                elif inst.op == IrOpcode.JLE:
                    self._append(f'\tIFE {self._translate_operand(inst.oprs[1], True)}, {self._translate_operand(inst.oprs[2], True)}')
                    self._append(f'\t\tSET PC, {dest}')
                    self._append(f'\tIFL {self._translate_operand(inst.oprs[1], True)}, {self._translate_operand(inst.oprs[2], True)}')
                    self._append(f'\t\tSET PC, {dest}')

                elif inst.op == IrOpcode.CALL or inst.op == IrOpcode.CALL_PTR:

                    # save registers that we need to
                    # TODO: we can do this much smarter if
                    #       we look at which of them is gonna
                    #       be used again later
                    for e in self._to_store_on_call:
                        self._append(f'\tSET PUSH, {e}')

                    for e in reversed(inst.extra):
                        self._append(f'\tSET PUSH, {self._translate_operand(e, True)}')

                    if inst.op == IrOpcode.CALL:
                        self._append(f'\tJSR {self._translate_operand(inst.oprs[0], False)}')
                    else:
                        self._append(f'\tJSR {self._translate_operand(inst.oprs[0], True)}')

                    self._append(f'\tSUB SP, {len(inst.extraR)}')

                    # restore registers that we need to
                    for e in reversed(self._to_store_on_call):
                        self._append(f'\tSET {e}, POP')

                elif inst.op == IrOpcode.ASSIGN_CALL or inst.op == IrOpcode.ASSIGN_CALL_PTR:

                    # save registers that we need to
                    # TODO: we can do this much smarter if
                    #       we look at which of them is gonna
                    #       be used again later
                    for e in self._to_store_on_call:
                        if e != dest:
                            self._append(f'\tSET PUSH, {e}')

                    for e in reversed(inst.extra):
                        self._append(f'\tSET PUSH, {self._translate_operand(e, True)}')

                    if inst.op == IrOpcode.ASSIGN_CALL:
                        self._append(f'\tJSR {self._translate_operand(inst.oprs[1], False)}')
                    else:
                        self._append(f'\tJSR {self._translate_operand(inst.oprs[1], True)}')

                    self._append(f'\tSUB SP, {len(inst.extra)}')

                    # restore registers that we need to
                    for e in reversed(self._to_store_on_call):
                        if e != dest:
                            self._append(f'\tSET {e}, POP')

                    if dest != 'A':
                        self._append(f'\tSET {dest}, A')

                elif inst.op == IrOpcode.STORE:
                    lr = tuple(inst.extra)
                    i = self._stored_lrs.index(lr)
                    self._append(f'\tSET [J - {i + 1}], {dest}')

                elif inst.op == IrOpcode.LOAD:
                    lr = tuple(inst.extra)
                    i = self._stored_lrs.index(lr)

                    self._loaded_lrs[dest] = lr
                    self._append(f'\tSET {dest}, [J - {i + 1}]')
                    pass

                elif inst.op == IrOpcode.UNLOAD:
                    # lr = self._loaded_lrs[dest]
                    # del self._loaded_lrs[dest]
                    # i = self._stored_lrs.index(lr)
                    #
                    # self._append(f'\tSET [J - {i + 1}], {dest}')
                    pass

                elif inst.op == IrOpcode.ASSIGN_ADDROF:
                    if inst.oprs[1] is None:
                        lr = tuple(inst.extra)
                        i = self._stored_lrs.index(lr)

                        self._append(f'\tSET {dest}, J')
                        self._append(f'\tADD {dest}, {i + 1}')
                    else:
                        opr = inst.oprs[1]
                        if isinstance(opr, IrVar):
                            if var_base(opr.get_id()) in self._proc.get_params():
                                if self._need_prologue:
                                    self._append(f'\tSET {dest}, J')
                                else:
                                    self._append(f'\tSET {dest}, SP')
                                self._append(f'\tADD {dest}, {self._proc.get_params().index(var_base(opr.get_id())) + 2}')
                            else:
                                assert False, "Tried to addrof a variable which is not on the stack"
                        elif isinstance(opr, IrName):
                            self._append(f'\tSET {dest}, {opr.get_name()}')
                        else:
                            assert False, f"Invalid operand {opr} for addrof"
                elif inst.op == IrOpcode.ASSIGN_PHI:
                    pass
                else:
                    assert False, f"Unknown instruction = {inst}"

    def _translate_operand(self, opr, deref):
        """
        Translates a single operand to dcpu16
        """
        if opr is None:
            return None

        if isinstance(opr, IrConst):
            return opr.get_value()
        elif isinstance(opr, IrBlockRef):
            return f'.blk{opr.get_id()}'
        elif isinstance(opr, IrVar):
            if var_base(opr.get_id()) in self._proc.get_params():
                index = self._proc.get_params().index(var_base(opr.get_id()))
                if index in self._copied_params:
                    return self._copied_params[index]
                else:
                    if self._need_prologue:
                        return f'[J + {index + 2}]'
                    else:
                        return f'[SP + {index + 2}]'
            else:
                reg = self._register_mapping[self._reg_res.get_color(opr.get_id())]
                if reg in 'ABC' and reg not in self._to_store_on_call:
                    self._to_store_on_call.append(reg)
                return reg
        elif isinstance(opr, IrName):
            if deref:
                return f'[{opr.get_name()}]'
            else:
                return opr.get_name()
        else:
            assert False, opr
