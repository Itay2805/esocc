import os
import sys
import pcpp
import pickle
import struct
import argparse
from io import StringIO

# C parsing related
from parsing.parser import Parser
from parsing.types import StorageClass
from parsing.optimizer import Optimizer
from parsing.ir_translator import IrTranslator

from ir.printer import Printer

# Dcpu16 related
from ir.translate.dcpu16_translator import Dcpu16Translator
from asm.dcpu16.peephole import Dcpu16PeepholeOptimizer
from asm.dcpu16.assembler import Dcpu16Assembler
from asm.dcpu16.linker import Dcpu16Linker, BinaryType


def main():
    parser = argparse.ArgumentParser(description="Esoteric C compiler")
    parser.add_argument('infiles', metavar='infile', type=str, nargs='+', help="Input files, can be either C or ASM")
    parser.add_argument('-o', dest='outfile', metavar='outfile', type=str, default='a.out', required=False, help="Place the output into <outfile>")
    parser.add_argument('-E', dest='preprocess_only', action='store_const', const=True, default=False, help="Preprocess only; do not compile, assemble or link.")
    parser.add_argument('-S', dest='compile_only', action='store_const', const=True, default=False, help="Compile only; do not assemble or link.")
    parser.add_argument('-c', dest='assemble_only', action='store_const', const=True, default=False, help="Compile and assemble, but do not link.")
    parser.add_argument('-D', dest='defines', metavar='macro[=val]', nargs=1, action='append', help='Predefine name as a macro [with value]')
    parser.add_argument('-I', dest='includes', metavar='path', nargs=1, action='append', help="Path to search for unfound #include's")

    parser.add_argument('--dump-ir', dest='dump_ir', action='store_const', const=True, default=False, help="Dump the IR into a file")
    parser.add_argument('--dump-ast', dest='dump_ast', action='store_const', const=True, default=False, help="Dump the AST into a file")

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

    #
    # Figure all the files
    #
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

        elif file.endswith('.S'):
            asms.append((file, open(file).read()))

        elif file.endswith('.o'):
            obj = pickle.Unpickler(open(file, 'rb')).load()
            objects.append((obj, file))

        else:
            assert False, f"Unknown file extension {file}"

    #
    # If preprocess just print the preprocessed files
    #
    if args.preprocess_only:
        for code, file in files:
            print(code)
        return

    #
    # Compile all c files
    #
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

        if args.dump_ast:
            with open(file[:-2] + '.ast', 'w') as f:
                for func in opt.parser.func_list:
                    f.write(str(func) + '\n')

        # Now we need to translate it into
        # the ir code
        trans = IrTranslator(parser)
        trans.translate()

        if args.dump_ir:
            with open(file[:-2] + '.ir', 'w') as f:
                p = Printer()
                for proc in trans.proc_list:
                    f.write(proc.get_name() + ":\n")
                    for inst in proc.get_body():
                        f.write('\t' + p.print_instruction(inst) + '\n')

        # Now run it through the ir translator for
        # the dcpu16
        code_trans = Dcpu16Translator()
        for proc in trans.proc_list:
            code_trans.translate_procedure(proc)
        asm = code_trans.get_asm()

        # Run the code through the peephole optimizer
        optimizer = Dcpu16PeepholeOptimizer()
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

    #
    # If we only do compilation then save the assembly files
    #
    if args.compile_only:
        for asm, file in asms:
            with open(file[:-2] + '.S', 'w') as f:
                f.write(asm)
        return

    #
    # Assemble all assembly files
    #
    for asm, file in asms:
        asm = Dcpu16Assembler(asm, file)
        asm.parse()
        asm.fix_labels()
        if asm.got_errors:
            exit(1)
        assert not asm.got_errors
        objects.append((asm.get_object(), file))

    #
    # If only assemble save the object files
    #
    if args.assemble_only:
        for obj, file in objects:
            pickle.Pickler(open(file[:-2] + '.o', 'wb')).dump(obj)
        return

    #
    # Link everything
    #
    linker = Dcpu16Linker()
    for obj, file in objects:
        linker.append_object(obj)
    linker.link(BinaryType.RAW)

    #
    # Output the final binary
    #
    with open(args.outfile, 'wb') as f:
        for word in linker.get_words():
            f.write(struct.pack('>H', word))


if __name__ == '__main__':
    main()
