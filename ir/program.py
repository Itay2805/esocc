from .ir import *


class Procedure:
    """
    An IR procedure/function.
    """

    def __init__(self, name: str):
        self._name = name
        self._params: List[IrVarId] = []
        self._body: List[IrInstruction] = []
        self._export = False

    def set_export(self):
        self._export = True

    def is_exported(self):
        return self._export

    def get_name(self):
        return self._name

    def get_params(self):
        return self._params

    def get_body(self):
        return self._body

    def insert_instructions(self, insts: List[IrInstruction]):
        for inst in insts:
            self._body.append(inst)
