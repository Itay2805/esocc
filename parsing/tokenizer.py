from enum import Enum
from typing import Tuple
import traceback
import sys


class UnknownCharacter(Exception):
    pass


class CodePosition:

    def __init__(self, start_line, end_line, start_column, end_column):
        self.start_line = start_line
        self.end_line = end_line
        self.start_column = start_column
        self.end_column = end_column


class Token:

    def __init__(self, pos: CodePosition):
        self.pos = pos

    def __repr__(self):
        raise NotImplementedError()


class EofToken(Token):

    def __init__(self):
        super(EofToken, self).__init__(None)

    def __str__(self):
        return 'End of file'

    def __repr__(self):
        return f'<EofToken>'


class IntToken(Token):

    def __init__(self, pos: CodePosition, value: int):
        super(IntToken, self).__init__(pos)
        self.value = value

    def __str__(self):
        return 'Integer constant'

    def __repr__(self):
        return f'<IntToken: value={repr(self.value)}>'


class FloatToken(Token):

    def __init__(self, pos: CodePosition, value: float):
        super(FloatToken, self).__init__(pos)
        self.value = value

    def __str__(self):
        return 'Float constant'

    def __repr__(self):
        return f'<FloatToken: value={repr(self.value)}>'


class IdentToken(Token):

    def __init__(self, pos: CodePosition, value: str):
        super(IdentToken, self).__init__(pos)
        self.value = value

    def __str__(self):
        return f'Identifier (`{self.value}`)'

    def __repr__(self):
        return f'<IdentToken: value={repr(self.value)}>'


class KeywordToken(Token):

    def __init__(self, pos: CodePosition, value: str):
        super(KeywordToken, self).__init__(pos)
        self.value = value

    def __str__(self):
        return f'`{self.value}`'

    def __repr__(self):
        return f'<KeywordToken: value={repr(self.value)}>'


class SymbolToken(Token):

    def __init__(self, pos: CodePosition, value: str):
        super(SymbolToken, self).__init__(pos)
        self.value = value

    def __str__(self):
        return f'`{self.value}` token'

    def __repr__(self):
        return f'<SymbolToken: value={repr(self.value)}>'


