from xsharp_parser import *
from xsharp_helper import CompilationError
from typing import Literal

# Error codes: 20

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

class Compiler:
	X_ADDR = 2048
	Y_ADDR = 2049
	INPUT_ADDR = 2050

	def __init__(self):
		self.instructions: list[str] = []
		self.allocated_registers: set = set()
		self.available_registers: set[int] = {i for i in range(16)}
		self.jumps_dict: dict[int, int] = {}
		self.memory: dict[int, int] = {}
		self.subroutine_defs: list[SubroutineDef] = []
		self.plotted: bool = False

		self.symbols: dict[str, tuple[str, int]] = {
			"true": ("const", -1),
			"false": ("const", 0),
			"N_BITS": ("const", 16),
			"update": ("nativesub", 0),
			"flip": ("nativesub", 0),
			"halt": ("nativesub", 0),
			"plot": ("nativesub", 0),
		}

		self.vars: int = 0
		self.jumps: int = 0

		self.a_reg = 0
		self.d_reg = 0

		self.input_addr = 2050

		self.known_values = (-2, -1, 0, 1)

	def raise_error(self, node, code: int, message: str):
		error = Exception(message)
		if node is None:
			error.start_pos, error.end_pos = None, None
		else:
			error.start_pos, error.end_pos = node.start_pos, node.end_pos
		error.code = code
		raise error

	def compile(self, ast: Statements, remove_that_one_line: bool = False):
		result = CompileResult()
		self.a_reg = 0
		self.d_reg = 0
		self.jumps = 0

		if not ast.body:
			return result.success(["HALT"])

		try:
			self.generate_code(ast)
			if len(self.instructions) > 0 and self.instructions[-1] == "COMP A D" and remove_that_one_line:
				self.instructions = self.instructions[:-1]

			if self.plotted and "BUFR update" not in self.instructions:
				self.instructions.append("BUFR update") # Auto-update screen
			self.instructions.append("HALT")  # Ensure program ends with HALT
			self.peephole_optimize()

			for sub in self.subroutine_defs:
				self.plotted = False
				self.instructions.append(f".sub_{sub.name}")
				self.generate_code(sub.body)
				self.instructions.append("RETN")
			
			return result.success(self.instructions)
		
		except Exception as e:
			return result.fail(CompilationError(e.start_pos, e.end_pos, f"{e}\nError code: {e.code}"))

	def generate_code(self, node: Any):
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
			self.raise_error(None, 0, "Too many temporary registers! Refine your code!")

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

	def comparison(self, reg1: int, end_pos: int, jump: Literal["JLT", "JLE", "JEQ", "JGT", "JNE", "JGE"]):
		true = self.make_jump_label(False, "true")
		end = self.make_jump_label(False, "false")

		self.instructions = self.instructions[:end_pos]

		self.load_immediate(f"r{reg1}")
		self.instructions.append("COMP M-D D")
		self.load_immediate(f".true{true}")
		self.instructions.append(f"COMP D {jump}")

		self.load_immediate(f".false{end}")
		self.instructions.append("COMP 0 D JMP")

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
		self.a_reg = value if isinstance(value, int) or not value.startswith("r") else int(value[1:])

	def noVisitMethod(self, node):
		self.raise_error(node, 1, f"Unknown AST node type: {type(node).__name__}")

	def visitStatements(self, node: Statements):
		for stmt in node.body:
			self.generate_code(stmt) # Visit line by line

	def visitBinaryOperation(self, node: BinaryOperation):
		op_map = {
			"ADD": "D+M",
			"SUB": "M-D",
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
				if self.symbols.get(node.left.symbol, ("null", 0))[0] == "const":
					left = f"{self.symbols[node.left.symbol][1]}"
				else: folding = False
			else: left = f"{node.left.value}"

		if folding:
			if isinstance(node.right, (IntLiteral, Identifier)):
				if isinstance(node.right, Identifier):
					if self.symbols.get(node.right.symbol, ("null", 0))[0] == "const":
						right = f"{self.symbols[node.right.symbol][1]}"
					else: folding = False
				else:
					right = f"{node.right.value}"
			else: folding = False

			if folding:
				op = op_map.get(str(node.op.token_type), None)

				if op is None:
					self.raise_error(node, 2, f"Unsupported binary operation: {node.op}")

				value = op.replace("D", f"{left}").replace("M", f"{right}")
				result = eval(value)
				if op == "M-D": result = -result

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

		right_start: int = len(self.instructions)
		right = self.generate_code(node.right)
		# Allocate a register for right side
		right_pos: int = len(self.instructions)
		reg2 = tuple(self.available_registers - self.allocated_registers)[0]
		self.allocate_register(reg2)

		# Optimizing +/- 1
		if isinstance(node.left, Identifier) and self.symbols.get(node.left.symbol, ("const", 0))[0] != "const" and right == 1:
			if str(node.op.token_type) in ("ADD", "SUB"):
				self.instructions = self.instructions[:start_pos]
				self.a_reg = temp_a_reg
				self.load_immediate(self.symbols[node.left.symbol][1], node.left.symbol)
				self.instructions.append("COMP M++ D" if str(node.op.token_type) == "ADD" else "COMP M-- D")
				self.d_reg = self.memory[self.symbols[node.left.symbol][1]]
				self.free_register(reg1)
				self.free_register(reg2)

				return

		# Fold if necessary
		if isinstance(left, int) and isinstance(right, int):
			value = op_map[str(node.op.token_type)]

			value = value.replace("D", f"{left}")
			value = value.replace("M", f"{right}")

			self.instructions = self.instructions[:start_pos]
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

			# Free temporary registers allocated earlier
			self.free_register(reg1)
			self.free_register(reg2)

			return result

		# Unable to fold
		operation = op_map.get(str(node.op.token_type), None)
		if not operation:
			self.raise_error(node, 3, f"Unsupported binary operation: {node.op}")
		
		match operation[1:-1]:
			case "*": # Shift-and-add algorithm
				self.instructions.append("COMP 0 D")
				product = tuple(self.available_registers - self.allocated_registers)[0]
				self.allocate_register(product)

				self.load_immediate(16)
				self.instructions.append("COMP A D")
				bits = tuple(self.available_registers - self.allocated_registers)[0]
				self.allocate_register(bits)

				rshift = self.make_jump_label(False, "shift")
				loop = self.make_jump_label(name="loop")

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
				if right in (0, 1):
					self.instructions = self.instructions[:right_start]
					if right == 1:
						self.instructions.append("COMP >>M D")
						self.d_reg = self.memory[self.a_reg] >> 1
				else:
					loop = self.make_jump_label(name="loop")
					end = self.make_jump_label(False, "end")

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
				if right in (0, 1):
					self.instructions = self.instructions[:right_start]
					if right == 1:
						self.instructions.append("COMP D+M D")
						self.d_reg = self.memory[self.a_reg] << 1
				else:
					loop = self.make_jump_label(name="loop")
					end = self.make_jump_label(False, "end")

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

			case "<": self.comparison(reg1, right_pos, "JLT")
			
			case "<=": self.comparison(reg1, right_pos, "JLE")

			case "==": self.comparison(reg1, right_pos, "JEQ")

			case "!=": self.comparison(reg1, right_pos, "JNE")

			case ">": self.comparison(reg1, right_pos, "JGT")

			case ">=": self.comparison(reg1, right_pos, "JGE")

			case _:
				self.instructions = self.instructions[:-2]
				self.load_immediate(f"r{reg1}")
				self.instructions.append(f"COMP {operation} D")

		# Precompute expression
		expr = f"{self.d_reg}{operation[1:-1]}{self.memory[reg2]}"
		expr_result = eval(expr)
		if expr_result == True: expr_result = -1
		if expr_result == False: expr_result = 0
		self.d_reg = expr_result

		# Free temporary registers allocated earlier
		self.free_register(reg1)
		self.free_register(reg2)

	def visitUnaryOperation(self, node: UnaryOperation):
		if str(node.op.token_type) == "AT": # Address operator (@identifier)
			if (not self.symbols.get(node.value.symbol, None)) or (self.symbols[node.value.symbol][0] == "const"):
				self.raise_error(node, 4, f"Undefined variable: {node.value.symbol}")
			
			self.load_immediate(self.symbols.get(node.value.symbol, (0, 0))[1])
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
				self.raise_error(node, 5, f"Unsupported unary operation: {node.op}")

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
					self.raise_error(node, 5, f"Unsupported unary operation: {node.op}")
				
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
				jump = self.make_jump_label(False, "abs")
				self.load_immediate(f".abs{jump}")
				self.instructions.append("COMP D JGE")
				self.instructions.append("COMP -D D")
				self.instructions.append(f".abs{jump}")
			elif str(node.op.token_type) == "SIGN": # Sign
				neg = self.make_jump_label(False, "neg")
				pos = self.make_jump_label(False, "pos")
				end = self.make_jump_label(False, "end")
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
				self.raise_error(node, 7, f"Unsupported unary operation: {node.op}")

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
			self.load_immediate(16 + self.vars, f"array[{self.vars - base_pointer + 16}]")
			self.instructions.append("COMP D M")
			self.memory[16 + self.vars] = self.d_reg
			self.vars += 1
		return base_pointer

	def visitIdentifier(self, node: Identifier):
		if node.symbol not in self.symbols.keys():
			self.raise_error(node, 8, f"Undefined symbol: {node.symbol}")

		# Load a symbol's value into the D register.
		if self.symbols[node.symbol][0] == "const":
			# Value is already known, so just load it into D register
			value = self.symbols[node.symbol][1]
			if value in self.known_values: # Known values in the ISA
				self.instructions.append(f"COMP {value} D")
			else:
				self.load_immediate(value, node.symbol)
				self.instructions.append("COMP A D")
			
			self.d_reg = value
			return value
		
		elif self.symbols[node.symbol][0] == "array": # It is an array, in this case it will return the base pointer
			addr = self.symbols[node.symbol][1]

			if self.instructions[-1] == "COMP D M" and self.a_reg == addr:
				pass

			else:
				self.load_immediate(addr, node.symbol)
				self.instructions += ["COMP M D"]

			self.d_reg = self.memory[addr]

		else: # It is a variable, in this case it's value is not known
			addr = self.symbols[node.symbol][1]

			if self.instructions[-1] == "COMP D M" and self.a_reg == addr:
				pass

			else:
				self.load_immediate(addr, node.symbol)
				self.instructions += ["COMP M D"]
		
			self.d_reg = self.memory.get(addr, 0)

	def visitConstDefinition(self, node: ConstDefinition):
		# Check if symbol is already defined
		if node.symbol.symbol in self.symbols.keys():
			self.raise_error(node, 9, f"Symbol {node.symbol.symbol} is already defined.")
		
		start_pos = len(self.instructions)
		temp_a_reg = self.a_reg
		temp_d_reg = self.d_reg

		temp_jumps = self.jumps
		temp_jumps_dict = self.jumps_dict

		self.generate_code(node.value)
		self.symbols[node.symbol.symbol] = ("const", self.d_reg)

		self.a_reg = temp_a_reg
		self.d_reg = temp_d_reg
		self.jumps = temp_jumps
		self.jumps_dict = temp_jumps_dict
		self.instructions = self.instructions[:start_pos]

	def visitVarDeclaration(self, node: VarDeclaration):
		# Check if symbol is already defined
		if node.identifier in self.symbols.keys():
			self.raise_error(node, 10, f"Symbol {node.identifier} is already defined.")

		value: int|None = None
		if node.value:
			value = self.generate_code(node.value)
		memory_location: int = 16 + self.vars
		temp_location: int|None = None
		length = node.length

		if node.length is not None:
			if isinstance(node.length, str): # Constant
				if node.length not in self.symbols.keys():
					self.raise_error(node, 8, f"Undefined symbol: {node.length}")
				
				if self.symbols[node.length][0] != "const":
					self.raise_error(node, 21, "Expected a constant, got an identifier instead.")
				
			length = self.symbols[node.length][1]
			
			if node.value is None:
				self.vars += length
				temp_location = memory_location
				memory_location: int = 16 + self.vars
			else:
				if node.length != len(node.value.elements):
					self.raise_error(node, 11, f"Expected array length {len(node.value.elements)}, got {node.length} instead.")

			self.symbols[node.identifier] = ("array", memory_location)
			self.memory[memory_location] = value or temp_location
			value: int
			self.load_immediate(value or temp_location, f"array_{node.identifier}")
			self.instructions.append("COMP A D") # Load base pointer
			self.d_reg = self.a_reg
		else:
			match node.data_type:
				case "int":
					self.symbols[node.identifier] = ("int", memory_location)
				case "bool":
					if self.d_reg not in (-1, 0):
						self.raise_error(node.value, 16, "Expected a boolean, got an integer instead.")
					self.symbols[node.identifier] = ("bool", memory_location)
		
		comment = node.identifier
		if node.length is not None:
			comment += f" ({node.length}"
			if node.length != length: comment += f" = {length}"
			comment += " elements)"


		self.load_immediate(memory_location, comment)
		self.instructions.append("COMP D M") # Store result in D register to memory
		self.memory[memory_location] = self.d_reg
		
		self.vars += 1

	def visitAssignment(self, node: Assignment):
		if node.identifier.symbol not in self.symbols.keys():
			self.raise_error(node, 13, f"Undefined variable: {node.identifier.symbol}.")

		self.generate_code(node.expr)

		if self.symbols[node.identifier.symbol][0] == "const":
			self.raise_error(node, 12, f"Cannot assign to constant '{node.identifier.symbol}'.")

		if self.symbols[node.identifier.symbol][0] == "array":
			self.raise_error(node, 13, f"Undefined variable: {node.identifier.symbol}.")
		
		addr = self.symbols[node.identifier.symbol][1]
		
		self.load_immediate(addr, f"{node.identifier.symbol}")
		self.instructions += [
			"COMP D M"
		] # Store result in D register to memory
		self.d_reg = self.memory.get(addr, 0)

	def visitForLoop(self, node: ForLoop):
		# Check if identifier is a variable
		if node.identifier not in self.symbols.keys() or\
		self.symbols.get(node.identifier)[0] in ("const", "array", "subroutine"):
			self.raise_error(node, 14, f"Variable {node.identifier} is not defined.")
		
		location = self.symbols[node.identifier][1]

		if not node.body.body: # Loop is empty, so there is no need to execute it
			end = self.generate_code(node.end)			
			self.d_reg = end
			self.load_immediate(location, f"End value <- {node.identifier}")
			self.instructions += ["COMP D-- M"]
			self.memory[location] = self.d_reg - 1
			return

		# Set iterator to start value
		self.generate_code(node.start)
		self.load_immediate(location, f"Start value <- {node.identifier}")
		self.instructions += ["COMP D M"]
		
		self.memory[location] = self.d_reg
		jump: int = self.make_jump_label(name="for")

		self.generate_code(node.body)

		self.generate_code(node.step)
		self.instructions[-1] += f" // Step value (.for{jump})"
		step_value: int = self.d_reg
		
		self.load_immediate(location, f"{node.identifier}")
		self.instructions.append("COMP D+M DM")
		self.d_reg += self.memory[location]

		self.generate_code(node.end)
		self.instructions[-1] += f" // End value (.for{jump})"
		self.load_immediate(location, f"{node.identifier}")
		self.instructions.append("COMP D-M D")
		self.d_reg -= self.memory[location]

		self.load_immediate(f".for{jump}", f"Jump to start (.for{jump})")
		self.instructions.append("COMP D JGT") if step_value > 0 else self.instructions.append("COMP D JLT")
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

	def visitArrayAccess(self, node: ArrayAccess):
		if isinstance(node.array, Identifier) and (node.array.symbol not in self.symbols or self.symbols[node.array.symbol][0] != "array"):
			self.raise_error(node, 15, f"Undefined array: {node.array.symbol}")
		
		if isinstance(node.array, ArrayLiteral):
			base_pointer: int = self.generate_code(node.array)
			self.generate_code(node.index)

			if self.d_reg >= len(node.array.elements):
				self.raise_error(node, 17, f"Out of bounds: index must not exceed {len(node.array.elements) - 1}, found index {self.d_reg} instead.")
			
			if self.d_reg < 0:
				self.raise_error(node, 17, f"Out of bounds: index must be at least 0, found index {self.d_reg} instead.")

			self.load_immediate(base_pointer)
			self.instructions.append("COMP D+A A")
			self.a_reg += self.d_reg
			self.instructions.append("COMP M D")
			self.d_reg = self.memory[self.a_reg]
		else: # Identifier, trickier to manage but still doable
			address = self.symbols[node.array.symbol][1]
			base_pointer = self.memory[address]

			self.generate_code(node.index)
			
			if self.d_reg >= address - base_pointer:
				self.raise_error(node, 17, f"Out of bounds: index must not exceed {address - base_pointer - 1}, found index {self.d_reg} instead.")
			
			if self.d_reg < 0:
				self.raise_error(node, 17, f"Out of bounds: index must be at least 0, found index {self.d_reg} instead.")
			
			self.load_immediate(base_pointer, "Access base pointer")
			self.instructions.append("COMP D+A A")
			self.a_reg += self.d_reg
			self.instructions.append("COMP M D")
			self.d_reg = self.memory.get(self.a_reg, self.d_reg)

	def visitArraySet(self, node: ArraySet):
		if isinstance(node.array, Identifier) and (node.array.symbol not in self.symbols or self.symbols[node.array.symbol][0] != "array"):
			self.raise_error(node, 16, f"Undefined array: {node.array.symbol}")
		
		if isinstance(node.array, ArrayLiteral):
			base_pointer: int = self.generate_code(node.array)
			self.generate_code(node.index)

			if self.d_reg >= len(node.array.elements):
				self.raise_error(node, 17, f"Out of bounds: index must not exceed {len(node.array.elements) - 1}, found index {self.d_reg} instead.")
			
			if self.d_reg < 0:
				self.raise_error(node, 17, f"Out of bounds: index must be at least 0, found index {self.d_reg} instead.")

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
			address = self.symbols[node.array.symbol][1]
			base_pointer = self.memory[address]

			self.generate_code(node.index)
			
			self.load_immediate(base_pointer, "Base pointer")
			self.instructions.append("COMP D+A D")
			self.d_reg += self.a_reg

			pointer_reg = tuple(self.available_registers - self.allocated_registers)[0]
			self.allocate_register(pointer_reg)
			self.a_reg = pointer_reg

			self.generate_code(node.value)

			self.load_immediate(f"r{pointer_reg}", "Set base pointer")
			self.instructions.append("COMP M A")
			self.instructions.append("COMP D M")
			self.free_register(pointer_reg)

	def visitIfStatement(self, node: IfStatement):
		end = self.make_jump_label(False, "endif")
		for condition, body in node.cases:
			self.generate_code(condition)
			
			jump = self.make_jump_label(False, "if")
			self.load_immediate(f".if{jump}")
			self.instructions.append("COMP D JEQ")
			self.generate_code(body)
			self.load_immediate(f".endif{end}", "End if body")
			self.instructions.append("COMP 0 JMP")
			self.instructions.append(f".if{jump}")
		
		if node.else_case:
			self.generate_code(node.else_case)
		
		self.instructions.append(f".endif{end}")

	def visitSubroutineDef(self, node: SubroutineDef):
		# Check if symbol is already defined
		if node.name in self.symbols.keys():
			self.raise_error(node, 10, f"Symbol {node.name} is already defined.")

		# Allocate memory for parameters
		for param in node.parameters:
			memory_location: int = 16 + self.vars
			self.symbols[param] = ("int", memory_location)
			self.memory[memory_location] = 0
			self.vars += 1
		
		self.generate_code(IntLiteral(len(node.parameters), node.start_pos, node.end_pos))
		memory_location: int = 16 + self.vars
		self.symbols[node.name] = ("subroutine", memory_location)
		self.memory[memory_location] = len(node.parameters)
		self.subroutine_defs.append(node)
		self.vars += 1

		self.load_immediate(memory_location, f"{node.name}")
		self.instructions.append("COMP D M" if self.d_reg not in self.known_values else f"COMP {self.d_reg} M")
	
	def visitCallExpression(self, node: CallExpression):
		# Check if symbol is already defined
		if node.sub_name not in self.symbols.keys():
			self.raise_error(node, 10, f"Symbol {node.sub_name} is undefined.")
		
		# Check if symbol is a subroutine
		if self.symbols[node.sub_name][0] not in ("subroutine", "nativesub"):
			self.raise_error(node, 18, f"Symbol {node.sub_name} is not a subroutine.")
		
		if self.symbols[node.sub_name][0] == "subroutine":
			# Check number of arguments
			memory_location: int = self.symbols[node.sub_name][1]
			params: int = self.memory.get(memory_location, 0)
			if params != len(node.arguments):
				self.raise_error(node, 19, f"Expected {params} arguments, got {len(node.arguments)} arguments instead.")
			
			# Populate arguments
			for i, arg in enumerate(node.arguments):
				self.generate_code(arg)
				self.load_immediate(memory_location - params + i, f"arg_{i}")
				self.instructions.append("COMP D M")
				self.memory[memory_location - params - i] = self.d_reg
		
			self.instructions.append(f"CALL .sub_{node.sub_name}")
		else: # Native subroutines
			match node.sub_name:
				case "update":
					if len(node.arguments) != 0:
						self.raise_error(node, 19, f"Expected 0 arguments, got {len(node.arguments)} arguments instead.")
					self.instructions.append("BUFR update")
					self.plotted = True
				case "flip":
					if len(node.arguments) != 0:
						self.raise_error(node, 19, f"Expected 0 arguments, got {len(node.arguments)} arguments instead.")
					self.instructions.append("BUFR move")
					self.plotted = False
				case "halt":
					if len(node.arguments) != 0:
						self.raise_error(node, 19, f"Expected 0 arguments, got {len(node.arguments)} arguments instead.")
					self.instructions.append("HALT")
				case "plot":
					if len(node.arguments) != 3:
						self.raise_error(node, 19, f"Expected 3 arguments, got {len(node.arguments)} arguments instead.")
					
					# X Port
					self.generate_code(node.arguments[0])
					self.load_immediate(self.X_ADDR, "X Port")
					self.instructions.append("COMP D M")
					self.memory[self.X_ADDR] = self.d_reg

					# Y Port
					self.generate_code(node.arguments[1])
					self.load_immediate(self.Y_ADDR, "Y Port")
					self.instructions.append("COMP D M")
					self.memory[self.Y_ADDR] = self.d_reg

					# Value
					if not isinstance(node.arguments[2], IntLiteral):
						self.raise_error(node.arguments[2], 20, "Expected 0 or 1 for argument 3.")
					
					if node.arguments[2].value not in (0, 1):
						self.raise_error(node.arguments[2], 20, "Expected 0 or 1 for argument 3.")
					self.instructions.append(f"PLOT {node.arguments[2].value}")

					self.plotted = True
