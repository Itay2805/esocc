from .ir import *
from typing import Dict


class BasicBlock:
    """
    A straight-line piece of code without any jumps.
    """

    def __init__(self, xid: BasicBlockId):
        self._id: BasicBlockId = xid
        self._insts: List[IrInstruction] = []
        self._base = 0
        self._prev: List[BasicBlock] = []
        self._next: List[BasicBlock] = []

    def get_id(self):
        return self._id

    def get_instructions(self):
        return self._insts

    def clear_instructions(self):
        self._insts.clear()

    def get_prev(self):
        return self._prev

    def get_next(self):
        return self._next

    def get_base(self):
        return self._base

    def set_base(self, base: int):
        self._base = base

    def push_instruction(self, inst: IrInstruction):
        """
        Inserts the specified instruction to the end of the block.
        """
        self._insts.append(inst)

    def push_instruction_front(self, inst: IrInstruction):
        """
        Inserts the specified instruction to the beginning of the block.
        """
        assert isinstance(inst, IrInstruction)
        self._insts.insert(0, inst)

    def push_instructions_front(self, insts: List[IrInstruction]):
        """
        Inserts a range of instructions to the beginning of the block.
        """
        for inst in reversed(insts):
            self.push_instruction_front(inst)

    def add_prev(self, blk):
        """
        Inserts a basic block to this block's list of predecessor blocks.
        """
        self._prev.append(blk)

    def add_next(self, blk):
        """
        Inserts a basic block to this block's list of successor blocks.
        """
        self._next.append(blk)


class ControlFlowGraphType(Enum):
    """
    Describes the type of a CFG's contents.
    """

    NORMAL = 'normal'
    SSA = 'ssa'


class ControlFlowGraph:
    """
    A control flow graph!
    """

    def __init__(self, xtype: ControlFlowGraphType, root: BasicBlock):
        self._type = xtype
        self._root = root
        self._block_map: Dict[BasicBlockId, BasicBlock] = {}
        self._blocks: List[BasicBlock] = []

    def get_type(self):
        return self._type

    def set_type(self, xtype: ControlFlowGraphType):
        self._type = xtype

    def get_root(self):
        return self._root

    def get_blocks(self):
        return self._blocks

    def __len__(self):
        return len(self._blocks)

    def map_block(self, xid: BasicBlockId, blk: BasicBlock):
        """
        Inserts the specified <id, block> pair to the CFG.
        """
        self._block_map[xid] = blk
        self._blocks.append(blk)

    def find_block(self, xid: BasicBlockId) -> BasicBlock:
        """
        Searches for a block in the CFG by ID.
        """
        return self._block_map[xid]


def _is_branch_instruction(inst: IrInstruction):
    return inst.op in [
        IrOpcode.JMP,
        IrOpcode.JE,
        IrOpcode.JNE,
        IrOpcode.JL,
        IrOpcode.JLE,
        IrOpcode.JG,
        IrOpcode.JGE,
    ]


def _is_end_instruction(inst: IrInstruction):
    return inst.op in [
        IrOpcode.RET,
        IrOpcode.RETN,
    ]


class ControlFlowAnalyzer:
    """
    Performs control flow analysis.
    """

    def __init__(self):
        self._next_blk_id = 1

    def build_graph(self, insts: List[IrInstruction]) -> ControlFlowGraph:
        """
        Builds a control flow graph.
        """

        if len(insts) == 0:
            root = BasicBlock(self._next_blk_id)
            self._next_blk_id += 1
            cfg = ControlFlowGraph(ControlFlowGraphType.NORMAL, root)
            cfg.map_block(root.get_id(), root)
            return cfg

        # pick leads
        leaders = [False] * len(insts)
        leaders[0] = True  # first instruction is a leader
        for i in range(len(insts)):
            inst = insts[i]

            if _is_branch_instruction(inst):
                # Mark next instruction and target instruction as leader
                if i != len(insts) - 1:
                    leaders[i + 1] = True
                assert isinstance(inst.oprs[0], IrOffset), "branch instruction operand is not an offset"
                leaders[i + 1 + inst.oprs[0].get_offset()] = True

            elif _is_end_instruction(inst):
                # Mark next instruction as leader
                if i != len(insts) - 1:
                    leaders[i + 1] = True

        # use leaders to build basic blocks
        blocks = {}
        i = 0
        while i < len(insts):
            start = i
            blk = BasicBlock(self._next_blk_id)
            self._next_blk_id += 1

            blk.push_instruction(insts[i])
            i += 1

            while i < len(insts) and not leaders[i]:
                blk.push_instruction(insts[i])
                i += 1

            blocks[start] = blk

        # link blocks together
        for p in blocks:
            blk = blocks[p]
            last = blk.get_instructions()[-1]

            if _is_branch_instruction(last):
                target_idx = p + len(blk.get_instructions()) + last.oprs[0].get_offset()
                if target_idx in blocks:
                    target = blocks[target_idx]
                    target.add_prev(blk)
                    blk.add_next(target)

                    last.oprs[0] = IrBlockRef(target.get_id())

            if last.op != IrOpcode.JMP and not _is_end_instruction(last):
                next_idx = p + len(blk.get_instructions())
                if next_idx in blocks:
                    next_blk = blocks[next_idx]
                    next_blk.add_prev(blk)
                    blk.add_next(next_blk)

        cfg = ControlFlowGraph(ControlFlowGraphType.NORMAL, blocks[0])
        for p in blocks:
            cfg.map_block(blocks[p].get_id(), blocks[p])
            blocks[p].set_base(p)
        return cfg


def make_cfg(insts: List[IrInstruction]) -> ControlFlowGraph:
    """
    Static method for convenience.
    """
    an = ControlFlowAnalyzer()
    return an.build_graph(insts)
