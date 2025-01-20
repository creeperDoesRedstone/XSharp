# XSharp
## Overview
This is a programming language for creeperdoesredstone's computer - Xenon.

## Syntax
### Operations
```
value1 + value2 // Addition
value1 - value2 // Subtraction
value1 & value2 // Bitwise AND
value1 | value2 // Bitwise OR
value1 ^ value2 // Bitwise XOR
~value          // Negation
-value          // Inversion
value++         // Increment
value--         // Decrement
```

### Variables and constants
Constants are defined using the `define` keyword:
```
define identifier value
```
From that point, the compiler will replace all instances of the constant with its defined value.

Variables are defined using the `var` keyword:
```
var identifier expression
```
This allocates a memory address for the variable.
Unlike constants, variables can be changed using the `:` operator:
```
identifier: expression
```

### Loops
For loops have `start`, `end`, and `step` values:
```
for identifier start: expr end: expr step: expr { <body> }
```

## Assembly
There are currently 4 instructions: `LDIA`, `COMP`, `NOOP`, `HALT`:
```
LDIA: Loads a value into the A register.
Syntax: LDIA value
```
```
COMP: Executes the ALU code, stores it into the specified destination(s), and jumps if necessary.
Destinations: Data (D) register, Address (A) register, Memory (M)
Jumps: JLT, JEQ, JLE, JGT, JNE, JGE, JMP
Syntax: COMP code dest? jump?
```
```
NOOP: Nothing!
HALT: Stops the execution of the program.
```