class Tokenizer:

    def __init__(self, stream: str, filename: str = "<unknown>"):
        self.stream = stream
        self.filename = filename
        self.lines = stream.splitlines()
        self.line = 0
        self.column = 0
        self.token = Token(None)

        self.pushes = []

    def _syntax_error(self, msg):
        pos = self.token.pos

        BOLD = '\033[01m'
        RESET = '\033[0m'
        GREEN = '\033[32m'
        RED = '\033[31m'

        print(
            f'{BOLD}{self.filename}:{pos.start_line + 1}:{pos.start_column + 1}:{RESET} {RED}{BOLD}syntax error:{RESET} {msg}')
        line = self.lines[pos.start_line]
        line = line[:pos.start_column] + BOLD + line[pos.start_column:pos.end_column] + RESET + line[pos.end_column:]
        print(line)
        c = ''
        for i in range(pos.start_column):
            if self.lines[pos.start_line][i] == '\t':
                c += '\t'
            else:
                c += ' '

        print(c + BOLD + RED + '^' + '~' * (pos.end_column - pos.start_column - 1) + RESET)
        print()

        traceback.print_stack(file=sys.stdout)
        exit(-1)

    def _inc_stream(self, times=1):
        # Increment the first thing
        while times > 0:
            was = self.stream[0]
            self.stream = self.stream[1:]
            if was == '\n':
                self.line += 1
                self.column = 0
            else:
                self.column += 1
            times -= 1

    def save(self):
        """
        Will save the state so it can be restored later
        """
        self.pushes.append((self.token, self.stream, self.line, self.column))

    def restore(self):
        """
        Will restore the state to the saved state
        """
        token, stream, line, col = self.pushes.pop()
        self.token = token
        self.stream = stream
        self.line = line
        self.column = col

    def discard(self):
        """
        Discard the last saved state
        """
        self.pushes.pop()

    def is_token(self, kind) -> bool:
        if isinstance(kind, str):
            return isinstance(self.token, SymbolToken) and self.token.value == kind
        elif isinstance(self.token, kind):
            return True

    def is_keyword(self, ident) -> bool:
        if self.is_token(KeywordToken) and self.token.value == ident:
            return True
        else:
            return False

    def match_keyword(self, ident) -> bool:
        if self.is_keyword(ident):
            self.next_token()
            return True
        else:
            return False

    def match_token(self, kind) -> bool:
        if self.is_token(kind):
            self.next_token()
            return True
        else:
            return False

    def expect_token(self, kind):
        if self.is_token(kind):
            self.next_token()
        else:
            if isinstance(kind, str):
                self._syntax_error(f'expected `{kind}`, got {str(self.token)} instead')
            else:
                self._syntax_error(f'expected {str(kind)}, got {str(self.token)} instead')

    def expect_keyword(self, kind):
        if self.is_keyword(kind):
            self.next_token()
        else:
            self._syntax_error(f'expected {str(kind)}, got {str(self.token)} instead')

    def expect_ident(self) -> Tuple[str, CodePosition]:
        if not self.is_token(IdentToken):
            self._syntax_error(f'expected Identifier, got {str(self.token)} instead')
        val = self.token.value
        pos = self.token.pos
        self.next_token()
        return val, pos

    def next_token(self):
        # Clear unneeded stuff
        while True:
            # Consume spaces
            if len(self.stream) > 0 and self.stream[0].isspace():
                self._inc_stream()

            # Consume multiline comment
            elif len(self.stream) > 2 and self.stream[:2] == '/*':
                self._inc_stream(2)
                while len(self.stream) > 0:
                    if len(self.stream) > 1 and self.stream[:2] == '*/':
                        self._inc_stream(2)
                        break
                    self._inc_stream()

            # Consume one line comments
            elif len(self.stream) > 2 and self.stream[:2] == '//':
                self._inc_stream(2)
                while len(self.stream) > 0:
                    if self.stream[0] == '\n':
                        self._inc_stream()
                        break
                    self._inc_stream()

            # Nothing left to clear
            else:
                break

        pos = CodePosition(self.line, self.line, self.column, self.column)

        # End of file
        if len(self.stream) == 0:
            self.token = EofToken()

        elif self.stream[0] == '\'':
            self._inc_stream()
            ch = self.stream[0]
            self._inc_stream()
            if ch == '\\':
                ch = self.stream[0]
                if ch == 'n':
                    ch = '\n'
                elif ch == 't':
                    ch = '\t'
                elif ch == '\0':
                    ch = '\0'
                else:
                    self._syntax_error(f'invalid escape sequence `\\{ch}`')
                self._inc_stream()
            if self.stream[0] != '\'':
                self._syntax_error(f'expected `\'`, got `{self.stream[0]}`')
            self._inc_stream()
            self.token = IntToken(pos, ord(ch))

        # Integers
        elif self.stream[0].isdigit():
            # Figure the base
            base = 10
            chars = '0123456789'
            if self.stream[0] == '0' and len(self.stream) > 3:
                if self.stream[1].lower() == 'x':
                    base = 16
                    chars = '0123456789abcdefABCDEF'
                    self._inc_stream(2)
                elif self.stream[1].lower() == 'b':
                    base = 2
                    chars = '01'
                    self._inc_stream(2)
                else:
                    base = 8
                    chars = '01234567'

            # Get the value and parse it
            value = ''
            while len(self.stream) > 0 and self.stream[0] in chars:
                value += self.stream[0]
                self._inc_stream()

            self.token = IntToken(pos, int(value, base))

        # Identifier token or keywords
        elif self.stream[0].isalpha() or self.stream[0] == '_':
            value = ''
            while len(self.stream) > 0 and (self.stream[0].isalnum() or self.stream[0] == '_'):
                value += self.stream[0]
                self._inc_stream()

            # Check if a keyword
            if value in [
                'if',
                'else',
                'do',
                'while',
                'for',
                'return',
                'goto',
                'break',
                'continue',
                'switch',
                'case',
                'default',

                'void',
                'char',
                'signed',
                'unsigned',
                'short',
                'int',
                'long',
                'float',
                'double',

                'struct',
                'enum',
                'union',
                'typedef',

                'volatile',
                'register',
                'static',
                'const',
                'inline',
                'extern',

                'sizeof',
                'asm',

                '__regcall',
                '__stackcall',
                '__interrupt'
            ]:
                self.token = KeywordToken(pos, value)
            else:
                self.token = IdentToken(pos, value)

        # Special characters
        elif self.stream[0] in '()[]{};\'",.:/*-+!%&<>=~^|?;':

            # Three character symbols
            if len(self.stream) > 2 and self.stream[:3] in [
                '>>=',
                '<<='
            ]:
                self.token = SymbolToken(pos, self.stream[:3])
                self._inc_stream(3)

            # Two character symbols
            elif len(self.stream) > 1 and self.stream[:2] in [
                '<<',
                '>>',
                '&&',
                '||',
                '!=',
                '==',
                '<=',
                '>=',
                '+=',
                '-=',
                '*=',
                '/=',
                '%=',
                '&=',
                '|=',
                '^=',
                '++',
                '--',
                '->',
            ]:
                self.token = SymbolToken(pos, self.stream[:2])
                self._inc_stream(2)

            # Simple symbols
            else:
                self.token = SymbolToken(pos, self.stream[0])
                self._inc_stream()

        # Unknown
        else:
            assert False, f'Unknown character {self.stream[0]}'

        pos.end_column = self.column
        pos.end_line = self.line

        return self.token
