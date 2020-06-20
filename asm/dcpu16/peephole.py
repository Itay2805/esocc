import re


# TODO: use custom rule syntax for easier time

SET_ADDSUB_DEREF_1 = re.compile(
    r"\tSET (?P<tmp_reg>A|B|C|X|Y|Z|I|J|SP), (?P<target_reg>A|B|C|X|Y|Z|I|J|SP|([_a-zA-Z0-9]+))\n"
    r"\t(?P<operation>ADD|SUB) (?P=tmp_reg), (?P<constant>\d+)\n"
    r"\tSET (?P<destination>.+), \[(?P=tmp_reg)( (?P<existing_operation>[-+]) (?P<existing_constant>\d+))?\]")

SET_ADDSUB_DEREF_2 = re.compile(
    r"\tSET (?P<tmp_reg>A|B|C|X|Y|Z|I|J|SP), (?P<target_reg>A|B|C|X|Y|Z|I|J|SP|([_a-zA-Z0-9]+))\n"
    r"\t(?P<operation>ADD|SUB) (?P=tmp_reg), (?P<constant>\d+)\n"
    r"\tSET \[(?P=tmp_reg)( (?P<existing_operation>[-+]) (?P<existing_constant>\d+))?\], (?P<source>.+)")

TWO_SAME_OPS = re.compile(
    r"\t(?P<operation>ADD|SUB|MUL) (?P<target>A|B|C|X|Y|Z|I|J|SP), (?P<constant_1>\d+)\n"
    r"\t(?P=operation) (?P=target), (?P<constant_2>\d+)")

class Dcpu16PeepholeOptimizer:

    def __init__(self):
        pass

    def optimize(self, asm: str):
        new_asm = self._apply(asm)
        while asm != new_asm:
            asm = new_asm
            new_asm = self._apply(asm)
        return new_asm

    def _set_addsub_deref(self, match: re.Match):
        """
        matches:
            SET <tmp_reg:REG>, <target:REG>
            {ADD,SUB} <tmp_reg>, <constant:CONSTANT>
            SET <destination:OPERAND>, [<tmp_reg> ( {-,+} <value:CONSTANT>)?]

        and turns into
            SET <destination>, [<target> <operation> <value>]

        so for example the following code:
            SET B, SP
            ADD B, 2
            SET A, B
            ADD A, 1
            SET A, [A]
            ADD A, [SP + 2]
            SET PC, POP

        will first turn into
            SET B, SP
            ADD B, 2
            SET A, [B + 1]
            ADD A, [SP + 2]
            SET PC, POP

        and then into
            SET A, [SP + 3]
            ADD A, [SP + 2]
            SET PC, POP
        """

        groups = match.groupdict()
        tmp_reg = groups['tmp_reg']
        target_reg = groups['target_reg']
        operation = '+' if groups['operation'] == 'ADD' else '-'
        constant = int(groups['constant'])

        if groups['existing_operation'] is not None:
            existing_operation = groups['existing_operation']
            existing_constant = int(groups['existing_constant'])
            constant = eval(f'{operation} {constant} {existing_operation} {existing_constant}')

        if 'destination' in groups:
            return f'\tSET {groups["destination"]}, [{target_reg} {operation} {constant}]'
        else:
            return f'\tSET [{target_reg} {operation} {constant}], {groups["source"]}'

    def _two_same_ops(self, match: re.Match):
        groups = match.groupdict()
        target = groups['target']
        operation = groups['operation']
        const1 = int(groups['constant_1'])
        const2 = int(groups['constant_1'])
        if operation == 'ADD':
            val = const1 + const2
        elif operation == 'SUB':
            val = const1 - const2
        elif operation == 'MUL':
            val = const1 * const2
        else:
            assert False
        return f'\t{operation} {target}, {val}'

    def _dead_set(self, match: re.Match):
        return '\t' + match.group('expression')

    def _apply(self, asm: str):
        asm = SET_ADDSUB_DEREF_1.sub(self._set_addsub_deref, asm)
        asm = SET_ADDSUB_DEREF_2.sub(self._set_addsub_deref, asm)
        asm = TWO_SAME_OPS.sub(self._two_same_ops, asm)
        return asm
