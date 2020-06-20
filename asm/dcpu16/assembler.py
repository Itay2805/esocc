from .tokenizer import *
from typing import *
import struct


class Dcpu16Assembler(Tokenizer):

    class LabelUse:

        def __init__(self, name: str, pos: int):
            self.pos = pos
            self.name = name

    def __init__(self, code, filename='<unknown>'):
        super(Dcpu16Assembler, self).__init__(code, filename)

        self._lbl_uses = []  # type: List[Dcpu16Assembler.LabelUse]
        self._lbls = {}  # type: Dict[str, int]
        self._words = []
        self._pos = 0
        self._current_lbl = None

        self._externs = []
        self._globals = {}

        self._global_relocations = []
        self._local_relocations = []

        self.next_token()
        self.got_errors = False

    ####################################################################################################################
    # Labels
    ####################################################################################################################

    def _mark_label(self, name: str, pos: CodePosition):
        if name[0] == '_':
            if self._current_lbl is None:
                self.report_error(f'defined local label `{name}` before a label', pos)
            else:
                name = self._current_lbl + name
        else:
            self._current_lbl = name
        self._lbls[name] = self._pos

    def _use_label(self, name: str):
        self._lbl_uses.append(Dcpu16Assembler.LabelUse(name, self._pos))

    def fix_labels(self):
        orig = self._pos
        unknown = []
        for lbl in self._lbl_uses:
            if lbl.name in self._lbls:
                self._pos = lbl.pos
                self._words[self._pos] += self._lbls[lbl.name]
                self._local_relocations.append(lbl.pos)
            else:
                unknown.append(lbl)
        self._pos = orig

        for lbl in unknown:
            if lbl.name not in self._externs:
                self.report_error(f'undefined symbol `{lbl.name}` referenced')
            else:
                self._global_relocations.append((lbl.name, lbl.pos))

        for glob in self._globals:
            if glob not in self._lbls:
                self.report_error(f'global defined for undefined symbol `{glob}`')
            else:
                self._globals[glob] = self._lbls[glob]

    def get_object(self):
        return self.get_words(), self._global_relocations, self._local_relocations, self._globals

    ####################################################################################################################
    # Assembling
    ####################################################################################################################

    def _emit_word(self, word):
        self._words.append(word & 0xFFFF)
        self._pos += 1

    def get_words(self):
        return self._words

    ####################################################################################################################
    # Error reporting
    ####################################################################################################################

    BOLD = '\033[01m'
    RESET = '\033[0m'
    GREEN = '\033[32m'
    RED = '\033[31m'
    YELLOW = '\033[33m'

    def report(self, typ: str, col: str, msg: str, pos=None):
        if pos is None:
            if not isinstance(self.token, EofToken):
                pos = self.token.pos

        if pos is not None:
            print(f'{Dcpu16Assembler.BOLD}{self.filename}:{pos.start_line + 1}:{pos.start_column + 1}:{Dcpu16Assembler.RESET} {col}{Dcpu16Assembler.BOLD}{typ}:{Dcpu16Assembler.RESET} {msg}')

            line = self.lines[pos.start_line]
            line = line[:pos.start_column] + Dcpu16Assembler.BOLD + line[pos.start_column:pos.end_column] + Dcpu16Assembler.RESET + line[pos.end_column:]
            print(line)

            c = ''
            for i in range(pos.start_column):
                if self.lines[pos.start_line][i] == '\t':
                    c += '\t'
                else:
                    c += ' '

            print(c + Dcpu16Assembler.BOLD + col + '^' + '~' * (pos.end_column - pos.start_column - 1) + Dcpu16Assembler.RESET)
            print()
        else:
            print(f'{Dcpu16Assembler.BOLD}{self.filename}:{Dcpu16Assembler.RESET} {col}{Dcpu16Assembler.BOLD}{typ}:{Dcpu16Assembler.RESET} {msg}')

    def report_error(self, msg: str, pos=None):
        self.report('error', Dcpu16Assembler.RED, msg, pos)
        self.got_errors = True

    def report_warn(self, msg: str, pos=None):
        self.report('warning', Dcpu16Assembler.YELLOW, msg, pos)

    def report_fatal_error(self, msg: str, pos=None):
        self.report('error', Dcpu16Assembler.RED, msg, pos)
        exit(-1)

    ####################################################################################################################
    # Constant expression parsing (for number constants)
    ####################################################################################################################

    def _parse_addition(self):
        if self.match_token('+'):
            pos = self.token.pos
            if self.is_token(IntToken):
                val = self.token.value
                self.next_token()
                return val
            else:
                assert False
        elif self.match_token('-'):
            pos = self.token.pos
            if self.is_token(IntToken):
                val = -self.token.value
                self.next_token()
                return val
            else:
                assert False
        else:
            return 0

    def _parse_operand(self, a: bool):
        if not a and self.match_keyword('PUSH'):
            return 0x18, None
        elif a and self.match_keyword('POP'):
            return 0x18, None
        elif self.match_keyword('PEEK'):
            return 0x19, None
        elif self.match_keyword('PICK'):
            if self.is_token(IntToken):
                val = self.token.value
                self.next_token()
                return 0x1A, val
            else:
                return 0x1A, 0
        elif self.match_keyword('A'):
            return 0, None
        elif self.match_keyword('B'):
            return 1, None
        elif self.match_keyword('C'):
            return 2, None
        elif self.match_keyword('X'):
            return 3, None
        elif self.match_keyword('Y'):
            return 4, None
        elif self.match_keyword('Z'):
            return 5, None
        elif self.match_keyword('I'):
            return 6, None
        elif self.match_keyword('J'):
            return 7, None
        elif self.match_keyword('SP'):
            return 0x1B, None
        elif self.match_keyword('PC'):
            return 0x1C, None
        elif self.match_keyword('EX'):
            return 0x1D, None
        elif self.match_token('['):
            # UGLY CODE AHEAD
            # Parse the first part
            if self.match_keyword('A'):
                off = self._parse_addition()
                self.expect_token(']')
                if off == 0:
                    return 0x08, None
                else:
                    return 0x10, off
            elif self.match_keyword('B'):
                off = self._parse_addition()
                self.expect_token(']')
                if off == 0:
                    return 0x09, None
                else:
                    return 0x11, off
            elif self.match_keyword('C'):
                off = self._parse_addition()
                self.expect_token(']')
                if off == 0:
                    return 0x0A, None
                else:
                    return 0x12, off
            elif self.match_keyword('X'):
                off = self._parse_addition()
                self.expect_token(']')
                if off == 0:
                    return 0x0B, None
                else:
                    return 0x13, off
            elif self.match_keyword('Y'):
                off = self._parse_addition()
                self.expect_token(']')
                if off == 0:
                    return 0x0C, None
                else:
                    return 0x14, off
            elif self.match_keyword('Z'):
                off = self._parse_addition()
                self.expect_token(']')
                if off == 0:
                    return 0x0D, None
                else:
                    return 0x15, off
            elif self.match_keyword('I'):
                off = self._parse_addition()
                self.expect_token(']')
                if off == 0:
                    return 0x0E, None
                else:
                    return 0x16, off
            elif self.match_keyword('J'):
                off = self._parse_addition()
                self.expect_token(']')
                if off == 0:
                    return 0x0F, None
                else:
                    return 0x17, off
            elif self.match_keyword('SP'):
                off = self._parse_addition()
                self.expect_token(']')
                if off == 0:
                    return 0x19, None
                else:
                    return 0x1A, off
            elif self.is_token(IntToken):
                val = self.token.value
                self.next_token()
                off = self._parse_addition()
                self.expect_token(']')
                return 0x1E, (val, off)
            elif self.is_token(IdentToken):
                val = self.token.value
                self.next_token()
                self.expect_token(']')
                return 0x1E, val
            else:
                assert False, self.token
        elif self.is_token(IntToken):
            val = self.token.value
            self.next_token()
            # TODO this
            if a and -1 <= val <= 30:
                return 0x20 + (val + 1), None
            else:
                return 0x1F, val
        elif self.is_token(IdentToken):
            val = self.token.value
            off = self._parse_addition()
            self.next_token()
            return 0x1F, (val, off)
        else:
            self.report_fatal_error('jwjwdwaduuihwadiuawd')

    INST_TABLE = {
        'SET': 0x01,
        'ADD': 0x02,
        'SUB': 0x03,
        'MUL': 0x04,
        'MLI': 0x05,
        'DIV': 0x06,
        'DVI': 0x07,
        'MOD': 0x08,
        'MDI': 0x09,
        'AND': 0x0A,
        'BOR': 0x0B,
        'XOR': 0x0C,
        'SHR': 0x0D,
        'ASR': 0x0E,
        'SHL': 0x0F,
        'IFB': 0x10,
        'IFC': 0x11,
        'IFE': 0x12,
        'IFN': 0x13,
        'IFG': 0x14,
        'IFA': 0x15,
        'IFL': 0x16,
        'IFU': 0x17,

        'ADX': 0x1A,
        'SBX': 0x1B,

        'STI': 0x1E,
        'STD': 0x1F
    }

    SPECIAL_INST_TABLE = {
        'JSR': 0x01,

        'INT': 0x08,
        'IAG': 0x09,
        'IAS': 0x0A,
        'RFI': 0x0B,
        'IAQ': 0x0C,

        'HWN': 0x10,
        'HWQ': 0x11,
        'HWI': 0x12,
    }

    def _parse_instruction(self):
        tok = self.token
        self.expect_token(KeywordToken)
        keyword = tok.value
        pos = tok.value
        if keyword in Dcpu16Assembler.INST_TABLE:
            opcode = Dcpu16Assembler.INST_TABLE[keyword]
            b, extra1 = self._parse_operand(False)
            self.expect_token(',')
            a, extra2 = self._parse_operand(True)

            value = opcode | b << 5 | a << 10
            self._emit_word(value)

            if extra1 is not None:
                if isinstance(extra1, tuple):
                    self._use_label(extra1[0])
                    self._emit_word(extra1[1])
                else:
                    self._emit_word(extra1)

            if extra2 is not None:
                if isinstance(extra2, str):
                    self._use_label(extra2)
                    self._emit_word(0)
                else:
                    self._emit_word(extra2)

        elif keyword in Dcpu16Assembler.SPECIAL_INST_TABLE:
            opcode = Dcpu16Assembler.SPECIAL_INST_TABLE[keyword]
            a, extra = self._parse_operand(True)

            value = 0 | opcode << 5 | a << 10
            self._emit_word(value)
            if extra is not None:
                if isinstance(extra, str):
                    self._use_label(extra)
                    self._emit_word(0)
                else:
                    self._emit_word(extra)

        else:
            self.report_fatal_error(f'expected an instruction', pos)

    def parse(self):
        while not self.is_token(EofToken):
            if self.match_token('.'):
                if self.match_keyword('global'):
                    name, pos = self.expect_ident()
                    self._globals[name] = 0
                elif self.match_keyword('extern'):
                    name, pos = self.expect_ident()
                    self._externs.append(name)
                elif self.match_keyword('dw'):
                    if self.is_token(IntToken):
                        val = self.token.value
                        self.next_token()
                        self._emit_word(val)
                    elif self.is_token(IdentToken):
                        assert False
                    else:
                        self.report_error('invalid value for .dw')
                elif self.match_keyword('fill'):
                    if self.is_token(IntToken):
                        count = self.token.value
                        val = 0
                        if self.is_token(IntToken):
                            val = self.token.value
                            self.next_token()
                        self.next_token()
                        for i in range(count):
                            self._emit_word(val)
                    else:
                        self.report_error('invalid value for .fill')
                else:
                    self.report_warn(f'unknown directive {self.token} ignored')
                    while not self.match_token('\n'):
                        self.next_token()
            elif self.is_token(IdentToken):
                val = self.token.value
                self._mark_label(val, self.token.pos)
                self.next_token()
                self.expect_token(':')
            elif self.match_token('\n'):
                continue
            else:
                self._parse_instruction()
            self.expect_token('\n')
