from ir.assembler import *
from ir.program import *
from .parser import Parser
from .ast import *


class IrTranslator:
    """
    Will translate the AST into IR code
    """

    def __init__(self, ast: Parser):
        self._ast = ast
        self._asm = Assembler()

        # Function compilation state
        self._proc: Procedure = None
        self._func: Function = None
        self._temp = 0

        # Compilation output
        self.proc_list: List[Procedure] = []

    def _get_temp(self):
        t = self._temp
        self._temp += 1
        return IrVar(t)

    def translate(self):
        for func in self._ast.func_list:
            if not func.prototype:
                self._func = func
                self._translate_function()

    def _translate_function(self):
        self._proc = Procedure(self._func.name)
        self.proc_list.append(self._proc)

        if self._func.storage_decl == StorageClass.AUTO:
            self._proc.set_export()

        self._temp = len(self._func.vars) + self._func.num_params + 1

        for i in range(self._func.num_params):
            self._proc.get_params().append(i + 1)

        self._asm.clear()
        self._translate_expr(self._func.code, None)
        self._asm.fix_labels()

        self._proc.insert_instructions(self._asm.get_instructions())

    def _translate_to_operand(self, expr: Expr):
        if isinstance(expr, ExprNumber):
            return IrConst(expr.value)

        elif isinstance(expr, ExprIdent):
            if isinstance(expr.ident, VariableIdentifier):
                return IrVar(self._func.num_params + expr.ident.index + 1)
            elif isinstance(expr.ident, ParameterIdentifier):
                return IrVar(expr.ident.index + 1)
            else:
                return IrName(expr.ident.name)

        elif isinstance(expr, ExprCast):
            return self._translate_to_operand(expr.expr)

        else:
            a = self._get_temp()
            self._translate_expr(expr, a)
            return a

    def _translate_expr(self, expr: Expr, dest):
        if isinstance(expr, ExprNumber):
            assert dest is not None
            self._asm.emit_assign(dest, IrConst(expr.value))

        elif isinstance(expr, ExprBinary):

            if dest is not None:
                if expr.op in '+-/*%' or expr.op in ['==']:
                    opr1 = self._translate_to_operand(expr.left)
                    opr2 = self._translate_to_operand(expr.right)

                    if expr.op == '+':
                        self._asm.emit_assign_add(dest, opr1, opr2)

                    elif expr.op == '-':
                        self._asm.emit_assign_sub(dest, opr1, opr2)

                    elif expr.op == '/':
                        self._asm.emit_assign_div(dest, opr1, opr2)

                    elif expr.op == '*':
                        self._asm.emit_assign_mul(dest, opr1, opr2)

                    elif expr.op == '%':
                        self._asm.emit_assign_mod(dest, opr1, opr2)

                    elif expr.op == '==':
                        end = self._asm.make_label()
                        self._asm.emit_assign(dest, IrConst(0))
                        self._asm.emit_cmp(opr1, opr2)
                        self._asm.emit_jne(IrLabel(end))
                        self._asm.emit_assign(dest, IrConst(1))
                        self._asm.mark_label(end)

                    # TODO: more comparison implementations

                elif expr.op == '&&':
                    setfalse = self._asm.make_label()
                    end = self._asm.make_label()
                    self._asm.emit_cmp(self._translate_to_operand(expr.left), IrConst(0))
                    self._asm.emit_je(IrLabel(setfalse))
                    self._asm.emit_cmp(self._translate_to_operand(expr.right), IrConst(0))
                    self._asm.emit_je(IrLabel(setfalse))
                    self._asm.emit_assign(dest, IrConst(1))
                    self._asm.emit_jmp(IrLabel(end))
                    self._asm.mark_label(setfalse)
                    self._asm.emit_assign(dest, IrConst(0))
                    self._asm.mark_label(end)

                else:
                    assert False, f"{expr} [{expr.op}] - {type(expr)} | {dest}"
            else:
                opr1 = self._translate_to_operand(expr.left)
                if expr.op == '||':
                    end = self._asm.make_label()
                    self._asm.emit_cmp(opr1, IrConst(0))
                    self._asm.emit_jne(IrLabel(end))
                    self._translate_expr(expr.right, None)
                    self._asm.mark_label(end)

                elif expr.op == '&&':
                    end = self._asm.make_label()
                    self._asm.emit_cmp(opr1, IrConst(0))
                    self._asm.emit_je(IrLabel(end))
                    self._translate_expr(expr.right, None)
                    self._asm.mark_label(end)
                else:
                    assert False, dest

        elif isinstance(expr, ExprCall):
            # handle arguments
            operands = []
            for arg in expr.args:
                operands.append(self._translate_to_operand(arg))

            if dest is None:
                call = self._asm.emit_call(self._translate_to_operand(expr.func))
                for opr in operands:
                    call.push_extra(opr)
            else:
                call = self._asm.emit_assign_call(dest, self._translate_to_operand(expr.func))
                for opr in operands:
                    call.push_extra(opr)

        elif isinstance(expr, ExprComma):
            for ex in expr.exprs[:-1]:
                self._translate_expr(ex, None)
            self._translate_expr(expr.exprs[-1], dest)

        elif isinstance(expr, ExprCopy):
            src = self._translate_to_operand(expr.source)
            dst = self._translate_to_operand(expr.destination)

            self._asm.emit_assign(dst, src)

            if dest is not None:
                self._asm.emit_assign(dest, src)

        elif isinstance(expr, ExprReturn):
            assert dest is None

            if expr.expr is not None:
                opr1 = self._translate_to_operand(expr.expr)
                self._asm.emit_ret(opr1)

            else:
                self._asm.emit_retn()

        elif isinstance(expr, ExprAddrof):
            assert dest is not None
            self._asm.emit_assign_addrof(dest, self._translate_to_operand(expr.expr))

        elif isinstance(expr, ExprDeref):
            assert dest is not None
            self._asm.emit_assign_read(dest, self._translate_to_operand(expr.expr))

        else:
            assert False, expr
