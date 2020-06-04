from parsing.parser import Parser
from parsing.optimizer import Optimizer
from parsing.ir_translator import IrTranslator
from parsing.types import StorageClass
from ir.printer import Printer
from ir.translate.dcpu16_translator import Dcpu16Translator
from asm.dcpu16.peephole import PeepholeOptimizer

code = """
typedef struct device {
    int id;
    int vendor;
} device_t;

void search_for_devices(device_t* device) {
    int c = 54, d = 123;
    device->id = device->vendor + 5 + c + d;
}
"""

# Parse the code into an ast
parser = Parser(code)
parser.parse()
assert not parser.got_errors

# print('\n'.join(map(str, parser.func_list)))

# Optimize the AST
opt = Optimizer(parser)
opt.optimize()

print('\n'.join(map(str, opt.parser.func_list)))

# Now we need to translate it
trans = IrTranslator(parser)
trans.translate()

printer = Printer()
for func in trans.proc_list:
    for inst in func.get_body():
        print(printer.print_instruction(inst))

code_trans = Dcpu16Translator()
for proc in trans.proc_list:
    code_trans.translate_procedure(proc)
asm = code_trans.get_asm()

optimizer = PeepholeOptimizer()
asm = optimizer.optimize(asm)

for func in parser.func_list:
    if func.prototype:
        asm += f'\n.extern {func.name}\n'

for var in parser.global_vars:
    if var.storage == StorageClass.EXTERN:
        asm += f'\n.extern {var.ident.name}\n'
    else:
        if var.storage != StorageClass.STATIC:
            asm += f'\n.global {var.ident.name}\n'
        asm += f'{var.ident.name}:\n'
        if var.value is None:
            asm += f'\t.fill {var.typ.sizeof()}, 0\n'
        else:
            asm += f'\t.dw {var.value}\n'

print(asm)
