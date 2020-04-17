from .parser import Parser
from .ast import *


class Optimizer:

    def __init__(self, parser):
        self.parser = parser

    def _find_pure_functions(self):
        for f in self.parser.func_list:
            f.pure_known = False
            f.pure = False

        def check_function(f):

            if f.pure_known:
                return False

            unknown_functions = [False]
            side_effects = False

            def check_side_effects(expr, lvalue=False):
                # Iterate all the expressions
                if isinstance(expr, ExprComma):
                    for e in expr.exprs:
                        if check_side_effects(e):
                            return True
                    return False
                elif isinstance(expr, ExprCopy):
                    return check_side_effects(expr.destination, True) or check_side_effects(expr.source)
                elif isinstance(expr, ExprBinary):
                    return check_side_effects(expr.right) or check_side_effects(expr.left)
                elif isinstance(expr, ExprLoop):
                    return check_side_effects(expr.cond) or check_side_effects(expr.body)
                elif isinstance(expr, ExprAddrof):
                    return check_side_effects(expr.expr)

                # if this is an lvalue and we have a deref we assume side effects
                elif isinstance(expr, ExprDeref):
                    if lvalue:
                        return True
                    else:
                        return check_side_effects(expr.expr)

                elif isinstance(expr, ExprCall):
                    if check_side_effects(expr.func):
                        return True

                    for arg in expr.args:
                        if check_side_effects(arg):
                            return True

                    # assume indirect function calls have side effects
                    if not isinstance(expr.func, ExprIdent) or not isinstance(expr.func.ident, FunctionIdentifier):
                        return True
                    func = self.parser.func_list[expr.func.ident.index]

                    # This function has side effects
                    if func.pure_known and not func.pure:
                        return True

                    if not func.pure_known and func.name != f.name:
                        unknown_functions[0] = True

                else:
                    return False

            side_effects = check_side_effects(f.code)

            if side_effects or not unknown_functions[0]:
                f.pure_known = True
                f.pure = not side_effects
                return True

            return False

        # Iterate until no improvements are found
        count = 0

        for f in self.parser.func_list:
            if check_function(f):
                count += 1

        while count != 0:
            count = 0
            for f in self.parser.func_list:
                if check_function(f):
                    count += 1

    def _constant_fold(self, expr, stmt):
        # TODO: on assign expressions we can probably do some kind of fold inside binary operation
        #       so (5 + (a = 5)) can turn into (a = 5, 10)

        if isinstance(expr, ExprComma):
            new_exprs = []
            for i, e in enumerate(expr.exprs):
                e = self._constant_fold(e, stmt)

                # If we got to a return just don't continue
                if isinstance(e, ExprReturn):
                    new_exprs.append(e)
                    break

                # elif isinstance(e, ExprLoop):
                #
                #     # Break on loops that never exit
                #     # if isinstance(e.cond, ExprNumber) and e.cond.value != 0:
                #     #     new_exprs.append(e.body)
                #     #     break
                #     #
                #     # else:
                #     new_exprs.append(e)

                # Ignore nops
                elif isinstance(e, ExprNop):
                    continue

                # only add if has side effects
                else:
                    # inside statements we only append non-pure nodes
                    if stmt:
                        if not e.is_pure(self.parser):
                            new_exprs.append(e)

                    # Outside of that only add non-pure and the last element
                    else:
                        if not e.is_pure(self.parser) or i == len(expr.exprs) - 1:
                            new_exprs.append(e)

            if len(new_exprs) == 0:
                return ExprNop()

            if len(new_exprs) == 1:
                return new_exprs[0]

            expr = ExprComma().add(new_exprs)
            return expr

        elif isinstance(expr, ExprReturn):
            expr.expr = self._constant_fold(expr.expr, False)

        elif isinstance(expr, ExprBinary):
            # TODO: support for multiple expressions in the binary expressions, that will allow
            #       for better constant folding

            expr.left = self._constant_fold(expr.left, False)
            expr.right = self._constant_fold(expr.right, False)

            if expr.op == '&&':
                # We know both
                if isinstance(expr.left, ExprNumber) and isinstance(expr.right, ExprNumber):
                    return 1 if expr.left.value != 0 and expr.right.value != 0 else 0

                # If we first have 0 we can just return 0
                if isinstance(expr.left, ExprNumber):
                    if expr.left.value == 0:
                        return ExprNumber(0)
                    else:
                        return expr.right

                # if the second is a 0 we can just replace this with a comma operator
                if isinstance(expr.right, ExprNumber) and expr.left.value == 0:
                    return ExprComma().add(expr.left).add(ExprNumber(0))

            elif expr.op == '||':
                # We know both
                if isinstance(expr.left, ExprNumber) and isinstance(expr.right, ExprNumber):
                    return ExprNumber(1) if expr.left.value != 0 or expr.right.value != 0 else ExprNumber(0)

                # Left is constant
                if isinstance(expr.left, ExprNumber):
                    # if the left is a 0, then we can simply remove it and
                    # return the right expression
                    if expr.left.value == 0:
                        return expr.right

                    # if left is 1, we can ommit the right expression
                    else:
                        return ExprNumber(1)

                # Right is a const
                if isinstance(expr.right, ExprNumber):
                    # If the const is 0 then the left will be the one
                    # who says what will happen
                    if expr.right.value == 0:
                        return expr.left

                    # If the const is a 1, then it will always be 1
                    # and we can always run the left
                    else:
                        return ExprComma().add(expr.left).add(ExprNumber(1))

            else:
                # The numbers are know and we can calculate them
                if isinstance(expr.left, ExprNumber) and isinstance(expr.right, ExprNumber):
                    return ExprNumber(int(eval(f'{expr.left} {expr.op} {expr.right}')))

                # One of the sides is 0
                elif (isinstance(expr.left, ExprNumber) and expr.left.value == 0) or (
                        isinstance(expr.right, ExprNumber) and expr.right.value == 0):
                    if expr.op == '*':
                        return ExprNumber(0)
                    elif expr.op == '+':
                        return expr.right if isinstance(expr.left, ExprNumber) else expr.left

                # Left is 0
                if isinstance(expr.left, ExprNumber) and expr.left.value == 0:
                    if expr.op == '/':
                        return ExprNumber(0)

                # right is 0
                elif isinstance(expr.right, ExprNumber) and expr.right.value == 0:
                    if expr.op == '-':
                        return expr.left

        elif isinstance(expr, ExprDeref):
            expr.expr = self._constant_fold(expr.expr, False)
            # deref an addrof
            if isinstance(expr.expr, ExprAddrof):
                return expr.expr.expr

        elif isinstance(expr, ExprAddrof):
            expr.expr = self._constant_fold(expr.expr, False)
            if isinstance(expr.expr, ExprDeref):
                return expr.expr.expr

        elif isinstance(expr, ExprCopy):
            expr.source = self._constant_fold(expr.source, False)
            expr.destination = self._constant_fold(expr.destination, False)
            # assignment equals to itself and has no side effects
            if expr.source == expr.destination and expr.source.is_pure(self):
                return expr.destination

        elif isinstance(expr, ExprLoop):
            expr.cond = self._constant_fold(expr.cond, False)
            expr.body = self._constant_fold(expr.body, True)

            # The loop has a constant 0
            if isinstance(expr.cond, ExprNumber) and expr.cond.value == 0:
                return ExprNop()

        elif isinstance(expr, ExprCast):
            expr = self._constant_fold(expr.expr, False)

        return expr

    def optimize(self):
        last = str(self)

        for f in self.parser.global_vars:
            if f.value is not None:
                f.value = self._constant_fold(f.value, False).value

        self._find_pure_functions()
        for f in self.parser.func_list:
            f.code = self._constant_fold(f.code, True)

        while str(self) != last:
            last = str(self)
            self._find_pure_functions()
            for f in self.parser.func_list:
                f.code = self._constant_fold(f.code, True)
