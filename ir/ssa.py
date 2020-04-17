from .data_flow import *
from .assembler import *
from ir.printer import Printer


def _has_phi_function(insts: List[IrInstruction], var: IrVarId) -> bool:
    for inst in insts:
        if inst.op != IrOpcode.ASSIGN_PHI:
            break

        if isinstance(inst.oprs[0], IrVar) and inst.oprs[0].get_id() == var:
            return True

    return False


class SsaBuilder:
    """
    Transforms control flow graphs into SSA form.
    """

    def __init__(self):
        self._cfg: ControlFlowGraph = None

        self._globals: Set[IrVarId] = set()
        self._def_blocks: Dict[IrVarId, Set[BasicBlockId]] = {}
        self._dom_results: DomAnalysis = None

        # Used when renaming
        self._counters: Dict[IrVarId, int] = {}
        self._stacks: Dict[IrVarId, List[int]] = {}

    def transform(self, cfg: ControlFlowGraph):
        """
        Transforms the specified CFG into SSA form.

        :param cfg: The control flow graph to transform.
        """
        self._cfg = cfg

        da = DomAnalyzer()
        self._dom_results = da.analyze(self._cfg)

        self._find_globals(self._globals, self._def_blocks)
        self._define_initial_names()
        self._insert_phi_functions()
        self._rename()

        self._cfg.set_type(ControlFlowGraphType.SSA)

    def _insert_phi_functions(self):
        """
        Inserts phi-functions at the start of every block that has multiple
        predecessors. A phi-function is inserted for every name that is defined
        or used in the control flow graph.
        """
        handled_blocks: Dict[IrVarId, Set[BasicBlockId]] = {}
        asems: Dict[BasicBlockId, Assembler] = {}

        for var in self._globals:

            if var in self._def_blocks:
                var_blocks = self._def_blocks[var]
                work_list = list(var_blocks)
            else:
                work_list = []

            while len(work_list) != 0:
                bid = work_list.pop(-1)

                dfs = self._dom_results.get_dfs(bid)
                for df in dfs:
                    blk = self._cfg.find_block(df)
                    if df not in asems:
                        asems[df] = Assembler()
                    asem = asems[df]

                    if not _has_phi_function(blk.get_instructions(), var) and not _has_phi_function(asem.get_instructions(), var):
                        # insert phi function to the beginning of the block
                        phi = asem.emit_assign_phi(IrVar(var))
                        for i in range(len(blk.get_prev())):
                            phi.push_extra(IrVar(var))

                        if var not in handled_blocks or df not in handled_blocks[var]:
                            work_list.append(df)
                            if var not in handled_blocks:
                                handled_blocks[var] = set()
                            handled_blocks[var].add(df)

        for p in asems:
            blk = self._cfg.find_block(p)
            insts = asems[p].get_instructions()
            blk.push_instructions_front(insts)

    def _define_initial_names(self):
        """
        Initializes the stack/counter for the first block.
        """
        root = self._cfg.get_root()
        undef_globals = set(self._globals)
        for inst in root.get_instructions():
            if inst.op.is_opcode_assign() and isinstance(inst.oprs[0], IrVar):
                if inst.oprs[0].get_id() in undef_globals:
                    undef_globals.remove(inst.oprs[0].get_id())

        for var in undef_globals:
            self._new_name(var)

    def _find_globals(self, globals: Set[IrVarId], blocks: Dict[IrVarId, Set[BasicBlockId]]):
        """
        Finds all variables that are live across multiple blocks.
        """
        for blk in self._cfg.get_blocks():
            kill: Set[IrVarId] = set()
            for inst in blk.get_instructions():
                opr_start = 1 if inst.op.is_opcode_assign() else 0
                opr_end = inst.op.get_operand_count()

                for i in range(opr_start, opr_end):
                    if isinstance(inst.oprs[i], IrVar) and inst.oprs[i].get_id() not in kill:
                        globals.add(inst.oprs[i].get_id())

                if inst.op.has_extra_operands():
                    for opr in inst.extra:
                        if isinstance(opr, IrVar) and opr.get_id() not in kill:
                            globals.add(opr.get_id())

                if inst.op.is_opcode_assign() and isinstance(inst.oprs[0], IrVar):
                    var = inst.oprs[0].get_id()
                    kill.add(var)

                    if var not in blocks:
                        blocks[var] = set()

                    blocks[var].add(blk.get_id())

    def _rename(self):
        """
        Renames variables so that each definition is unique.
        """
        self._rename_block(self._cfg.get_root())

    def _rename_block(self, blk: BasicBlock):
        insts = blk.get_instructions()
        for inst in insts:
            if inst.op == IrOpcode.ASSIGN_PHI:
                inst.oprs[0].set_id(self._new_name(inst.oprs[0].get_id()))
            else:
                opr_start = 1 if inst.op.is_opcode_assign() else 0
                opr_end = inst.op.get_operand_count()

                # rename operands
                for opr in inst.oprs[opr_start:opr_end]:
                    if isinstance(opr, IrVar):
                        var = opr.get_id()
                        stk = self._stacks[var]
                        assert len(stk) != 0, "variable used before being defined"
                        opr.set_id(make_var_id(var, stk[-1]))

                if inst.op.has_extra_operands():
                    for opr in inst.extra:
                        if isinstance(opr, IrVar):
                            var = opr.get_id()
                            stk = self._stacks[var]
                            assert len(stk) != 0, "variable used before being defined"
                            opr.set_id(make_var_id(var, stk[-1]))

                # rename name being assigned
                if inst.op.is_opcode_assign() and isinstance(inst.oprs[0], IrVar):
                    inst.oprs[0].set_id(self._new_name(inst.oprs[0].get_id()))

        # fill phi-function parameters
        for next in blk.get_next():
            idx = 0

            for i in range(len(next.get_prev())):
                if next.get_prev()[i].get_id() == blk.get_id():
                    idx = i
                    break

            for inst in next.get_instructions():
                if inst.op != IrOpcode.ASSIGN_PHI:
                    break

                var = inst.extra[idx].get_id()
                stk = self._stacks[var_base(var)]
                assert len(stk) != 0, "bad"
                inst.extra[idx].set_id(make_var_id(var_base(var), stk[-1]))

        # recurse
        for b in self._cfg.get_blocks():
            if b.get_id() == blk.get_id() or b.get_id() == self._cfg.get_root().get_id():
                continue

            idom = self._dom_results.get_idom(b.get_id())
            if blk.get_id() == idom:
                self._rename_block(b)

        for inst in insts:
            if inst.op.is_opcode_assign() and isinstance(inst.oprs[0], IrVar):
                var = inst.oprs[0].get_id()
                stk = self._stacks[var_base(var)]
                if len(stk) != 0:
                    stk.pop()

    def _new_name(self, base: IrVarId) -> IrVarId:
        if base not in self._counters:
            self._counters[base] = 0
        self._counters[base] += 1

        if base not in self._stacks:
            self._stacks[base] = []

        i = self._counters[base]
        self._stacks[base].append(i)

        return make_var_id(base, i)

    def _enum_vars(self) -> Set[IrVarId]:
        """
        Returns a list of all variables defined or used in the CFG.
        """
        pass
