# Xenon's Languages
## Overview
This repository contains 2 programming languages:

  - A high-level programming language called XSharp
  - A low-level programming language called XAssembly

VSCode extension for these languages: https://marketplace.visualstudio.com/items/?itemName=stufflyer.xenon-xsharp-tools

## XSharp
### `Operations`
```
value1 + value2  // Addition
value1 - value2  // Subtraction

value1 & value2  // Bitwise AND
value1 | value2  // Bitwise OR
value1 ^ value2  // Bitwise XOR
value1 >> value2 // Right Shift
value1 << value2 // Left shift

~value           // Negation
-value           // Inversion
value++          // Increment
value--          // Decrement

value1 < value2  // Less than
value1 <= value2 // Less than or equal to
value1 == value2 // Equal to
value1 != value2 // Not equal to
value1 > value2  // Greater than
value1 >= value2 // Greater than or equal to

#value           // Absolute value
$value           // Sign of value (-1 if negative, 0 if zero, 1 if positive)
```

### `Data types`
- `int`: Represents an integer.
- `int[]`: Represents an array of integers.
- `bool`: Represents a boolean (`true` or `false`).
- `bool[]`: Represents an array of booleans.

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

### `Conditionals`
If statements execute if a condition evaluates to `true` (-1).
```
if condition {
    do_something
}
```
If there are multiple conditions, you can use the `elseif` keyword:
```
if condition1 {
    do_something
} elseif condition2 {
    do_another_thing
}
```
Finally, you can use the `else` keyword to execute something if all the above conditions are false:
```
if condition1 {
    do_something
} elseif condition2 {
    do_another_thing
} else {
    do_something_else
}
```

### `Subroutines`
A subroutine is defined as follows:
```
sub sub_name(param1, param2, ...) {
    body
}
```
Once defined, a subroutine can be called using `sub_name(arg1, arg2, ...)`.

### `Writing to the screen`
You can use the `plot` keyword (deprecated) to plot a pixel value (`0` or `1`) to the buffer:
```
plot x y 0/1
```
To plot to the screen, use the subroutine calls `update()` or `flip()`:
- `update()`: Transfer the contents of the buffer to the screen.
- `flip()`: Transfer the contents of the buffer to the screen and clear it.

### `Other Things`
The language has a few other functions:
```
include operation // Includes the operations library
17 * 2 // multiplication
5 % 2 // modulo
```

## XAssembly
### `Labels`
Labels are placeholders for addresses. They are defined in a separate line before an instruction as follows:
```
0 | .label_name
1 | <remaining instructions>
```
### `NOOP`
This instruction does nothing.
### `HALT`
This instruction stops the execution of the program.
### `LDIA`
This instruction loads a 14-bit signed integer into the `Address` register.
```
LDIA value
```
### `COMP`
This instruction computes the given operation. Valid operations can be found in the `xasm_assembler.py` file.
If specified, it can store the result in the `Data` register, the `Address` register, and the RAM location pointed by the `Address` register.
It can also perform a branch if specified and matches the result.
```
COMP operation dest? jump?
```
### `PLOT`
This instruction plots a value (`0` or `1`) to the screen buffer.
The x and y coordinates are stored in 2 ports (currently with addresses 2048 and 2049).
```
PLOT value
```
### `BUFR`
This instruction is responsible for porting the buffer data to the screen.
You can specify one of four modes:
  - `move`: Moves the buffer's content onto the screen, erasing previous data on the screen and clearing the buffer.
  - `update`: Same as `move`, but doesn't clear the buffer.
```
BUFR mode
```
### `CALL`
This instruction stores the next instruction address in the call stack and jumps to the specified address. The address can be a label or a predefined constant.
It is mainly used for subroutines.
```
CALL addr
```
### `RETN`
This instruction pops the address in the call stack and jumps to that address.
