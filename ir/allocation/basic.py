from ir.allocation.undirected_graph import UndirectedGraph
from ir.allocation.allocator import *
from ir.assembler import Assembler
from ir.printer import Printer
from ir.data_flow import LiveAnalyzer, LiveAnalysis
from typing import Set


LiveRange = Set[IrVarId]


class BasicRegisterAllocator(RegisterAllocator):
    """
    A basic register allocator!
    """

    def __init__(self):
        self._cfg: ControlFlowGraph = None

        self._num_colors = 0

        self._live_ranges: List[LiveRange] = []
        self._live_range_map: Dict[IrVarId, int] = {}

        self._spilled_lrs: Set[LiveRange] = set()
        self._tmp_idx = 0

        self._infer_graph = UndirectedGraph()

        self._res = RegisterAllocation()

    def allocate(self, cfg: ControlFlowGraph, num_colors: int) -> RegisterAllocation:
        assert cfg.get_type() == ControlFlowGraphType.SSA, "CFG must be in SSA form"

        self._cfg = cfg
        self._num_colors = num_colors
        self._spilled_lrs.clear()
        self._tmp_idx = 0

        res = RegisterAllocation()
        self._res = res

        self._discover_live_ranges()
        self._build_inference_graph()
        while not self._color_graph():
            p = Printer()
            for blk in self._cfg.get_blocks():
                p.print_basic_block(blk)
            self._discover_live_ranges()
            self._build_inference_graph()

        self._res = None
        return res

    def _discover_live_ranges(self):
        """
        Finds all global live ranges in the underlying CFG, and maps all SSA
        names to a matching live range.
        """
        self._live_range_map.clear()
        self._live_ranges.clear()

        lr_map: Dict[IrVarId, LiveRange] = {}

        for blk in self._cfg.get_blocks():
            for inst in blk.get_instructions():
                if inst.op != IrOpcode.ASSIGN_PHI:
                    continue

                dest_var = inst.oprs[0].get_id()

                lr = set()
                lr.add(dest_var)

                # insert the sets associated with the operands in to the final
                # live range.
                for i in range(len(inst.extra)):
                    opr = inst.extra[i].get_id()
                    if opr in lr_map:
                        opr_lr = lr_map[opr]
                        for it in opr_lr:
                            lr.add(it)
                    else:
                        lr.add(opr)

                # update operands' sets.
                for i in range(len(inst.extra)):
                    opr = inst.extra[i].get_id()
                    lr_map[opr] = lr

                lr_map[dest_var] = lr

        for p in lr_map:
            lr = lr_map[p]
            lr_id = len(self._live_ranges)

            for var in lr:
                self._live_range_map[var] = lr_id
            self._live_ranges.append(lr)

        # create a live range for variables that weren't handled
        for blk in self._cfg.get_blocks():
            for inst in blk.get_instructions():
                if inst.op.is_opcode_assign() or inst.op == IrOpcode.LOAD:
                    var = inst.oprs[0].get_id()
                    if var not in self._live_range_map:
                        lr = set()
                        lr.add(var)
                        self._live_range_map[var] = len(self._live_ranges)
                        self._live_ranges.append(lr)

        self._nub_live_ranges()

    def _nub_live_ranges(self):
        """
        Joins equal live ranges together.
        """
        lrs: Dict[tuple, int] = {}
        for lr in self._live_ranges:
            if tuple(lr) not in lrs:
                idx = len(lrs)
                lrs[tuple(lr)] = idx

        ord_lrs: List[LiveRange] = []
        for p in lrs:
            ord_lrs.append(set(p))

        xvars: List[IrVarId] = []
        for p in self._live_range_map:
            xvars.append(p)
        for var in xvars:
            self._live_range_map[var] = lrs[tuple(self._live_ranges[self._live_range_map[var]])]

        self._live_ranges = ord_lrs

    def _build_inference_graph(self):
        """
        Builds the inference graph for the underlying CFG.

        The inference graph is populated with a node for every global live range
        in the CFG. Then, an edge is drawn between every two nodes whose live
        ranges interfere at some point in the CFG.
        """
        self._infer_graph.clear()

        # insert a node for every global live range
        for i in range(len(self._live_ranges)):
            self._infer_graph.add_node(i)

        la = LiveAnalyzer()
        live_results = la.analyze(self._cfg)

        # print("Building inference graph:")

        for blk in self._cfg.get_blocks():
            live_now: Set[int] = set()
            for var in live_results.get_live_out(blk.get_id()):
                live_now.add(self._live_range_map[var])

            insts = blk.get_instructions()
            for inst in reversed(insts):

                # p = Printer()
                # print(f'\tinst: {p.print_instruction(inst)}')

                if inst.op == IrOpcode.STORE or inst.op == IrOpcode.UNLOAD:
                    if isinstance(inst.oprs[0], IrVar) and self._live_range_map[inst.oprs[0].get_id()] in live_now:
                        live_now.add(self._live_range_map[inst.oprs[0].get_id()])

                elif inst.op == IrOpcode.LOAD:
                    lr_dest = self._live_range_map[inst.oprs[0].get_id()]
                    for lr in live_now:
                        if lr != lr_dest:
                            self._infer_graph.add_edge(lr_dest, lr)
                    if lr_dest in live_now:
                        live_now.remove(lr_dest)

                else:
                    opr_start = 1 if inst.op.is_opcode_assign() else 0
                    opr_end = inst.op.get_operand_count()

                    if inst.op.is_opcode_assign():
                        lr_dest = self._live_range_map[inst.oprs[0].get_id()]
                        for lr in live_now:
                            if lr != lr_dest:
                                self._infer_graph.add_edge(lr_dest, lr)

                        if lr_dest in live_now:
                            live_now.remove(lr_dest)

                    # insert operands into LiveNow set
                    for opr in inst.oprs[opr_start:opr_end]:
                        if isinstance(opr, IrVar):
                            if opr.get_id() in self._live_range_map:
                                live_now.add(self._live_range_map[opr.get_id()])
                            else:
                                live_now.add(0)

                    if inst.op.has_extra_operands():
                        for opr in inst.extra:
                            if isinstance(opr, IrVar):
                                live_now.add(self._live_range_map[opr.get_id()])

    def _color_graph(self) -> bool:
        """
        Attempts to color the inference graph.
        :return: True if the graph has been successfully colored.
        """

        #
        # Puck out nodes from the inference graph until it is empty
        #
        stk: List[UndirectedGraph.Node] = []
        while len(self._infer_graph) != 0:
            # pick node to remove from graph
            if self._infer_graph.has_less_k(self._num_colors):
                # pick an unconstrained node to remove from the graph
                xid = self._infer_graph.find_less_k(self._num_colors)
            else:
                # no unconstrained nodes left in the graph
                # carefully pick a constrained node
                xid = self._pick_constrained_node()

            stk.append(self._infer_graph.get_node(xid).clone())
            self._infer_graph.remove_node(xid)

        #
        # Reconstruct the inference graph, coloring nodes at the same time.
        #
        color_map: Dict[int, RegisterColor] = {}
        while len(stk) != 0:
            # insert node back into the graph
            node = stk.pop()
            self._infer_graph.add_node(node.value)
            for xid in node.nodes:
                self._infer_graph.add_edge(node.value, xid)

            # color node
            avail: Set[RegisterColor] = set()
            for i in range(self._num_colors):
                avail.add(i)

            for n in node.nodes:
                if n in color_map and color_map[n] in avail:
                    avail.remove(color_map[n])

            if len(avail) != 0:
                col = next(iter(avail))
                color_map[node.value] = col

        if len(color_map) != len(self._infer_graph):
            # not all nodes colored.
            # spill
            xid = self._pick_node_to_spill(color_map)
            self._insert_spill_code(self._live_ranges[xid])
            return False

        for p in self._live_range_map:
            lr_id = self._live_range_map[p]
            self._res.set_color(p, color_map[lr_id])
        return True

    def _pick_constrained_node(self) -> int:
        """
        Picks a constrained node to remove from the inference graph.
        """
        # TODO: this
        return self._infer_graph.get_nodes()[0].value

    def _pick_node_to_spill(self, color_map: Dict[int, RegisterColor]) -> int:
        """
        Picks a node to spill from the inference graph.
        """
        # TODO

        for n in self._infer_graph.get_nodes():
            if n.value not in color_map:
                lr = tuple(self._live_ranges[n.value])
                if lr in self._spilled_lrs:
                    continue

                self._spilled_lrs.add(lr)
                return n.value

        assert False, "node not found"

    def _insert_spill_code(self, lr: LiveRange):
        """
        Inserts spill code for the specified live range into the CFG.
        """
        asem = Assembler()
        for blk in self._cfg.get_blocks():
            insts = []
            for inst in blk.get_instructions():
                if inst.op == IrOpcode.ASSIGN_PHI:
                    if not (isinstance(inst.oprs[0], IrVar) and inst.oprs[0].get_id() in lr):
                        found = False
                        for ext in inst.extra:
                            if isinstance(ext, IrVar) and ext.get_id() in lr:
                                found = True
                                break
                        if not found:
                            insts.append(inst)
                    continue

                need_store = False
                need_load = False
                tmp_var = make_var_id(var_base(next(iter(lr))), 0, self._tmp_idx + 1)

                if inst.op.is_opcode_assign():
                    # append store after definition of variablse in the live range.
                    if isinstance(inst.oprs[0], IrVar) and inst.oprs[0].get_id() in lr:
                        need_store = True

                        # replace destination variable with temporary variable
                        inst.oprs[0] = IrVar(tmp_var)

                # wrap uses of variables in the live range with load+unload
                if self._contains_live_range_use(inst, lr):
                    need_load = True

                    # replace uses with the temporary variable
                    opr_start = 1 if inst.op.is_opcode_assign() else 0
                    opr_end = inst.op.get_operand_count()

                    for i in range(opr_start, opr_end):
                        if isinstance(inst.oprs[i], IrVar) and inst.oprs[i].get_id() in lr:
                            inst.oprs[i] = IrVar(tmp_var)

                    if inst.op.has_extra_operands():
                        for i in range(len(inst.extra)):
                            if isinstance(inst.extra[i], IrVar) and inst.extra[i].get_id() in lr:
                                inst.extra[i] = IrVar(tmp_var)

                if need_load or need_store:
                    self._tmp_idx += 1

                if need_load:
                    # load
                    si = asem.emit_load(IrVar(tmp_var))
                    for var in lr:
                        si.push_extra(IrVar(var))
                    insts.append(asem.get_instructions()[0])
                    asem.clear()

                insts.append(inst)

                if need_store:
                    # store
                    si = asem.emit_store(IrVar(tmp_var))
                    for var in lr:
                        si.push_extra(IrVar(var))
                    insts.append(asem.get_instructions()[0])
                    asem.clear()

                elif need_load:
                    # unload
                    asem.emit_unload(IrVar(tmp_var))
                    insts.append(asem.get_instructions()[0])
                    asem.clear()

            blk.clear_instructions()
            blk.push_instructions_front(insts)

    def _contains_live_range_use(self, inst: IrInstruction, lr: LiveRange):
        """
        Checks whether the specified instruction's operands contain variables
        from the the given live range.
        """
        opr_start = 1 if inst.op.is_opcode_assign() else 0
        opr_end = inst.op.get_operand_count()

        for opr in inst.oprs[opr_start:opr_end]:
            if isinstance(opr, IrVar) and opr.get_id() in lr:
                return True

        if inst.op.has_extra_operands():
            for opr in inst.extra:
                if isinstance(opr, IrVar) and opr.get_id() in lr:
                    return True

        return False
