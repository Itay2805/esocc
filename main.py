from parsing.parser import Parser
from parsing.optimizer import Optimizer
from parsing.ir_translator import IrTranslator
from ir.printer import Printer
from ir.translate.dcpu16_translator import Dcpu16Translator

code = """
short buffer[0x1000];

int get_from_buffer(int index) {
    return buffer[index];
}
"""

# Parse the code into an ast
parser = Parser(code)
parser.parse()
assert not parser.got_errors

print('\n'.join(map(str, parser.func_list)))

# Optimize the AST
opt = Optimizer(parser)
opt.optimize()

print('\n'.join(map(str, opt.parser.func_list)))

# Now we need to translate it
trans = IrTranslator(parser)
trans.translate()

code_trans = Dcpu16Translator()
for proc in trans.proc_list:
    code_trans.translate_procedure(proc)
