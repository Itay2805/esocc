import os
import sys
import pcpp
import argparse
import pickle
from io import StringIO

from parsing.parser import Parser
from parsing.types import StorageClass
from parsing.optimizer import Optimizer
from parsing.ir_translator import IrTranslator

from ir.printer import Printer
from ir.translate.dcpu16_translator import Dcpu16Translator

from asm.dcpu16.peephole import PeepholeOptimizer
from asm.dcpu16.assembler import Assembler

def main():
    parser = argparse.ArgumentParser(description="Esoteric C compiler")
    parser.add_argument('infiles', metavar='infile', type=str, nargs='+', help="Input files, can be either C or ASM")
    parser.add_argument('-o', dest='outfile', metavar='outfile', type=str, default='a.out', required=False, help="Place the output into <outfile>")
    parser.add_argument('-E', dest='preprocess_only', action='store_const', const=True, default=False, help="Preprocess only; do not compile, assemble or link.")
    parser.add_argument('-S', dest='compile_only', action='store_const', const=True, default=False, help="Compile only; do not assemble or link.")
    parser.add_argument('-c', dest='assembly_only', action='store_const', const=True, default=False, help="Compile and assemble, but do not link.")
    parser.add_argument('-D', dest='defines', metavar='macro[=val]', nargs=1, action='append', help='Predefine name as a macro [with value]')
    parser.add_argument('-I', dest='includes', metavar='path', nargs=1, action='append', help="Path to search for unfound #include's")
    args = parser.parse_args()

    ################################################
    # preprocess all files
    ################################################

    preprocessor = pcpp.Preprocessor()
    preprocessor.add_path('.')
    if args.includes is not None:
        for path in args.includes:
            preprocessor.add_path(path)

    # TODO: pass defines

    files = []
    asms = []
    objects = []
    for file in args.infiles:
        if file.endswith('.c'):
            preprocessor.parse(open(file), file)
            s = StringIO()
            preprocessor.write(s)
            code = s.getvalue()
            files.append((code, file))

        elif file.endswith('.s'):
            asms.append((file, open(file).read()))

        elif file.endswith('.o'):
            object = pickle.Unpickler(open(file)).load()
            objects.append((object, file))

        else:
            assert False, f"Unknown file extension {file}"

    if args.preprocess_only:
        for code, file in files:
            print(code)
        return

    for code, file in files:
        # Parse the code into an ast
        parser = Parser(code, filename=file)
        parser.parse()
        if parser.got_errors:
            exit(1)
        assert not parser.got_errors

        # Optimize the AST
        opt = Optimizer(parser)
        opt.optimize()

        # Now we need to translate it into
        # the ir code
        trans = IrTranslator(parser)
        trans.translate()

        # Now run it through the ir translator for
        # the dcpu16
        code_trans = Dcpu16Translator()
        for proc in trans.proc_list:
            code_trans.translate_procedure(proc)
        asm = code_trans.get_asm()

        # Run the code through the peephole optimizer
        optimizer = PeepholeOptimizer()
        asm = optimizer.optimize(asm)

        # Add externs for any unknown label
        for func in parser.func_list:
            if func.prototype:
                asm += f'\n.extern {func.name}\n'

        # Add global vars definitions
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

        asms.append((asm, file))

    if args.assembly_only:
        for asm, file in asms:
            if file.endswith('.c'):
                with open(file[:-2] + '.s', 'w') as f:
                    f.write(asm)
        return

    for asm, file in asms:
        asm = Assembler(asm, file)
        asm.parse()
        if not asm.got_errors:
            for word in asm.get_words():
                print(hex(word)[2:].zfill(4))


if __name__ == '__main__':
    main()
