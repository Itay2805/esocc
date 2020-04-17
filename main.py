from parser.parser import Parser
from parser.optimizer import Optimizer
from parser.translator import Translator
from ir.printer import Printer
from ir.translate.dcpu16_translator import Dcpu16Translator

code = """
int add(int a, int b); 

int main() {
    return add(add(1, 2), add(3, 4));
}
"""

# Parse the code into an ast
parser = Parser(code)
parser.parse()
assert not parser.got_errors

# Optimize the AST
opt = Optimizer(parser)
opt.optimize()

# Now we need to translate it
trans = Translator(parser)
trans.translate()

code_trans = Dcpu16Translator()
for proc in trans.proc_list:
    code_trans.translate_procedure(proc)
