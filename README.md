# XSharp
## Overview
This is a programming language for creeperdoesredstone's computer - Xenon.

## Syntax
### `Operations`
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

### `Variables and constants`
Constants are defined using the `const` keyword:
```
const identifier value
```
From that point, the compiler will replace all instances of the constant with its defined value.

Variables are defined using the `var` keyword:
```
var identifier expression
```
This allocates a memory address for the variable.
Unlike constants, variables can be changed using the `=` operator:
```
identifier = expression
```
The memory address of a variable can be accessed using the `&` operator:
```
&identifier
```

### `Loops`
For loops have `start`, `end`, and `step` values:
Their range is `[start, end)`, meaning they loop from `start` to `end - 1`.
```
for identifier start: expr end: expr step: expr { <body> }
```
While loops will execute until the value of `condition` is 0:
```
while condition { <body> }
```

## Assembly
There are currently 5 instructions: `LDIA`, `COMP`, `NOOP`, `HALT`, and `PLOT`:
```
LDIA: Loads a value into the A register.
Syntax: LDIA value
```
```
COMP: Executes the ALU code, stores it into the specified destination(s), and jumps if necessary.
Syntax: COMP code dest? jump?

Destinations: Data (D) register, Address (A) register, Memory (M)
Jumps: JLT, JEQ, JLE, JGT, JNE, JGE, JMP
```
```
PLOT: Plot the value (0 or 1) based on the x and y values stored in 2 ports.
Syntax: PLOT value
```
```
NOOP: Nothing!
HALT: Stops the execution of the program.
```
