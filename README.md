# Esoteric C Compiler

A C compiler targeting esoteric architectures (for fun and profit).

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
