from parsing.parser import Parser
from parsing.optimizer import Optimizer
from parsing.ir_translator import IrTranslator
from ir.printer import Printer
from ir.translate.dcpu16_translator import Dcpu16Translator

code = """
void add(int* a); 

int main() {
    int a = 123;
    add(&a);
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
trans = IrTranslator(parser)
trans.translate()

code_trans = Dcpu16Translator()
for proc in trans.proc_list:
    code_trans.translate_procedure(proc)
