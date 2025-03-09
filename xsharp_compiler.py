from xsharp_parser import *
from xsharp_helper import CompilationError

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
		self.available_registers: set = {i for i in range(16)}
		self.constants: dict[str, int] = {"true": -1, "false": 0}
		self.variables: dict[str, int] = {}
		self.jumps_dict: dict[int, int] = {}

		self.vars: int = 0
		self.jumps: int = 0

		self.a_reg = 0
		self.d_reg = 0

		self.x_addr = 2048
		self.y_addr = 2049

		self.input_addr = 2050

		self.known_values = (-2, -1, 0, 1)

	def compile(self, ast, remove_that_one_line: bool = False):
		result = CompileResult()
		self.make_bools: bool = False

		try:
			self.generate_code(ast)
			if self.instructions[-1] == "COMP A D" and remove_that_one_line:
				self.instructions = self.instructions[:-1]

			self.instructions.append("HALT")  # Ensure program ends with HALT
			self.peephole_optimize()
			
			return result.success(self.instructions)
		
		except Exception as e:
			return result.fail(CompilationError(e.start_pos, e.end_pos, str(e)))

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
			raise error

		self.allocated_registers.add(register)
		self.available_registers.remove(register)
		loaded = False
		if register != self.a_reg:
			self.instructions.append(f"LDIA r{register}")
			loaded = True

		if self.instructions[-1].endswith(" D") and self.instructions[-1].startswith("COMP ") and not loaded:
			self.instructions[-1] += "M"
		else: self.instructions.append("COMP D M")

	def free_register(self, register: int):
		# Frees up a temporary register
		self.allocated_registers.remove(register)
		self.available_registers.add(register)

	def make_jump_label(self, appending: bool = True):
		if appending:
			self.instructions.append(f".jmp{self.jumps}")
		
		self.jumps_dict[self.jumps] = len(self.instructions) - 1
		self.jumps += 1

		return self.jumps - 1

	def load_immediate(self, value: int|str, comment: str = ""):
		# Load an immediate value into the A register
		if value in self.known_values:
			return
		else:
			if self.a_reg != value or self.instructions[-1].startswith("."):
				if comment: self.instructions.append(f"LDIA {value} // {comment}")
				else: self.instructions.append(f"LDIA {value}")
		self.a_reg = value

	def noVisitMethod(self, node):
		error = Exception(f"Unknown AST node type: {type(node).__name__}")
		error.start_pos = node.start_pos
		error.end_pos = node.end_pos
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
					raise error

				value = op.replace("D", f"{left}").replace("M", f"{right}")
				result = eval(value)

				if result in self.known_values: # Known values in the ISA
					self.instructions.append(f"COMP {result} D")
				else:
					self.load_immediate(result)
					self.instructions.append(f"COMP A D")
				self.a_reg = result
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
				self.free_register(reg1)
				self.free_register(reg2)

				return

		# Fold if necessary
		if isinstance(left, int) and isinstance(right, int):
			value = op_map[str(node.op.token_type)].replace("D", f"{left}").replace("M", f"{right}")

			self.instructions = self.instructions[:start_pos]
			result = int(eval(value))

			self.a_reg = result

			if result in self.known_values: # Known values in the ISA
				self.instructions.append(f"COMP {result} D")
			else:
				self.load_immediate(result)
				self.instructions.append(f"COMP A D")

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
			raise error

		self.load_immediate(f"r{reg1}")
		self.instructions.append("COMP M D")
		self.load_immediate(f"r{reg2}")
		self.instructions.append(f"COMP {operation} D")

		# Free temporary registers allocated earlier
		self.free_register(reg1)
		self.free_register(reg2)

	def visitUnaryOperation(self, node: UnaryOperation):
		if str(node.op.token_type) == "AND": # Address operator (&identifier)
			if not self.variables.get(node.value.symbol, None):
				error = Exception(f"Variable '{node.value.symbol}' not found.")
				error.start_pos = node.start_pos
				error.end_pos = node.end_pos
				raise error
			
			self.load_immediate(self.variables.get(node.value.symbol))
			self.instructions.append("COMP A D")
			return

		# Check if the operand is a constant
		if isinstance(node.value, IntLiteral):
			value = node.value.value
			if str(node.op.token_type) == "SUB":  # Negation
				folded_value = -value
			elif str(node.op.token_type) == "ADD":  # Unary plus (does nothing)
				folded_value = value
			elif str(node.op.token_type) == "NOT":  # Logical NOT
				folded_value = ~value
			elif str(node.op.token_type) == "INC":  # Increment
				folded_value = value + 1
			elif str(node.op.token_type) == "DEC":  # Decrement
				folded_value = value - 1
			else:
				error = Exception(f"Unsupported unary operation: {node.op}")
				error.start_pos = node.start_pos
				error.end_pos = node.end_pos
				raise error

			# Append the folded value to instructions
			if folded_value in self.known_values:
				self.instructions.append(f"COMP {folded_value} D")
			else:
				self.load_immediate(folded_value)
				self.instructions.append("COMP A D")
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
				else:
					error = Exception(f"Unsupported unary operation: {node.op}")
					error.start_pos = node.start_pos
					error.end_pos = node.end_pos
					raise error
				
				self.instructions = self.instructions[:start_pos]

				if result in self.known_values: # Known values in the ISA
					self.instructions.append(f"COMP {result} D")
				else:
					self.instructions.append(f"LDIA {result}")
					self.instructions.append("COMP A D")
					self.a_reg = result
				return result

			if str(node.op.token_type) == "SUB":  # Negation
				self.instructions.append("COMP -D D")  # Negate the value in A
			elif str(node.op.token_type) == "ADD":  # Does nothing
				return node.value.value
			elif str(node.op.token_type) == "NOT":  # Logical NOT
				if isinstance(node.value, BinaryOperation):
					instruction: str = self.instructions[-1][5:-2]
					self.instructions[-1] = f"COMP !({instruction}) D"
				else:
					self.instructions.append("COMP !D D")
			elif str(node.op.token_type) == "INC":  # Increment
				self.instructions.append("COMP D++ D")
			elif str(node.op.token_type) == "DEC":  # Decrement
				self.instructions.append("COMP D-- D")
			else:
				error = Exception(f"Unsupported unary operation: {node.op}")
				error.start_pos = node.start_pos
				error.end_pos = node.end_pos
				raise error

	def visitIntLiteral(self, node: IntLiteral):
		if node.value in self.known_values: # Known values in the ISA
			self.instructions.append(f"COMP {node.value} D")
		
		else:
			self.load_immediate(node.value)
			self.instructions.append("COMP A D")
		
		return node.value

	def visitIdentifier(self, node: Identifier):
		# Load a symbol's value into the A register.
		symbols = {**self.constants, **self.variables}

		if node.symbol not in symbols:
			error = Exception(f"Undefined symbol: {node.symbol}")
			error.start_pos = node.start_pos
			error.end_pos = node.end_pos
			raise error

		if node.symbol in self.constants:
			# Value is already known, so just load it into A register
			value = self.constants[node.symbol]
			if value in self.known_values: # Known values in the ISA
				self.instructions.append(f"COMP {value} D")
			
			else:
				self.load_immediate(value, node.symbol)
				self.instructions.append("COMP A D")
			return value

		else: # Value must be a variable, in this case it's value is not known
			addr = self.variables[node.symbol]

			if self.instructions[-1] == "COMP D M" and self.a_reg == addr:
				pass

			else:
				self.load_immediate(addr, node.symbol)
				self.instructions += ["COMP M D"]

	def visitConstDefinition(self, node: ConstDefinition):
		# Check if symbol is already defined
		if node.symbol.symbol in {**self.constants, **self.variables}:
			error = Exception(f"Symbol {node.symbol.symbol} is already defined.")
			error.start_pos = node.start_pos
			error.end_pos = node.end_pos
			raise error
		
		expr = Compiler().generate_code(node.value)
		self.constants[node.symbol.symbol] = expr

	def visitVarDeclaration(self, node: VarDeclaration):
		# Check if symbol is already defined
		if node.identifier in {**self.constants, **self.variables}:
			error = Exception(f"Symbol {node.identifier} is already defined.")
			error.start_pos = node.start_pos
			error.end_pos = node.end_pos
			raise error

		self.generate_code(node.value)

		self.variables[node.identifier] = 16 + self.vars # Memory addresses start at location 16
		self.load_immediate(16 + self.vars, f"{node.identifier}")
		self.instructions += [
			"COMP D M"
		] # Store result in D register to memory
		self.vars += 1

	def visitAssignment(self, node: Assignment):
		self.generate_code(node.expr)

		if node.identifier.symbol in self.constants:
			error = Exception(f"Cannot assign to constant '{node.identifier.symbol}'.")
			error.start_pos = node.start_pos
			error.end_pos = node.end_pos
			raise error

		if node.identifier.symbol not in self.variables:
			error = Exception(f"Undefined symbol: {node.identifier.symbol}.")
			error.start_pos = node.start_pos
			error.end_pos = node.end_pos
			raise error
		
		addr = self.variables[node.identifier.symbol]
		
		self.load_immediate(addr, f"{node.identifier.symbol}")
		self.instructions += [
			"COMP D M"
		] # Store result in D register to memory

	def visitForLoop(self, node: ForLoop):
		if not node.body.body:
			# Loop is empty, so there is no need to execute it
			if node.end in self.known_values:
				self.instructions.append(f"COMP {node.end} D")
			else:
				self.load_immediate(node.end, f"End value")
				self.instructions.append("COMP A D")
			return

		# Check if identifier is a variable
		if node.identifier not in self.variables:
			error = Exception(f"Symbol {node.identifier} is not defined.")
			error.start_pos = node.start_pos
			error.end_pos = node.end_pos
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
		jump: int = self.make_jump_label()

		self.generate_code(node.body)

		if node.step in self.known_values:
			self.load_immediate(location, f"{node.identifier}")
			match node.step:
				case 0: self.instructions.append("COMP M D")
				case 1: self.instructions.append("COMP M++ DM")
				case -1: self.instructions.append("COMP M-- DM")
		else:
			self.load_immediate(node.step)
			self.instructions.append(f"COMP A D // Step value (.jmp{jump})")
			self.load_immediate(location, f"{node.identifier}")
			self.instructions.append("COMP D+M DM")

		self.load_immediate(node.end, f"End value (.jmp{jump})")
		self.instructions.append("COMP A-D D")
		self.load_immediate(f".jmp{jump}", f"Jump to start (.jmp{jump})")
		self.instructions.append("COMP D JGT") if node.step > 0 else self.instructions.append("COMP D JLT")
		self.a_reg = self.jumps_dict[jump]

	def visitWhileLoop(self, node: WhileLoop):
		jump: int = self.make_jump_label()
		end_loop: int = self.make_jump_label(appending=False)

		self.generate_code(node.condition)
		self.load_immediate(f".jmp{end_loop}")
		self.a_reg = self.jumps_dict[end_loop]
		self.instructions.append("COMP D JLE")
		self.generate_code(node.body)
		self.load_immediate(f".jmp{jump}")
		self.instructions.append(f"COMP 0 JMP")
		self.a_reg = self.jumps_dict[jump]

		self.instructions.append(f".jmp{end_loop}")
		self.a_reg = self.jumps_dict[end_loop]
	
	def visitPlotExpr(self, node: PlotExpr):
		self.generate_code(node.x)
		self.load_immediate(self.x_addr, "X Port")
		self.instructions.append("COMP D M")
		self.generate_code(node.y)
		self.load_immediate(self.y_addr, "Y Port")
		self.instructions.append("COMP D M")
		self.instructions.append(f"PLOT {node.value}")
