# Xenon's Languages
## Overview
This repository contains 2 programming languages:
  - A high-level programming language called XSharp
  - A low-level programming language called XAssembly

## XSharp
### `Operations`
```
value1 + value2 // Addition
value1 - value2 // Subtraction

value1 & value2 // Bitwise AND
value1 | value2 // Bitwise OR
value1 ^ value2 // Bitwise XOR
value1 >> value2 // Right Shift
value1 << value2 // Left shift

~value          // Negation
-value          // Inversion
value++         // Increment
value--         // Decrement

value1 < value2 // Less than
value1 <= value2 // Less than / equal to
value1 == value2 // Equal to
value1 != value2 // Not equal to
value1 > value2 // Greater than
value1 >= value2 // Greater than or equal to
```

### `Data types`
- `int`: Represents an integer.
- `int[]`: Represents an array of integers.

### `Array literals`
Array literals are elements encased in braces:
```
{1, 2, 3}
{1, 2, i} // Valid, assuming i is defined beforehand
```

### `Variables and constants`
Constants are defined using the `const` keyword:
```
const identifier value
```
From that point, the compiler will replace all instances of the constant with its defined value.
There are 2 built-in constants: `true` (-1) and `false` (0).

Variables are defined using the `var` keyword:
```
var identifier: data_type = expression
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
For loops have `start`, `end`, and `step` values. Their range is `[start, end)`, meaning they loop from `start` to `end - 1`.
```
for identifier start: expr end: expr step: expr { <body> }
```
While loops will execute until the value of `condition` is 0:
```
while condition { <body> }
```

### `Other Things`
The language has a few other functions:
```
include operation // includes the operations library
17 * 2 // multiplication
5 % 2 // modulo
```

## XAssembly
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
