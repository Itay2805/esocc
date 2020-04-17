from .control_flow import *
from typing import Set


class IterativeAnalyzer:
    """
    Base class for a special class of data-flow analyzers.

    Serves as the base class for global data-flow analyzers whose problems
    can be solved using an iterative fixed-point algorithm.
    """

    def __init__(self):
        self._frags = {}
        self._cfg: ControlFlowGraph = None

    def get_active_cfg(self):
        return self._cfg

    def set_active_cfg(self, cfg):
        self._cfg = cfg

    def _compute_fragment(self, frag, blk: BasicBlock) -> bool:
        """
        Computes a fragment for the specified basic block.

        :return: True if the fragment has been modified.
        """
        raise NotImplementedError()

    def _compute_init_fragment(self, blk: BasicBlock) -> object:
        """
        Initializes a fragment for the first time.
        """
        raise NotImplementedError()

    def _get_fragment(self, blk: BasicBlock or BasicBlockId):
        """
        Returns the fragment associated with the specified basic block ID.
        """
        if isinstance(blk, BasicBlock):
            blk = blk.get_id()
        return self._frags[blk]

    def _solve(self, cfg: ControlFlowGraph):
        """
        Solves the data-flow problem for the specified CFG using an iterative
        fixed-point algorithm.
        """
        self.set_active_cfg(cfg)

        self._frags.clear()

        # initialize fragments
        for blk in cfg.get_blocks():
            self._frags[blk.get_id()] = self._compute_init_fragment(blk)

        changed = True
        while changed:
            changed = False
            for blk in cfg.get_blocks():
                if self._compute_fragment(self._frags[blk.get_id()], blk):
                    changed = True


# ----------------------------------------------------------------------------------------------------------------------


# TODO: reach_def_analyzer


# ----------------------------------------------------------------------------------------------------------------------


class DomAnalysis:
    """
    Dominance analysis results.
    """

    def __init__(self):
        self._block_map: Dict[BasicBlockId, Set[BasicBlockId]] = {}
        self._idom_map: Dict[BasicBlockId, BasicBlockId] = {}
        self._df_map: Dict[BasicBlockId, Set[BasicBlockId]] = {}

    def add_block(self, xid: BasicBlockId, doms: Set[BasicBlockId]):
        self._block_map[xid] = doms

    def get_block(self, xid: BasicBlockId) -> Set[BasicBlockId]:
        """
        Returns the set of blocks dominating the specified block.
        """
        assert xid in self._block_map, "invalid id"
        return self._block_map[xid]

    def set_idom(self, xid: BasicBlockId, idom: BasicBlockId):
        """
        Sets a block's immediate dominator.
        """
        self._idom_map[xid] = idom

    def get_idom(self, xid: BasicBlockId) -> BasicBlockId:
        """
        Returns the specified block's immediate dominator.
        """
        assert xid in self._idom_map, "invalid id"
        return self._idom_map[xid]

    def add_df(self, xid: BasicBlockId, df: BasicBlockId):
        """
        Inserts a block into a specified block's dominance frontier set.
        """
        if xid not in self._df_map:
            self._df_map[xid] = set()
        self._df_map[xid].add(df)

    def get_dfs(self, xid: BasicBlockId) -> Set[BasicBlockId]:
        """
        Returns the dominance frontier set of a specified block.
        """
        if xid not in self._df_map:
            return set()
        return self._df_map[xid]


class DomAnalyzer(IterativeAnalyzer):
    """
    Dominance analyzer.
    """

    class MyFragment:

        def __init__(self):
            self.doms: Set[BasicBlockId] = set()

    def __init__(self):
        super(DomAnalyzer, self).__init__()

    def analyze(self, cfg: ControlFlowGraph) -> DomAnalysis:
        """
        Performs dominance analysis on the specified CFG.

        :param cfg: The control flow graph to analyze.
        :return: The results of the analysis.
        """

        self.set_active_cfg(cfg)
        self._solve(cfg)

        result = DomAnalysis()
        for blk in cfg.get_blocks():
            frag: DomAnalyzer.MyFragment = self._get_fragment(blk)
            result.add_block(blk.get_id(), frag.doms)

        # compute immediate dominators
        self._compute_idoms(result)

        # compute dominance frontiers
        self._compute_dfs(result)

        return result

    def _compute_idoms(self, result: DomAnalysis):
        """
        Finds all immediate dominators.
        """
        for blk in self._cfg.get_blocks():
            doms = result.get_block(blk.get_id())
            for dom in doms:
                if dom == blk.get_id():
                    continue

                found = False
                for other_dom in doms:
                    if other_dom != blk.get_id() and other_dom != dom:
                        other_dom_doms = result.get_block(other_dom)
                        if dom in other_dom_doms:
                            found = True
                            break

                if not found:
                    result.set_idom(blk.get_id(), dom)

    def _compute_dfs(self, result: DomAnalysis):
        """
        Computes dominance frontiers.
        """
        for blk in self._cfg.get_blocks():
            prevs = blk.get_prev()
            if len(prevs) > 1:
                blk_idom = result.get_idom(blk.get_id())
                for curr in prevs:
                    while curr.get_id() != blk_idom:
                        result.add_df(curr.get_id(), blk.get_id())
                        curr = self._cfg.find_block(result.get_idom(curr.get_id()))

    def _compute_fragment(self, frag: MyFragment, blk: BasicBlock) -> bool:
        ndoms = set()

        prevs = blk.get_prev()
        if len(prevs) != 0:
            ndoms = set(self._get_fragment(prevs[0]).doms)

            for prev in prevs[1:]:
                prev_frag = self._get_fragment(prev)
                ndoms = set(filter(lambda x: x in prev_frag.doms, ndoms))

        ndoms.add(blk.get_id())

        modified = frag.doms != ndoms
        if modified:
            frag.doms = ndoms
        return modified

    def _compute_init_fragment(self, blk: BasicBlock) -> MyFragment:
        frag = DomAnalyzer.MyFragment()

        if self._cfg.get_root().get_id() == blk.get_id():
            frag.doms.add(blk.get_id())
        else:
            for b in self._cfg.get_blocks():
                frag.doms.add(b.get_id())

        return frag


