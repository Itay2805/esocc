# Esoteric C Compiler

A C compiler targeting esoteric architectures (for fun and profit).

```
usage: main.py [-h] [-o outfile] [-E] [-S] [-c] [-D macro[=val]] [-I path]
               infile [infile ...]

Esoteric C compiler

positional arguments:
  infile          Input files, can be either C or ASM

optional arguments:
  -h, --help      show this help message and exit
  -o outfile      Place the output into <outfile>
  -E              Preprocess only; do not compile, assemble or link.
  -S              Compile only; do not assemble or link.
  -c              Compile and assemble, but do not link.
  -D macro[=val]  Predefine name as a macro [with value]
  -I path         Path to search for unfound #include's
```

## Features (TL;DR;)
* fairly nice support for the C language from control flow to structures and function and preprocessor.
* support for multiple compilation units
* Can generate raw binaries

## Features:
### C Parsing
* nice error and warning prints
* proper type checking (hopefully)
* typedefs
* nestable structs and unions
    * only named, anonymous will be added eventually
* variables 
    * only at start of function
* global variables (and arrays)
* fixed size arrays
* All of the arithmetic/bitwise operators
* while loops with break and continue
* if/else
* Constant folding

### IR
* Based on [jtac](https://github.com/BizarreCake/jcc) (ported to python and extended with whatever we need)
    * SSA with decent register allocation and spilling support
    * Should be easy to port to new targets
* Supports both signed and unsigned operations on registers

### Code gen
#### DCPU16
* ABI based on [0x10c Standards Committee](https://github.com/0x10cStandardsCommittee/0x10c-Standards/blob/master/ABI/ABI%20draft%202.txt)
    * only stackcall for now
* Peephole optimizations
* Assembler can output object linkable files
    * contain the raw data as well as relocations and import/exports

