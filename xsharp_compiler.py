from xsharp_parser import *
from xsharp_helper import CompilationError
from typing import Literal

## COMPILE RESULT
class CompileResult:
	def __init__(self):
		self.value, self.error = None, None
	
	def register(self, res):
		self.error = res.error
		return res.value
	
	def success(self, value: list[str]):
		self.value = value
		return self
	
	def fail(self, error: CompilationError):
		self.error = error
		return self

## COMPILER
class Compiler:
	def __init__(self):
		self.instructions: list[str] = []
		self.allocated_registers: set = set()
		self.available_registers: set[int] = {i for i in range(16)}
		self.constants: dict[str, int] = {"true": -1, "false": 0}
		self.variables: dict[str, int] = {}
		self.arrays: dict[str, int] = {}
		self.jumps_dict: dict[int, int] = {}
		self.memory: dict[int, int] = {}

		self.vars: int = 0
		self.jumps: int = 0

		self.a_reg = 0
		self.d_reg = 0

		self.x_addr = 2048
		self.y_addr = 2049

		self.input_addr = 2050

		self.known_values = (-2, -1, 0, 1)

	def compile(self, ast: Statements, remove_that_one_line: bool = False):
		result = CompileResult()
		self.a_reg = 0
		self.d_reg = 0

		if not ast.body:
			return result.success(["HALT"])

		try:
			self.generate_code(ast)
			if len(self.instructions) > 0 and self.instructions[-1] == "COMP A D" and remove_that_one_line:
				self.instructions = self.instructions[:-1]

			self.instructions.append("HALT")  # Ensure program ends with HALT
			self.peephole_optimize()
			
			return result.success(self.instructions)
		
		except Exception as e:
			return result.fail(CompilationError(e.start_pos, e.end_pos, f"{e}\nError code: {e.code}"))

	def generate_code(self, node):
		method_name = f"visit{type(node).__name__}"
		return getattr(self, method_name, self.noVisitMethod)(node)

	def peephole_optimize(self):
		optimized = []

		for i in range(len(self.instructions) - 1):
			curr, next_instr = self.instructions[i], self.instructions[i + 1]

			# Remove redundant `LDIA` followed by another `LDIA`
			if curr.startswith("LDIA") and next_instr.startswith("LDIA"):
				continue

			# Remove redundant double negation `-(-x)`
			check_next = curr + next_instr == "COMP -D DCOMP -D D"
			check_prev = i > 0 and curr + self.instructions[i - 1] == "COMP -D DCOMP -D D"
			if check_next or check_prev:
				continue

			# Append if no optimizations are needed
			optimized.append(curr)
		optimized.append(self.instructions[-1])
		self.instructions = optimized

	def allocate_register(self, register: int):
		# Allocates a temporary register
		if len(self.allocated_registers) == 16:
			error = Exception("Too many temporary registers! Refine your code!")
			error.start_pos = None
			error.end_pos = None
			error.code = 0
			raise error

		self.allocated_registers.add(register)
		self.available_registers.remove(register)
		loaded = False
		if register != self.a_reg:
			self.instructions.append(f"LDIA r{register}")
			self.a_reg = register
			loaded = True

		if self.instructions[-1][-1] == "D" and self.instructions[-1].startswith("COMP ") and not loaded:
			self.instructions[-1] += "M"
		else: self.instructions.append("COMP D M")

		self.memory[self.a_reg] = self.d_reg

	def free_register(self, register: int):
		# Frees up a temporary register
		self.allocated_registers.remove(register)
		self.available_registers.add(register)

	def make_jump_label(self, appending: bool = True, name: str = "jmp"):
		if appending:
			self.instructions.append(f".{name}{self.jumps}")
		
		self.jumps_dict[self.jumps] = len(self.instructions) - 1
		self.jumps += 1

		return self.jumps - 1

	def comparison(self, reg1: int, reg2: int, jump: Literal["JLT", "JLE", "JEQ", "JGT", "JNE", "JGE"]):
		true = self.make_jump_label(False)
		end = self.make_jump_label(False)

		self.load_immediate(f"r{reg1}")
		self.instructions.append("COMP M D")
		self.load_immediate(f"r{reg2}")
		self.instructions.append("COMP D-M D")
		self.load_immediate(f".true{true}")
		self.instructions.append(f"COMP D {jump}")

		self.instructions.append("COMP 0 D")
		self.load_immediate(f".false{end}")
		self.instructions.append("COMP 0 JMP")

		self.instructions.append(f".true{true}")
		self.instructions.append("COMP -1 D")
		self.instructions.append(f".false{end}")

	def load_immediate(self, value: int|str, comment: str = ""):
		# Load an immediate value into the A register
		if value in self.known_values:
			return
		else:
			if self.a_reg != value or \
			(len(self.instructions) > 0 and self.instructions[-1].startswith(".")):
				if comment: self.instructions.append(f"LDIA {value} // {comment}")
				else: self.instructions.append(f"LDIA {value}")
		self.a_reg = value

	def noVisitMethod(self, node):
		error = Exception(f"Unknown AST node type: {type(node).__name__}")
		error.start_pos = node.start_pos
		error.end_pos = node.end_pos
		error.code = 1
		raise error

	def visitStatements(self, node: Statements):
		for stmt in node.body:
			self.generate_code(stmt) # Visit line by line

	def visitBinaryOperation(self, node: BinaryOperation):
		op_map = {
			"ADD": "D+M",
			"SUB": "D-M",
			"AND": "D&M",
			"OR" : "D|M",
			"XOR": "D^M",
			"MUL": "D*M",
			"RSHIFT": "D>>M",
			"LSHIFT": "D<<M",
			"LT": "D<M",
			"LE": "D<=M",
			"EQ": "D==M",
			"GT": "D>M",
			"NE": "D!=M",
			"GE": "D>=M",
		}
		
		# Constant folding
		folding = False
		if isinstance(node.left, (IntLiteral, Identifier)) and isinstance(node.right, (IntLiteral, Identifier)):
			folding = True
			value: str

			if isinstance(node.left, Identifier):
				if node.left.symbol in self.constants:
					left = f"{self.constants[node.left.symbol]}"
				else: folding = False
			else: left = f"{node.left.value}"

		if folding:
			if isinstance(node.right, (IntLiteral, Identifier)):
				if isinstance(node.right, Identifier):
					if node.right.symbol in self.constants:
						right = f"{self.constants[node.right.symbol]}"
					else: folding = False
				else:
					right = f"{node.right.value}"
			else: folding = False

			if folding:
				op = op_map.get(str(node.op.token_type), None)

				if op is None:
					error = Exception(f"Unsupported binary operation: {node.op}")
					error.start_pos = node.start_pos
					error.end_pos = node.end_pos
					error.code = 2
					raise error

				value = op.replace("D", f"{left}").replace("M", f"{right}")
				result = eval(value)

				if result == True: result = -1
				if result == False: result = 0

				if result in self.known_values: # Known values in the ISA
					self.instructions.append(f"COMP {result} D")
				else:
					self.load_immediate(result)
					self.instructions.append(f"COMP A D")
				self.a_reg = result
				self.d_reg = result

				return result

		# Recursively fold constants
		start_pos = len(self.instructions)
		temp_a_reg = self.a_reg

		left = self.generate_code(node.left)
		# Allocate a register for left side
		reg1 = tuple(self.available_registers - self.allocated_registers)[0]
		self.allocate_register(reg1)

		right = self.generate_code(node.right)
		# Allocate a register for right side
		reg2 = tuple(self.available_registers - self.allocated_registers)[0]
		self.allocate_register(reg2)

		# Optimizing +/- 1
		if isinstance(node.left, Identifier) and node.left.symbol not in self.constants and right == 1:
			if str(node.op.token_type) in ("ADD", "SUB"):
				self.instructions = self.instructions[:start_pos]
				self.a_reg = temp_a_reg
				self.load_immediate(self.variables[node.left.symbol], node.left.symbol)
				self.instructions.append("COMP M++ D" if str(node.op.token_type) == "ADD" else "COMP M-- D")
				self.d_reg = self.memory[self.variables[node.left.symbol]]
				self.free_register(reg1)
				self.free_register(reg2)

				return

		# Fold if necessary
		if isinstance(left, int) and isinstance(right, int):
			value = op_map[str(node.op.token_type)]

			value = value.replace("D", f"{left}")
			value = value.replace("M", f"{right}")

			self.instructions = self.instructions[:start_pos]
			result = int(eval(value))

			if result in self.known_values: # Known values in the ISA
				self.instructions.append(f"COMP {result} D")
			else:
				self.load_immediate(result)
				self.instructions.append(f"COMP A D")

			self.a_reg = result
			self.d_reg = result

			# Free temporary registers allocated earlier
			self.free_register(reg1)
			self.free_register(reg2)

			return result

		# Unable to fold
		operation = op_map.get(str(node.op.token_type), None)
		if not operation:
			error = Exception(f"Unsupported binary operation: {node.op}")
			error.start_pos = node.start_pos
			error.end_pos = node.end_pos
			error.code = 3
			raise error
		
		match operation[1:-1]:
			case "*":
				self.instructions.append("COMP 0 D")
				product = tuple(self.available_registers - self.allocated_registers)[0]
				self.allocate_register(product)

				self.load_immediate(16)
				self.instructions.append("COMP A D")
				bits = tuple(self.available_registers - self.allocated_registers)[0]
				self.allocate_register(bits)

				rshift = self.make_jump_label(False)
				loop = self.make_jump_label()

				# reg1 is multiplier, reg2 is multiplicand
				self.instructions.append("COMP 1 D")
				self.load_immediate(f"r{reg2}", "Get LSB")
				self.instructions.append("COMP D&M D")
				self.load_immediate(f".shift{rshift}")
				self.instructions.append("COMP D JEQ")

				# Add multiplier to product
				self.load_immediate(f"r{reg1}", "Multiplier")
				self.instructions.append("COMP M D")
				self.load_immediate(f"r{product}")
				self.instructions.append("COMP D+M M")

				# Shift
				self.instructions.append(f".shift{rshift}")
				self.load_immediate(f"r{reg2}", "Multiplicand")
				self.instructions.append("COMP >>M M")
				self.load_immediate(f"r{reg1}", "Multiplier")
				self.instructions += [
					"COMP M D", "COMP D+M M"
				]

				# Looping
				self.load_immediate(f"r{bits}")
				self.instructions.append("COMP M-- DM")
				self.load_immediate(f".loop{loop}")
				self.instructions.append("COMP D JGE")

				self.load_immediate(f"r{product}")
				self.instructions.append("COMP M D")
				self.free_register(product)
				self.free_register(bits)
			
			case ">>":
				loop = self.make_jump_label()
				end = self.make_jump_label(False)

				self.load_immediate(f"r{reg2}")
				self.instructions.append("COMP M D")
				self.d_reg = self.memory.get(reg2, 0)

				self.load_immediate(f".end{end}")
				self.instructions.append("COMP D JLE")

				self.load_immediate(f"r{reg2}")
				self.instructions.append("COMP D-- M")

				self.load_immediate(f"r{reg1}")
				self.instructions.append("COMP M D")
				self.instructions.append("COMP >>D M")
				self.d_reg = self.memory.get(reg1, 0)
				self.memory[reg1] >>= 1

				self.load_immediate(f".loop{loop}")
				self.instructions.append("COMP 0 JMP")

				self.instructions.append(f".end{end}")
				self.load_immediate(f"r{reg1}")
				self.instructions.append("COMP M D")

			case "<<":
				loop = self.make_jump_label()
				end = self.make_jump_label()

				self.load_immediate(f"r{reg2}")
				self.instructions.append("COMP M D")
				self.d_reg = self.memory.get(reg2, 0)

				self.load_immediate(f".end{end}")
				self.instructions.append("COMP D JLE")

				self.load_immediate(f"r{reg2}")
				self.instructions.append("COMP D-- M")

				self.load_immediate(f"r{reg1}")
				self.instructions.append("COMP M D")
				self.instructions.append("COMP D+M M")
				self.d_reg = self.memory.get(reg1, 0)
				self.memory[reg1] <<= 1

				self.load_immediate(f".loop{loop}")
				self.instructions.append("COMP 0 JMP")

				self.instructions.append(f".end{end}")
				self.load_immediate(f"r{reg1}")
				self.instructions.append("COMP M D")

			case "<": self.comparison(reg1, reg2, "JLT")
			
			case "<=": self.comparison(reg1, reg2, "JLE")

			case "==": self.comparison(reg1, reg2, "JEQ")

			case "!=": self.comparison(reg1, reg2, "JNE")

			case ">": self.comparison(reg1, reg2, "JGT")

			case ">=": self.comparison(reg1, reg2, "JGE")

			case _:
				self.load_immediate(f"r{reg1}")
				self.instructions.append("COMP M D")
				self.load_immediate(f"r{reg2}")
				self.instructions.append(f"COMP {operation} D")

		# Precompute expression
		expr = f"{self.d_reg}{operation[1:-1]}{self.memory[reg2]}"
		expr_result = eval(expr)
		self.d_reg = expr_result

		# Free temporary registers allocated earlier
		self.free_register(reg1)
		self.free_register(reg2)

	def visitUnaryOperation(self, node: UnaryOperation):
		if str(node.op.token_type) == "AND": # Address operator (&identifier)
			if not {**self.variables, **self.arrays}.get(node.value.symbol, None):
				error = Exception(f"Undefined symbol: {node.value.symbol}")
				error.start_pos = node.start_pos
				error.end_pos = node.end_pos
				error.code = 4
				raise error
			
			self.load_immediate({**self.variables, **self.arrays}.get(node.value.symbol))
			self.instructions.append("COMP A D")
			return

		# Check if the operand is a constant
		if isinstance(node.value, IntLiteral):
			value = node.value.value
			if str(node.op.token_type) == "SUB":    # Negation
				folded_value = -value
			elif str(node.op.token_type) == "ADD":  # Unary plus (does nothing)
				folded_value = value
			elif str(node.op.token_type) == "NOT":  # Logical NOT
				folded_value = ~value
			elif str(node.op.token_type) == "INC":  # Increment
				folded_value = value + 1
			elif str(node.op.token_type) == "DEC":  # Decrement
				folded_value = value - 1
			elif str(node.op.token_type) == "ABS":  # Absolute value
				folded_value = abs(value)
			elif str(node.op.token_type) == "SIGN": # Sign
				folded_value = -1 if value < 0 else 0 if value == 0 else 1
			else:
				error = Exception(f"Unsupported unary operation: {node.op}")
				error.start_pos = node.start_pos
				error.end_pos = node.end_pos
				error.code = 5
				raise error

			# Append the folded value to instructions
			if folded_value in self.known_values:
				self.instructions.append(f"COMP {folded_value} D")
			else:
				self.load_immediate(folded_value)
				self.instructions.append("COMP A D")
			
			self.d_reg = folded_value
			return folded_value
		else:
			# Generate code for the operand
			start_pos = len(self.instructions)
			value = self.generate_code(node.value)

			if isinstance(value, int):
				# Fold the operation
				if str(node.op.token_type) == "SUB":
					result = -value
				elif str(node.op.token_type) == "ADD":
					result = value
				elif str(node.op.token_type) == "NOT":
					result = ~value
				elif str(node.op.token_type) == "INC":
					result = value + 1
				elif str(node.op.token_type) == "DEC":
					result = value - 1
				elif str(node.op.token_type) == "ABS":
					result = abs(value)
				elif str(node.op.token_type) == "SIGN":
					result = -1 if value < 0 else 0 if value == 0 else 1
				else:
					error = Exception(f"Unsupported unary operation: {node.op}")
					error.start_pos = node.start_pos
					error.end_pos = node.end_pos
					error.code = 6
					raise error
				
				self.instructions = self.instructions[:start_pos]

				if result in self.known_values: # Known values in the ISA
					self.instructions.append(f"COMP {result} D")
				else:
					self.instructions.append(f"LDIA {result}")
					self.instructions.append("COMP A D")
					self.a_reg = result
				self.d_reg = result
				return result

			if str(node.op.token_type) == "SUB":   # Negation
				self.instructions.append("COMP -D D") # Negate the value in A
				self.d_reg = -self.d_reg
			elif str(node.op.token_type) == "ADD": # Does nothing
				return node.value.value
			elif str(node.op.token_type) == "NOT": # Logical NOT
				if isinstance(node.value, BinaryOperation):
					instruction: str = self.instructions[-1][5:-2]
					self.instructions[-1] = f"COMP !({instruction}) D"
				else:
					self.instructions.append("COMP !D D")
				self.d_reg = ~self.d_reg
			elif str(node.op.token_type) == "INC": # Increment
				self.instructions.append("COMP D++ D")
				self.d_reg += 1
			elif str(node.op.token_type) == "DEC": # Decrement
				self.instructions.append("COMP D-- D")
				self.d_reg -= 1
			elif str(node.op.token_type) == "ABS": # Absolute value
				jump = self.make_jump_label(False)
				self.load_immediate(f".abs{jump}")
				self.instructions.append("COMP D JGE")
				self.instructions.append("COMP -D D")
				self.instructions.append(f".abs{jump}")
			elif str(node.op.token_type) == "SIGN": # Sign
				neg = self.make_jump_label(False)
				pos = self.make_jump_label(False)
				end = self.make_jump_label(False)
				self.load_immediate(f".neg{neg}")
				self.instructions.append("COMP D JLT")
				self.load_immediate(f".pos{pos}")
				self.instructions.append("COMP D JGT")
				self.load_immediate(f".end{end}")
				self.instructions.append("COMP D JMP")

				self.instructions += [
					f".neg{neg}",
					"COMP -1 D",
					f"LDIA .end{end}",
					"COMP D JMP"
				]
				self.instructions += [
					f".pos{pos}",
					"COMP 1 D",
					f"LDIA .end{end}",
					"COMP D JMP"
				]
				self.instructions.append(f".end{end}")
			else:
				error = Exception(f"Unsupported unary operation: {node.op}")
				error.start_pos = node.start_pos
				error.end_pos = node.end_pos
				error.code = 7
				raise error

	def visitIntLiteral(self, node: IntLiteral):
		if node.value in self.known_values: # Known values in the ISA
			self.instructions.append(f"COMP {node.value} D")
		
		else:
			self.load_immediate(node.value)
			self.instructions.append("COMP A D")
		
		self.d_reg = node.value
		return node.value

	def visitArrayLiteral(self, node: ArrayLiteral):
		base_pointer = 16 + self.vars
		for element in node.elements:
			self.generate_code(element)
			self.load_immediate(16 + self.vars, f"array_{len(self.arrays)}[{self.vars - base_pointer + 16}]")
			self.instructions.append("COMP D M")
			self.memory[16 + self.vars] = self.d_reg
			self.vars += 1
		return base_pointer

	def visitIdentifier(self, node: Identifier):
		# Load a symbol's value into the D register.
		if node.symbol in self.constants.keys():
			# Value is already known, so just load it into D register
			value = self.constants[node.symbol]
			if value in self.known_values: # Known values in the ISA
				self.instructions.append(f"COMP {value} D")
			else:
				self.load_immediate(value, node.symbol)
				self.instructions.append("COMP A D")
			
			self.d_reg = value
			return value

		elif node.symbol in self.variables.keys(): # It is a variable, in this case it's value is not known
			addr = self.variables[node.symbol]

			if self.instructions[-1] == "COMP D M" and self.a_reg == addr:
				pass

			else:
				self.load_immediate(addr, node.symbol)
				self.instructions += ["COMP M D"]
		
			self.d_reg = self.memory[addr]

		elif node.symbol in self.arrays.keys(): # It is an array, in this case it will return the base pointer
			addr = self.arrays[node.symbol]

			if self.instructions[-1] == "COMP D M" and self.a_reg == addr:
				pass

			else:
				self.load_immediate(addr, node.symbol)
				self.instructions += ["COMP M D"]

			self.d_reg = self.memory[addr]
		
		else:
			error = Exception(f"Undefined symbol: {node.symbol}")
			error.start_pos = node.start_pos
			error.end_pos = node.end_pos
			error.code = 8
			raise error

	def visitConstDefinition(self, node: ConstDefinition):
		# Check if symbol is already defined
		if node.symbol.symbol in {**self.constants, **self.variables}:
			error = Exception(f"Symbol {node.symbol.symbol} is already defined.")
			error.start_pos = node.start_pos
			error.end_pos = node.end_pos
			error.code = 9
			raise error
		
		expr = self.generate_code(node.value)
		self.constants[node.symbol.symbol] = expr

	def visitVarDeclaration(self, node: VarDeclaration):
		# Check if symbol is already defined
		if node.identifier in {**self.constants, **self.variables, **self.arrays}:
			error = Exception(f"Symbol {node.identifier} is already defined.")
			error.start_pos = node.start_pos
			error.end_pos = node.end_pos
			error.code = 10
			raise error

		base_pointer: int|None = self.generate_code(node.value)
		memory_location: int = 16 + self.vars

		if node.length is not None:
			if node.length != len(node.value.elements):
				error = Exception(f"Expected array length {len(node.value.elements)}, got {node.length} instead.")
				error.start_pos = node.start_pos
				error.end_pos = node.end_pos
				error.code = 11
				raise error

			self.arrays[node.identifier] = memory_location
			base_pointer: int
			self.load_immediate(base_pointer, f"array_{node.identifier}")
			self.instructions.append("COMP A D") # Load base pointer
		else:
			self.variables[node.identifier] = memory_location # Memory addresses start at location 16
		
		self.load_immediate(memory_location, f"{node.identifier}")
		self.instructions.append("COMP D M") # Store result in D register to memory
		self.memory[memory_location] = self.d_reg
		
		self.vars += 1

	def visitAssignment(self, node: Assignment):
		self.generate_code(node.expr)

		if node.identifier.symbol in self.constants:
			error = Exception(f"Cannot assign to constant '{node.identifier.symbol}'.")
			error.start_pos = node.start_pos
			error.end_pos = node.end_pos
			error.code = 12
			raise error

		if node.identifier.symbol not in self.variables:
			error = Exception(f"Undefined variable: {node.identifier.symbol}.")
			error.start_pos = node.start_pos
			error.end_pos = node.end_pos
			error.code = 13
			raise error
		
		addr = self.variables[node.identifier.symbol]
		
		self.load_immediate(addr, f"{node.identifier.symbol}")
		self.instructions += [
			"COMP D M"
		] # Store result in D register to memory
		self.d_reg = self.memory[addr]

	def visitForLoop(self, node: ForLoop):
		if not node.body.body:
			# Loop is empty, so there is no need to execute it
			if node.end in self.known_values:
				self.instructions.append(f"COMP {node.end} D")
			else:
				self.load_immediate(node.end, f"End value")
				self.instructions.append("COMP A D")
			
			self.d_reg = node.end
			return

		# Check if identifier is a variable
		if node.identifier not in self.variables:
			error = Exception(f"Variable {node.identifier} is not defined.")
			error.start_pos = node.start_pos
			error.end_pos = node.end_pos
			error.code = 14
			raise error

		# Set iterator to start value
		location = self.variables[node.identifier]
		if node.start in self.known_values:
			self.load_immediate(location, "Start value")
			self.instructions += [f"COMP {node.start} M"]
		else:
			self.load_immediate(node.start)
			self.instructions += ["COMP A D"]
			self.load_immediate(location, "Start value")
			self.instructions += [f"COMP D M"]
		
		self.memory[location] = node.start
		jump: int = self.make_jump_label(name="for")

		self.generate_code(node.body)

		if node.step in (-1, 0, 1):
			self.load_immediate(location, f"{node.identifier}")
			match node.step:
				case 0:
					self.instructions.append("COMP M D")
					self.d_reg = self.memory.get(location)
				case 1:
					self.instructions.append("COMP M++ DM")
					self.d_reg = self.memory[location] + 1
				case -1:
					self.instructions.append("COMP M-- DM")
					self.d_reg = self.memory[location] - 1
		else:
			self.load_immediate(node.step)
			self.instructions.append(f"COMP A D // Step value (.for{jump})")
			self.load_immediate(location, f"{node.identifier}")
			self.instructions.append("COMP D+M DM")
			self.d_reg += self.memory[location]

		self.load_immediate(node.end, f"End value (.for{jump})")
		self.instructions.append("COMP A-D D")
		self.d_reg = self.a_reg - self.d_reg
		self.load_immediate(f".for{jump}", f"Jump to start (.for{jump})")
		self.instructions.append("COMP D JGT") if node.step > 0 else self.instructions.append("COMP D JLT")
		self.a_reg = self.jumps_dict[jump]

	def visitWhileLoop(self, node: WhileLoop):
		jump: int = self.make_jump_label(name="while")
		end_loop: int = self.make_jump_label(appending=False, name="endwhile")

		self.generate_code(node.condition)
		self.load_immediate(f".endwhile{end_loop}")
		self.a_reg = self.jumps_dict[end_loop]
		self.instructions.append("COMP D JLE")
		self.generate_code(node.body)
		self.load_immediate(f".while{jump}")
		self.instructions.append(f"COMP 0 JMP")
		self.a_reg = self.jumps_dict[jump]

		self.instructions.append(f".endwhile{end_loop}")
		self.a_reg = self.jumps_dict[end_loop]
	
	def visitPlotExpr(self, node: PlotExpr):
		self.generate_code(node.x)
		self.load_immediate(self.x_addr, "X Port")
		self.instructions.append("COMP D M")
		self.memory[self.x_addr] = self.d_reg
		self.generate_code(node.y)
		self.load_immediate(self.y_addr, "Y Port")
		self.instructions.append("COMP D M")
		self.memory[self.y_addr] = self.d_reg
		self.instructions.append(f"PLOT {node.value}")

	def visitArrayAccess(self, node: ArrayAccess):
		res = CompileResult()
		if isinstance(node.array, Identifier) and node.array.symbol not in self.arrays:
			error = Exception(f"Undefined array: {node.array.symbol}")
			error.start_pos = node.array.start_pos
			error.end_pos = node.array.end_pos
			error.code = 15
			raise error
		
		if isinstance(node.array, ArrayLiteral):
			base_pointer: int = self.generate_code(node.array)
			self.generate_code(node.index)
			self.load_immediate(base_pointer)
			self.instructions.append("COMP D+A A")
			self.a_reg += self.d_reg
			self.instructions.append("COMP M D")
			self.d_reg = self.memory[self.a_reg]
		else: # Identifier, trickier to manage but still doable
			self.generate_code(node.array)
			self.instructions.append("COMP D A") # Base pointer

			res.register(self.compile(Statements(
				node.index.start_pos,
				node.index.end_pos,
				[node.index]
			), True))
			if res.error:
				error = Exception(res.error.details)
				error.start_pos = res.error.start_pos
				error.end_pos = res.error.end_pos
				error.code = res.error.code
				raise error
			
			self.instructions[-1] = "COMP D+A A"
			self.a_reg += self.d_reg
			self.instructions.append("COMP M D")
			self.d_reg = self.memory.get(self.a_reg, self.d_reg)

	def visitArraySet(self, node: ArraySet):
		if isinstance(node.array, Identifier) and node.array.symbol not in self.arrays:
			error = Exception(f"Undefined array: {node.array.symbol}")
			error.start_pos = node.array.start_pos
			error.end_pos = node.array.end_pos
			error.code = 16
			raise error
		
		if isinstance(node.array, ArrayLiteral):
			base_pointer: int = self.generate_code(node.array)
			self.generate_code(node.index)
			self.load_immediate(base_pointer)
			self.instructions.append("COMP D+A D")
			self.d_reg += self.a_reg

			pointer_reg = tuple(self.available_registers - self.allocated_registers)[0]
			self.allocate_register(pointer_reg)

			self.generate_code(node.value)
			self.load_immediate(pointer_reg)
			self.a_reg = self.memory.get(pointer_reg, 0)
			self.instructions.append("COMP M A")
			self.instructions.append("COMP D M")
			self.d_reg = self.memory.get(self.a_reg, 0)
		else: # Identifier, trickier to manage but still doable
			self.generate_code(node.array)

			pointer_reg = tuple(self.available_registers - self.allocated_registers)[0]
			self.allocate_register(pointer_reg)
			self.generate_code(node.index)
			self.load_immediate(f"r{pointer_reg}", "Array pointer")
			self.instructions.append("COMP D+M M")
			self.memory[pointer_reg] += self.d_reg
			self.generate_code(node.value)
			self.load_immediate(f"r{pointer_reg}", "Array pointer")
			self.instructions += [
				"COMP M A",
				"COMP D M"
			]
			self.a_reg = self.memory.get(pointer_reg, 0)
			self.d_reg = self.memory.get(self.a_reg, 0)
			self.free_register(pointer_reg)

	def visitIfStatement(self, node: IfStatement):
		end = self.make_jump_label(False, "endif")
		for condition, body in node.cases:
			self.generate_code(condition)
			
			jump = self.make_jump_label(False, "condition")
			self.load_immediate(f".condition{jump}")
			self.instructions.append("COMP D JEQ")
			self.generate_code(body)
			self.load_immediate(f".endif{end}", "End if")
			self.instructions.append("COMP 0 JMP")
			self.instructions.append(f".condition{jump}")
		
		if node.else_case:
			self.generate_code(node.else_case)
		
		self.instructions.append(f".endif{end}")