# ----------------------------------------------------------------------------------------------------------------------


class LiveAnalysis:
    """
    Live-variable analysis results.
    """

    def __init__(self):
        self._block_map: Dict[BasicBlockId, Set[IrVarId]] = {}

    def add_block(self, xid: BasicBlockId, live_out: Set[IrVarId]):
        self._block_map[xid] = live_out

    def get_live_out(self, xid: BasicBlockId) -> Set[IrVarId]:
        """
        Returns the variables live on exit from the specified block.
        """
        if xid not in self._block_map:
            return set()
        return self._block_map[xid]


class LiveAnalyzer(IterativeAnalyzer):

    class MyFragment:
        def __init__(self):
            self.live_out: Set[IrVarId] = set()

    def __init__(self):
        super(LiveAnalyzer, self).__init__()
        self._ue_vars: Dict[BasicBlockId, Set[IrVarId]] = {}
        self._var_kills: Dict[BasicBlockId, Set[IrVarId]] = {}

    def analyze(self, cfg: ControlFlowGraph) -> LiveAnalysis:
        """
        Performs live-variable analysis on the specified CFG.

        :param cfg: The control flow graph to analyze.
        :return: The results of the analysis.
        """
        self.set_active_cfg(cfg)
        self._compute_ue_var_and_var_kill()
        self._solve(cfg)

        result = LiveAnalysis()
        for blk in self._cfg.get_blocks():
            frag = self._get_fragment(blk)
            result.add_block(blk.get_id(), frag.live_out)

        return result

    def _compute_ue_var_and_var_kill(self):
        """
        Computes the sets of upward-exposed variables and killed variables.
        """
        for blk in self._cfg.get_blocks():
            self._ue_vars[blk.get_id()] = set()
            self._var_kills[blk.get_id()] = set()

            ue_var = self._ue_vars[blk.get_id()]
            var_kills = self._var_kills[blk.get_id()]

            in_mem: Set[IrVarId] = set()

            insts = blk.get_instructions()
            for inst in insts:
                if inst.op == IrOpcode.STORE:
                    if inst.oprs[0].get_id() in var_kills:
                        var_kills.remove(inst.oprs[0].get_id())
                    if inst.oprs[0].get_id() in in_mem:
                        in_mem.remove(inst.oprs[0].get_id())

                elif inst.op == IrOpcode.UNLOAD:
                    if inst.oprs[0].get_id() in in_mem:
                        in_mem.remove(inst.oprs[0].get_id())

                elif inst.op == IrOpcode.LOAD:
                    in_mem.add(inst.oprs[0].get_id())

                else:
                    opr_start = 1 if inst.op.is_opcode_assign() else 0
                    opr_end = inst.op.get_operand_count()

                    for opr in inst.oprs[opr_start:opr_end]:
                        if isinstance(opr, IrVar):
                            var = opr.get_id()
                            if var in in_mem:
                                continue
                            if var not in var_kills:
                                ue_var.add(var)

                    if inst.op.has_extra_operands():
                        for opr in inst.extra:
                            if isinstance(opr, IrVar):
                                var = opr.get_id()
                                if var in in_mem:
                                    continue
                                if var not in var_kills:
                                    ue_var.add(var)

                    if inst.op.is_opcode_assign() and isinstance(inst.oprs[0], IrVar):
                        var_kills.add(inst.oprs[0].get_id())

    def _compute_fragment(self, frag: MyFragment, blk: BasicBlock) -> bool:
        live_out: Set[IrVarId] = set()

        for next in blk.get_next():
            next_frag = self._get_fragment(next)
            next_ue_vars = self._ue_vars[next.get_id()]
            next_var_kills = self._var_kills[next.get_id()]

            for var in next_ue_vars:
                live_out.add(var)

            for var in next_frag.live_out:
                if var not in next_var_kills:
                    live_out.add(var)

        my_frag = self._get_fragment(blk)
        modified = my_frag.live_out != live_out
        if modified:
            my_frag.live_out = live_out
        return modified

    def _compute_init_fragment(self, blk: BasicBlock) -> MyFragment:
        return LiveAnalyzer.MyFragment()
