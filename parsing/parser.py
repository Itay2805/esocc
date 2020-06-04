from .tokenizer import *
from .ast import *


class Parser(Tokenizer):

    class Scope:

        def __init__(self):
            self.idents = {}  # type: Dict[str, Identifier]
            self.type_defs = {}  # type: Dict[Tuple[str], CType]

    def __init__(self, stream: str, filename: str = '<unknown>'):
        super().__init__(stream, filename)
        self._scopes: List[Parser.Scope] = []
        self.func_list: List[Function] = []
        self.global_vars: List[Variable] = []
        self.func: Function = None

        # Setup the global scope with all the default types
        self._push_scope()
        self._add_typedef(['char'], CInteger(8, True))
        self._add_typedef(['signed', 'char'], CInteger(8, True))
        self._add_typedef(['unsigned', 'char'], CInteger(8, False))
        self._add_typedef(['short'], CInteger(16, True))
        self._add_typedef(['signed', 'short'], CInteger(16, True))
        self._add_typedef(['unsigned', 'short'], CInteger(16, False))
        self._add_typedef(['int'], CInteger(16, True))
        self._add_typedef(['signed', 'int'], CInteger(16, True))
        self._add_typedef(['signed'], CInteger(16, True))
        self._add_typedef(['unsigned', 'int'], CInteger(16, False))
        self._add_typedef(['unsigned'], CInteger(16, False))
        self._add_typedef(['long'], CInteger(32, True))
        self._add_typedef(['signed', 'long'], CInteger(32, True))
        self._add_typedef(['unsigned', 'long'], CInteger(32, False))

        self._temp_counter = 0
        self._loop_nesting = 0
        self.got_errors = False

        # Start the parsing
        self.next_token()

    ####################################################################################################################
    # Helpers
    ####################################################################################################################

    def _define(self, name: str, ident: Identifier) -> ExprIdent:
        if self._use(name) is not None:
            return None
        self._scopes[-1].idents[name] = ident
        return ExprIdent(ident)

    def _def_var(self, name: str, typ: CType, storage: StorageClass) -> ExprIdent:
        if self.func is not None:
            ret = self._define(name, VariableIdentifier(name, len(self.func.vars)))
        else:
            ret = self._define(name, GlobalIdentifier(name, len(self.global_vars)))

        if ret is None:
            return None

        var = Variable(ret.ident, typ, storage)

        if self.func is not None:
            self.func.vars.append(var)
            if storage == StorageClass.STATIC:
                self.global_vars.append(var)
        else:
            self.global_vars.append(var)

        return ret

    def _def_param(self, name, typ) -> ExprIdent:
        ret = self._define(name, ParameterIdentifier(name, self.func.num_params))
        if ret is None:
            return None
        self.func.type.param_types.append(typ)
        self.func.num_params += 1
        return ret

    def _def_fun(self, name) -> ExprIdent:
        ret = self._define(name, FunctionIdentifier(name, len(self.func_list)))
        return ret

    def _temp(self, typ) -> ExprIdent:
        ret = self._def_var(f'$TEMP{self._temp_counter}', typ, StorageClass.AUTO)
        self._temp_counter += 1
        return ret

    def _use(self, name: str) -> ExprIdent:
        for scope in reversed(self._scopes):
            if name in scope.idents:
                return ExprIdent(scope.idents[name])
        return None

    def _resolve_type(self, name: List[str] or str or Tuple[str]) -> CType:
        # Turn to array if needed
        if name is str:
            name = [name]

        # Normalize
        n = list(name)
        n.sort()
        n = tuple(n)

        # Search for it
        for scope in reversed(self._scopes):
            if n in scope.type_defs:
                return scope.type_defs[n]

        return None

    def _type_in_scope(self, name: List[str] or str or Tuple[str]):
        # Turn to array if needed
        if name is str:
            name = [name]

        # Normalize
        n = list(name)
        n.sort()
        n = tuple(n)

        # search for it in the current scope
        if n in self._scopes[-1].type_defs:
            return self._scopes[-1].type_defs[n]

        return None

    def _add_function(self, name: str, typ: CType):
        self.func = Function(name)
        self.func.type.ret_type = typ
        self.func.code = ExprComma()
        self.func.prototype = False
        self.func_list.append(self.func)

    def _add_typedef(self, name: List[str], typ: CType):
        nlst = list(name)
        nlst.sort()
        self._scopes[-1].type_defs[tuple(nlst)] = typ

    def _push_scope(self):
        self._scopes.append(Parser.Scope())

    def _pop_scope(self):
        self._scopes.pop()

    @staticmethod
    def _combine_pos(pos1: CodePosition, pos2: CodePosition):
        if pos2 is None:
            return pos1
        return CodePosition(pos1.start_line, pos2.end_line, pos1.start_column, pos2.end_column)

    def _check_assignment(self, e1: Expr or CType, e2: Expr or CType, action: str):
        if isinstance(e1, Expr):
            pos1 = e1.pos
            t1 = e1.resolve_type(self)
        else:
            t1 = e1

        if isinstance(e2, Expr):
            pos2 = e2.pos
            t2 = e2.resolve_type(self)
        else:
            t2 = e2

        if isinstance(t1, CPointer) and isinstance(t2, CInteger):
            self.report_warn(f'{action} makes pointer from integer without a cast', e2.pos)
            return True
        elif isinstance(t1, CInteger) and (isinstance(t2, CPointer) or isinstance(t2, CArray)):
            self.report_warn(f'{action} makes integer from pointer without a cast', e2.pos)
            return True
        elif isinstance(t1, CInteger) and isinstance(t2, CInteger):
            return True
        elif isinstance(t1, CPointer) and (isinstance(t2, CPointer) or (isinstance(t2, CArray))):
            if t2.type != CVoid() and t1.type != CVoid() and t1.type != t2.type:
                self.report_warn(f'{action} from incompatible pointer type', e2.pos)
            return True
        else:
            if action == 'return':
                action = 'returning'
            elif action == 'initialization':
                action = 'initializing'
            self.report_error(f'incompatible types when {action} type `{t1}` using type `{t2}`', e2.pos)
            return False

    def _check_binary_op(self, op: str, pos: CodePosition, e1: Expr, e2: Expr):
        t1 = e1.resolve_type(self)
        t2 = e2.resolve_type(self)

        valid = False

        if op in ['+', '-', '==', '!=', '||', '&&']:
            valid = (isinstance(t1, CPointer) or isinstance(t1, CInteger)) and \
                   (isinstance(t2, CPointer) or isinstance(t2, CInteger))
        elif op in ['<<', '>>', '*', '/', '%', '&', '|', '^']:
            valid = isinstance(t1, CInteger) and isinstance(t2, CInteger)
        else:
            assert False

        if not valid:
            self.report_error(f'invalid operands to binary `{op}` (have `{t1}` and `{t2}`)', pos)

    def _is_lvalue(self, e: Expr):
        return isinstance(e, ExprIdent) or isinstance(e, ExprDeref)

    ####################################################################################################################
    # Error reporting
    ####################################################################################################################

    BOLD = '\033[01m'
    RESET = '\033[0m'
    GREEN = '\033[32m'
    RED = '\033[31m'
    YELLOW = '\033[33m'

    def report(self, typ: str, col: str, msg: str, pos=None, inside_function=True):
        if pos is None:
            pos = self.token.pos

        if inside_function and self.func is not None:
            print(f'{Parser.BOLD}{self.filename}:{Parser.RESET} In function `{Parser.BOLD}{self.func.name}{Parser.RESET}`')

        print(f'{Parser.BOLD}{self.filename}:{pos.start_line + 1}:{pos.start_column + 1}:{Parser.RESET} {col}{Parser.BOLD}{typ}:{Parser.RESET} {msg}')

        line = self.lines[pos.start_line]
        line = line[:pos.start_column] + Parser.BOLD + line[pos.start_column:pos.end_column] + Parser.RESET + line[pos.end_column:]
        print(line)

        c = ''
        for i in range(pos.start_column):
            if self.lines[pos.start_line][i] == '\t':
                c += '\t'
            else:
                c += ' '

        print(c + Parser.BOLD + col + '^' + '~' * (pos.end_column - pos.start_column - 1) + Parser.RESET)
        print()

    def report_error(self, msg: str, pos=None, inside_function=True):
        self.report('error', Parser.RED, msg, pos, inside_function)
        self.got_errors = True

    def report_warn(self, msg: str, pos=None, inside_function=True):
        self.report('warning', Parser.YELLOW, msg, pos, inside_function)

    def report_fatal_error(self, msg: str, pos=None, inside_function=True):
        self.report('error', Parser.RED, msg, pos, inside_function)
        exit(-1)

    ####################################################################################################################
    # Expression parsing
    ####################################################################################################################

    def _parse_literal(self):
        if self.is_token(IntToken):
            val = self.token.value
            pos = self.token.pos
            self.next_token()

            # Integer Literal modifiers
            # Kinda hacky but whatever
            if self.is_token(IdentToken) and self.token.value == 'u':
                typ = CInteger(16, False)
                self.next_token()
            elif self.is_token(IdentToken) and self.token.value == 'ul':
                typ = CInteger(32, False)
                self.next_token()
            elif self.is_token(IdentToken) and self.token.value == 'l':
                typ = CInteger(32, True)
                self.next_token()
            else:
                typ = CInteger(16, True)

            return ExprNumber(val, typ, pos)

        elif self.is_token(IdentToken):
            val = self.token.value
            pos = self.token.pos
            self.next_token()
            expr = self._use(val)
            if expr is None:
                self.report_fatal_error(f'`{val}` undeclared', pos)
            expr.pos = pos
            return expr

        elif self.match_token('('):
            expr = self._parse_expr()
            self.expect_token(')')
            return expr

        else:
            self.report_fatal_error(f'expected expression before {self.token}')

    def _parse_postfix(self):
        x = self._parse_literal()

        while True:

            pos = self.token.pos
            if self.is_token('++') or self.is_token('--'):
                op = self.token.value[0]
                self.next_token()

                if not self._is_lvalue(x):
                    s = 'increment' if op == '+' else 'decrement'
                    self.report_error(f'lvalue required asm {s} operand', pos)

                typ = x.resolve_type(self)
                if isinstance(typ, CPointer):
                    step_size = typ.type.sizeof()
                else:
                    step_size = 1

                self._check_binary_op(op, pos, x, ExprNumber(step_size, CInteger(16, False)))

                temp = self._temp(x.resolve_type(self))
                if x.is_pure(self):
                    x = ExprComma(self._combine_pos(x.pos, pos))\
                        .add(ExprCopy(x, temp))\
                        .add(ExprCopy(ExprBinary(x, op, ExprNumber(step_size, CInteger(16, False))), x))\
                        .add(temp)
                else:
                    temp2 = self._temp(x.resolve_type(self))
                    x = ExprComma(self._combine_pos(x.pos, pos))\
                        .add(ExprCopy(ExprAddrof(x), temp))\
                        .add(ExprCopy(ExprDeref(temp), temp2))\
                        .add(ExprCopy(ExprBinary(ExprDeref(temp), op, ExprNumber(step_size, CInteger(16, False))), ExprDeref(temp)))\
                        .add(temp2)

            elif self.match_token('['):
                sub = self._parse_expr()
                temp_pos = self.token.pos
                self.expect_token(']')

                arr_type = x.resolve_type(self)
                if not isinstance(arr_type, CPointer) and not isinstance(arr_type, CArray):
                    self.report_fatal_error('subscripted value is neither array nor pointer', pos)

                if not isinstance(sub.resolve_type(self), CInteger):
                    self.report_error('array subscript is not an integer', pos)

                multiply = 1
                if isinstance(arr_type, CPointer) or isinstance(arr_type, CArray):
                    multiply = arr_type.type.sizeof()

                x = ExprDeref(ExprBinary(x, '+', ExprBinary(sub, '*', ExprNumber(multiply))), self._combine_pos(x.pos, temp_pos))

            elif self.match_token('.'):
                member, mempos = self.expect_ident()

                typ = x.resolve_type(self)

                if not isinstance(typ, CStruct):
                    self.report_fatal_error(f'request for member `{member}` in something not a structure or union', pos)

                memtyp = typ.get_field(member)
                if memtyp is None:
                    self.report_fatal_error(f'`{typ}` has no member named `{member}`')

                x = ExprDeref(ExprCast(ExprBinary(ExprAddrof(x), '+', ExprNumber(typ.offsetof(member))), CPointer(memtyp)), self._combine_pos(x.pos, mempos))

            elif self.match_token('->'):
                member, mempos = self.expect_ident()

                typ = x.resolve_type(self)

                if not isinstance(typ, CPointer):
                    self.report_fatal_error(f'invalid type argument of `->` (has `{typ}`)', pos)

                typ = typ.type

                if not isinstance(typ, CStruct):
                    self.report_fatal_error(f'request for member `{member}` in something not a structure or union', pos)

                memtyp = typ.get_field(member)
                if memtyp is None:
                    self.report_fatal_error(f'{typ} has not member named `{member}`')

                x = ExprDeref(ExprCast(ExprBinary(x, '+', ExprNumber(typ.offsetof(member))), CPointer(memtyp)), self._combine_pos(x.pos, mempos))

            elif self.match_token('('):
                args = []
                temp_pos = self.token.pos
                while not self.match_token(')'):
                    args.append(self._parse_assignment())
                    if not self.is_token(')'):
                        self.expect_token(',')
                    temp_pos = self.token.pos

                typ = x.resolve_type(self)
                if not isinstance(typ, CFunction):
                    self.report_fatal_error(f'called object `{x}` is not a function or function pointer', x.pos)

                if len(args) < len(typ.param_types):
                    self.report_error(f'too few arguments to function `{x}`', x.pos)

                if len(args) > len(typ.param_types):
                    self.report_error(f'too many arguments to function `{x}`', x.pos)

                for i in range(len(typ.param_types)):
                    arg = args[i]
                    t = typ.param_types[i]
                    self._check_assignment(t, arg, 'passing argument')

                x = ExprCall(x, args, self._combine_pos(x.pos, temp_pos))

            else:
                break

        return x

    def _parse_prefix(self):
        pos = self.token.pos

        # Address-of
        if self.match_token('&'):
            e = self._parse_prefix()
            if not self._is_lvalue(e):
                self.token.pos = pos
                self.report_error('lvalue required asm unary `&` operand')
            return ExprAddrof(e, self._combine_pos(pos, e.pos))

        elif self.match_token('*'):
            e = self._parse_prefix()
            typ = e.resolve_type(self)
            pos = self._combine_pos(pos, e.pos)

            if not isinstance(typ, CPointer):
                self.report_error(f'invalid type argument of unary `*` (have `{typ}`)', pos)

            if isinstance(typ.type, CVoid):
                self.report_error('dereferencing `void *` pointer', pos)

            # Deref of function ptr returns a function ptr
            if isinstance(typ.type, CFunction):
                return e
            else:
                return ExprDeref(e, self._combine_pos(pos, e.pos))

        elif self.match_token('~'):
            e = self._parse_prefix()
            typ = e.resolve_type(self)
            pos = self._combine_pos(pos, e.pos)
            if not isinstance(typ, CInteger):
                self.report_error(f'invalid type argument of unary `~` (have `{typ}`)', pos)
            return ExprBinary(e, '^', ExprNumber(0xFFFF))

        elif self.match_token('!'):
            e = self._parse_prefix()
            typ = e.resolve_type(self)
            pos = self._combine_pos(pos, e.pos)
            if not isinstance(typ, CInteger):
                self.report_error(f'invalid type argument of unary `!` (have `{typ}`)', pos)
            return ExprBinary(e, '==', ExprNumber(0), self._combine_pos(pos, e.pos))

        elif self.is_token('++') or self.is_token('--'):
            op = self.token.value[0]
            self.next_token()
            e = self._parse_prefix()

            if not self._is_lvalue(e):
                s = 'decrement' if op == '-' else 'increment'
                self.report_error(f'lvalue required asm {s} operand', pos)

            if e.is_pure(self):
                return ExprCopy(ExprBinary(e, op, ExprNumber(1)), e)
            else:
                temp = self._temp(e.resolve_type(self))
                return ExprComma()\
                    .add(ExprCopy(ExprAddrof(e), temp))\
                    .add(ExprCopy(ExprBinary(ExprDeref(temp), op, ExprNumber(1)), ExprDeref(temp)))

        # Size-of
        elif self.match_keyword('sizeof'):
            xtype = self._parse_prefix().resolve_type(self).sizeof()
            return ExprNumber(xtype, self._combine_pos(pos, self.token.pos))

        # Type cast
        elif self.is_token('('):
            self.save()
            self.next_token()
            typ = self._parse_type(False)
            if typ is not None:
                self.discard()
                typ = self._parse_type_prefix(typ)
                self.expect_token(')')
                # TODO: check the cast is actually doable
                # TODO: Compound literal
                return ExprCast(self._parse_prefix(), typ)
            else:
                self.restore()

        return self._parse_postfix()

    def _parse_multiplicative(self):
        e1 = self._parse_prefix()
        while self.is_token('*') or self.is_token('/') or self.is_token('%'):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_prefix()
            self._check_binary_op(op, pos, e1, e2)
            e1 = ExprBinary(e1, op, e2, self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_additive(self):
        e1 = self._parse_multiplicative()
        while self.is_token('+') or self.is_token('-'):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_multiplicative()
            self._check_binary_op(op, pos, e1, e2)
            e1 = ExprBinary(e1, op, e2, self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_shift(self):
        e1 = self._parse_additive()
        while self.is_token('>>') or self.is_token('<<'):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_additive()
            self._check_binary_op(op, pos, e1, e2)
            e1 = ExprBinary(e1, op, e2, self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_relational(self):
        # e1 = self._parse_shift()
        # while self.is_token('<') or self.is_token('>') or self.is_token('>=') or self.is_token('<='):
        #     op = self.token
        #     self.next_token()
        #     e2 = self._parse_shift()
        #     self._check_binary_op(op, e1, e2)
        #     e1 = ExprBinary(self._expand_pos(e1.pos, self.token.pos), e1, op.value, e2)
        # return e1
        return self._parse_shift()

    def _parse_equality(self):
        e1 = self._parse_relational()
        while self.is_token('==') or self.is_token('!='):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_relational()
            self._check_binary_op(op, pos, e1, e2)
            if op == '==':
                e1 = ExprBinary(e1, op, e2, self._combine_pos(e1.pos, e2.pos))
            else:
                e1 = ExprBinary(ExprBinary(e1, '==', e2), '==', ExprNumber(0), self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_bitwise_and(self):
        e1 = self._parse_equality()
        while self.is_token('&'):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_equality()
            self._check_binary_op(op, pos, e1, e2)
            e1 = ExprBinary(e1, op, e2, self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_bitwise_xor(self):
        e1 = self._parse_equality()
        while self.is_token('^'):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_equality()
            self._check_binary_op(op, pos, e1, e2)
            e1 = ExprBinary(e1, op, e2, self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_bitwise_or(self):
        e1 = self._parse_equality()
        while self.is_token('|'):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_equality()
            self._check_binary_op(op, pos, e1, e2)
            e1 = ExprBinary(e1, op, e2, self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_logical_and(self):
        e1 = self._parse_bitwise_or()
        while self.is_token('&&'):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_bitwise_or()
            self._check_binary_op(op, pos, e1, e2)
            e1 = ExprBinary(e1, op, e2, self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_logical_or(self):
        e1 = self._parse_logical_and()
        while self.is_token('||'):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_logical_and()
            self._check_binary_op(op, pos, e1, e2)
            e1 = ExprBinary(e1, op, e2, self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_conditional(self):
        x = self._parse_logical_or()

        if self.match_token('?'):
            y = self._parse_conditional()
            pos = self.token.pos
            self.expect_token(':')
            z = self._parse_conditional()

            yt = y.resolve_type(self)
            zt = z.resolve_type(self)
            if yt != zt:
                self.report_error('type mismatch in conditional expression', pos)

            # TODO: this could be awkward if the types mismatch in size
            temp = self._temp(zt)
            x = ExprComma(self._combine_pos(x.pos, z.pos))\
                .add(ExprBinary(ExprBinary(x, '&&', ExprComma().add(ExprCopy(y, temp)).add(ExprNumber(1))), '||', ExprCopy(z, temp)))\
                .add(temp)

        return x

    def _parse_assignment(self):
        x = self._parse_conditional()

        if self.is_token('=') or self.is_token('+=') or self.is_token('-=') or self.is_token('*=') or \
                self.is_token('/=') or self.is_token('%=') or self.is_token('>>=') or self.is_token('<<=') or \
                self.is_token('&=') or self.is_token('^=') or self.is_token('|='):
            op = self.token.value
            pos = self.token.pos

            if not self._is_lvalue(x):
                self.report_error('lvalue required asm left operand of assignment', pos)

            self.next_token()
            y = self._parse_assignment()

            self._check_assignment(x, y, 'initialization')

            if op == '=':
                x = ExprCopy(y, x, self._combine_pos(x.pos, y.pos))
            else:
                op = op[:-1]
                if x.is_pure(self):
                    return ExprCopy(ExprBinary(x, op, y), x, self._combine_pos(x.pos, y.pos))
                else:
                    temp = self._temp(CPointer(x.resolve_type(self)))
                    return ExprComma(self._combine_pos(x.pos, y.pos)).add(ExprCopy(ExprAddrof(x), temp)).add(ExprCopy(ExprBinary(ExprDeref(temp), op, y), ExprDeref(temp)))

        return x

    def _parse_comma(self):
        e1 = self._parse_assignment()

        # Turn into a comma if has stuff
        if self.is_token(','):
            e1 = ExprComma().add(e1)

        while self.match_token(','):
            e1.add(self._parse_comma())

        return e1

    def _parse_expr(self):
        return self._parse_comma()

    ####################################################################################################################
    # Type parsing
    ####################################################################################################################

    def _parse_storage_decl(self, spec):
        while True:
            if self.match_keyword('register'):
                if spec != StorageClass.AUTO:
                    self.report_error('multiple storage classes in declaration specifiers')
                else:
                    spec = StorageClass.REGISTER
            elif self.match_keyword('static'):
                if spec != StorageClass.AUTO:
                    self.report_error('multiple storage classes in declaration specifiers')
                else:
                    spec = StorageClass.STATIC
            elif self.match_keyword('extern'):
                if spec != StorageClass.AUTO:
                    self.report_error('multiple storage classes in declaration specifiers')
                else:
                    spec = StorageClass.EXTERN
            else:
                break
        return spec

    def _parse_type(self, raise_error):
        typ = None
        pos = self.token.pos

        # See if any of these
        words = []
        while self.is_keyword('unsigned') or self.is_keyword('signed') or self.is_keyword('int') or self.is_keyword('short') or self.is_keyword('char') or self.is_keyword('long'):
            words.append(self.token.value)
            self.next_token()

        if len(words) != 0:
            # If has any of these then it is a number
            typ = self._resolve_type(words)

        elif self.is_keyword('struct') or self.is_keyword('union'):
            union = self.is_keyword('union')
            name_prefix = 'union' if union else 'struct'
            self.next_token()
            name, pos = self.expect_ident()

            # This will define the struct asm we go
            if self.match_token('{'):
                # Parse it
                typ = CStruct(name, pos)
                typ.union = union

                # While not in the struct definition end
                while not self.match_token('}'):
                    field_typ = self._parse_type(True)

                    # Parse the names
                    while True:
                        # Parse the name and specific type
                        cur_typ = self._parse_type_prefix(field_typ)
                        field_name, field_pos = self.expect_ident()
                        cur_typ = self._parse_type_postfix(cur_typ, field_pos)

                        # add it
                        typ.items.append((field_name, cur_typ))

                        # Check if has next
                        if self.match_token(';'):
                            break

                        # expect this
                        self.expect_token(',')

                if not self._type_in_scope([name_prefix, name]):
                    # If type is not defined in the current scope add it to the current scope
                    self._add_typedef([name_prefix, name], typ)
                else:
                    # Otherwise error, but keep the current type when doing type checking
                    self.report_error(f'redefinition of `{name_prefix} {name}`', pos)

            else:
                # Resolve it
                typ = self._resolve_type([name_prefix, name])
                if typ is None:
                    # Does not exists, create it
                    typ = CStruct(name, pos)
                    typ.union = union
                    self._add_typedef([name_prefix, name], typ)

        elif self.match_keyword('enum'):
            name, pos = self.expect_ident()
            assert False

        elif self.match_keyword('void'):
            typ = CVoid()

        elif self.is_token(IdentToken):
            name, pos = self.expect_ident()

            # Check if is a typedef
            if self._resolve_type(name) is not None:
                return self._resolve_type(name)

            if raise_error:
                self.token.pos = pos
                self.report_fatal_error(f'unknown type name `{name}`')
            else:
                return None
        else:
            if raise_error:
                self.expect_ident()
            else:
                return None

        return typ

    def _parse_type_prefix(self, typ):
        # Parse the prefixes
        while self.match_token('*'):
            typ = CPointer(typ)

        return typ

    def _parse_type_postfix(self, typ, name_pos):
        array_lens = []

        # Parse the postfixes
        while self.match_token('['):
            if self.is_token(IntToken):
                val = self.token.value
                self.next_token()
                array_lens.append(val)
            else:
                # incomplete array
                array_lens.append(None)
            self.expect_token(']')

        for i in reversed(array_lens):
            if not typ.is_complete():
                self.report_fatal_error(f'array type has incomplete element type `{typ}`', name_pos)
            typ = CArray(typ, i)

        return typ

    def _parse_type_name(self):
        typ = self._parse_type(False)
        if typ is None:
            return None, None, None

        typ = self._parse_type_prefix(typ)

        name = None
        name_pos = None
        if self.is_token(IdentToken):
            name, name_pos = self.expect_ident()
        return typ, name, name_pos

    ####################################################################################################################
    # Statement parsing
    ####################################################################################################################

    def _parse_stmt_block(self):
        block = ExprComma()
        while not self.match_token('}'):
            block.add(self._parse_stmt())
        return block

    def _parse_stmt(self):
        pos = self.token.pos

        if self.match_keyword('if'):
            self.expect_token('(')
            x = self._parse_expr()
            self.expect_token(')')
            y = self._parse_stmt()

            if self.match_keyword('else'):
                z = self._parse_stmt()
                return ExprComma(self._combine_pos(x.pos, z.pos))\
                    .add(ExprBinary(ExprBinary(x, '&&', ExprComma().add(y).add(ExprNumber(1))), '||', z))
            else:
                return ExprBinary(x, "&&", y)

        elif self.match_keyword('break'):
            if self._loop_nesting == 0:
                self.report_error('break statement not within loop or switch', pos)

            e = ExprBreak(pos)
            self.expect_token(';')
            return e

        elif self.match_keyword('continue'):
            if self._loop_nesting == 0:
                self.report_error('continue statement not within a loop', pos)

            e = ExprContinue(pos)
            self.expect_token(';')
            return e

        elif self.match_keyword('for'):
            assert False

        elif self.match_keyword('while'):
            self.expect_token('(')
            cond = self._parse_expr()
            self.expect_token(')')
            self._loop_nesting += 1
            body = self._parse_stmt()
            self._loop_nesting -= 1
            return ExprLoop(cond, body, self._combine_pos(pos, body.pos))

        elif self.match_keyword('do'):
            # body = self._parse_stmt()
            # self.expect_keyword('while')
            # self.expect_token('(')
            # cond = self._parse_expr()
            # temp_pos = self.token.pos
            # self.expect_token(')')
            # # TODO: This will not result in that efficient code gen tbh, we could probably do it better somehow
            # return ExprComma(self._combine_pos(pos, temp_pos)).add(body).add(ExprLoop(cond, body))
            pass

        elif self.match_keyword('switch'):
            assert False

        elif self.match_keyword('return'):
            stmt = ExprReturn(ExprNop())

            if not self.is_token(';'):
                x = self._parse_expr()
                if isinstance(self.func.type.ret_type, CVoid):
                    self.report_warn('`return` with a value, in function returning void', pos)
                    stmt.expr = ExprNop()
                else:
                    stmt.expr = x
            else:
                if not isinstance(self.func.type.ret_type, CVoid):
                    self.report_warn('`return` with no value, in function returning non-void', pos)
                    stmt.expr = ExprNumber(0)

            self._check_assignment(self.func.type.ret_type, stmt, 'return')

            temp_pos = self.token.pos
            self.expect_token(';')
            stmt.pos = self._combine_pos(pos, temp_pos)
            return stmt

        elif self.match_token('{'):
            return self._parse_stmt_block()

        elif self.match_token(';'):
            return ExprNop()

        else:
            stmt = self._parse_expr()
            temp_pos = self.token.pos
            self.expect_token(';')
            stmt.pos = self._combine_pos(stmt.pos, temp_pos)
            return stmt

    def _parse_func(self, func_name_pos: CodePosition, already_exists: bool):
        # Get the params
        self._push_scope()

        i = 0
        self.expect_token('(')
        if not self.match_token(')'):
            while True:

                # Parse it
                typ = self._parse_type(True)
                typ = self._parse_type_prefix(typ)
                pname, ppos = self.expect_ident()

                if already_exists:
                    if i > self.func.num_params:
                        self.report_fatal_error(f'number of arguments doesnt match prototype', func_name_pos, False)

                    # Just check arguments are the same
                    if typ != self.func.type.param_types[i]:
                        self.report_fatal_error(f'conflicting types for `{self.func.name}`', func_name_pos, False)

                    self._define(pname, ParameterIdentifier(pname, i))

                else:
                    # Check if the type is complete
                    if not typ.is_complete():
                        self.report_error(f'parameter {self.func.num_params + 1} (`{pname}`) has incomplete type', ppos, True)

                    # Define the parameter
                    if self._def_param(pname, typ) is None:
                        self.report_error(f'redefinition of `{pname}`', ppos, True)

                i += 1

                if self.match_token(')'):
                    break

                self.expect_token(',')

        if already_exists and i != len(self.func.type.param_types):
            self.report_fatal_error(f'number of arguments doesnt match prototype', func_name_pos, False)

        # Has a body
        if self.match_token('{'):

            # If the function is not a prototype complain on it already existing
            # also check the already_exists since the function is not a prototype by default
            if already_exists and not self.func.prototype:
                self.report_fatal_error(f'redefinition of `{self.func.name}`', func_name_pos, False)

            self.func.prototype = False

            # Parse all the variables
            # TODO: Support doing that not in the start of the function
            while True:
                # Save before we continue, so we can restore later
                self.save()

                # Parse the storage before
                spec = self._parse_storage_decl(StorageClass.AUTO)
                pos = self.token.pos

                # Parse the type, if failed we no longer have variables
                typ = self._parse_type(False)
                if typ is None:
                    self.restore()
                    break

                # Parse the after storage spec
                spec = self._parse_storage_decl(spec)

                # we can discard of the save because we def have a variable
                self.discard()

                # Get the name
                while True:

                    # parse the specific type of variable
                    cur_typ = self._parse_type_prefix(typ)
                    var_name, var_name_pos = self.expect_ident()
                    cur_typ = self._parse_type_postfix(cur_typ, var_name_pos)

                    # Make sure is a complete type
                    if not cur_typ.is_complete():
                        self.report_error(f'storage size of `{var_name}` isnt known', var_name_pos)

                    # Define the variable
                    new_var = self._def_var(var_name, cur_typ, spec)
                    if new_var is None:
                        self.report_error(f'redefinition of `{var_name}`', var_name_pos)

                    # Check for initialization
                    if self.match_token('='):
                        # if has initialization then parse the expression, check the assignment and add the
                        # copy expression to the start of the function
                        expr = self._parse_assignment()
                        self._check_assignment(cur_typ, expr, 'initialization')
                        self.func.code.add(ExprCopy(expr, new_var))

                    if self.match_token(';'):
                        # we are done with the specific variable list
                        break

                    # We expect this before the next one
                    self.expect_token(',')

            # Continue and parse the block
            self._push_scope()
            self.func.code.add(self._parse_stmt_block())
            self._pop_scope()

            # Add an implicit `return 0;`
            if isinstance(self.func.type.ret_type, CVoid):
                self.func.code.add(ExprReturn(ExprNop()))
            else:
                self.func.code.add(ExprReturn(ExprNumber(0)))
        else:
            # Just a prototype
            self.func.prototype = True

        self._pop_scope()

    def _parse_global_variable(self, typ: CType, storage: StorageClass):
        storage = self._parse_storage_decl(storage)

        def parse_one_variable(typ):
            typ = self._parse_type_prefix(typ)
            name, name_pos = self.expect_ident()
            typ = self._parse_type_postfix(typ, name_pos)

            if self.match_token('='):
                new_value = self._parse_conditional()
                if not new_value.is_constant(self):
                    self.report_error(f'initializer element is not constant')

                self._check_assignment(typ, new_value, 'initialization')
            else:
                new_value = None

            # TODO: better handling of redifition
            expr = self._def_var(name, typ, storage)
            if expr is None:
                self.report_error(f'redefinition of {name}', name_pos)
            self.global_vars[expr.ident.index].value = new_value

        parse_one_variable(typ)
        while self.match_token(','):
            parse_one_variable(typ)

        self.expect_token(';')

    def parse(self):
        while not self.is_token(EofToken):
            if self.match_token('#'):
                val, pos = self.expect_ident()
                if val == 'line':
                    self.line = self.token.value
                    self.expect_token(IntToken)
                    filename = self.filename
                    if self.is_token(StringToken):
                        self.filename = self.token.value
                        self.next_token()
                else:
                    self.report_warn(f'unknown directive `{val}` ignored', pos)
                    while not self.match_token('\n'):
                        self.next_token()

            elif self.match_keyword('typedef'):
                typ, name, pos = self._parse_type_name()

                if self._resolve_type(name) is not None:
                    if self._resolve_type(name) != typ:
                        self.report_error(f'conflicting types for `{name}`', pos, False)
                else:
                    self._add_typedef(name, typ)

                self.expect_token(';')

            # Ignore random ;
            elif self.match_token(';'):
                pass

            # Either a global or a function
            else:
                storage_class = self._parse_storage_decl(StorageClass.AUTO)

                # We are gonna check if this is a variable or function
                # if we get a `=` or `;` before a `(`, it is a variable
                func = False
                self.save()
                while not self.is_token('=') and not self.is_token(';'):
                    if self.is_token('('):
                        func = True
                        break
                    self.next_token()
                self.restore()

                # Now that we know what this is we can parse it normally
                if func:
                    ret_typ = self._parse_type(True)
                    ret_typ = self._parse_type_prefix(ret_typ)

                    # Parse the calling convention
                    callconv = CallConv.STACKCALL
                    if self.match_keyword('__stackcall'):
                        callconv = CallConv.STACKCALL
                    elif self.match_keyword('__regcall'):
                        callconv = CallConv.REGCALL
                    elif self.match_keyword('__interrupt'):
                        callconv = CallConv.INTERRUPT

                    name, name_pos = self.expect_ident()

                    if storage_class == StorageClass.REGISTER:
                        self.report_error(f'function definition declared `register`', name_pos)

                    if isinstance(ret_typ, CArray):
                        self.report_error(f'`{name}` declared asm function returning an array', name_pos)

                    e = self._def_fun(name)
                    if e is not None:
                        self._add_function(name, ret_typ)
                        self.func = self.func_list[e.ident.index]
                    else:
                        if self.func.type.ret_type != ret_typ:
                            self.report_fatal_error(f'conflicting types for `{self.func.name}`', name_pos, False)
                        self.func = self.func_list[self._use(name).ident.index]

                    # Handle setting the calling conv
                    if self.func.type.callconv is None:
                        self.func.type.callconv = callconv
                    elif callconv is not None:
                        assert callconv == self.func.type.callconv

                    self.func.storage_decl = storage_class

                    self._parse_func(name_pos, e is None)

                    self.func = None

                else:
                    typ = self._parse_type(True)

                    if not self.match_token(';'):
                        self._parse_global_variable(typ, storage_class)