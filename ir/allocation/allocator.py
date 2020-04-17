from ..control_flow import *


RegisterColor = int
"""
Stores the ID of a virtual register.
"""


class RegisterAllocation:
    """
    Stores the results returned by a register allocator.
    """

    def __init__(self):
        self._color_map: Dict[IrVarId, RegisterColor] = {}

    def set_color(self, var: IrVarId, col: RegisterColor):
        """
        Sets the color of the specified variable.
        """
        self._color_map[var] = col

    def get_color(self, var: IrVarId) -> RegisterColor:
        """
        Returns the color of the specified variable.
        """
        assert var in self._color_map, "variable has no color"
        return self._color_map[var]


class RegisterAllocator:
    """
    Base class for register allocators.
    """

    def allocate(self, cfg: ControlFlowGraph, num_colors: int) -> RegisterAllocation:
        """
        Performs register allocation.

        Processes the specified control flow graph and determines which
        variables get mapped to what registers, and which variables get spilled
        into memory.

        NOTE: The control graph is transformed to contain the necessary spill
              code.

        :param cfg: The control flow graph to process.
        :param num_colors: Max amount of physical registers available.
        """
        raise NotImplementedError()
