from xsharp_parser import Statements, BinaryOperation, UnaryOperation, IntLiteral, Identifier, ConstDefinition, VarDeclaration, Assignment, ForLoop
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
		self.constants = {}
		self.variables: dict[str, int] = {}

		self.vars: int = 0
		self.jumps : int = 0

		self.a_reg = 0
		self.d_reg = 0

	def compile(self, ast, remove_that_one_line: bool = False):
		result = CompileResult()

		try:
			self.generate_code(ast)
			if self.instructions[-1] == "COMP A D" and remove_that_one_line:
				self.instructions = self.instructions[:-1]

			self.instructions.append("HALT")  # Ensure program ends with HALT
			self.peephole_optimize()
			return result.success(self.instructions)
		
		except Exception as e:
			return result.fail(CompilationError(ast.start_pos, ast.end_pos, str(e)))

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
			raise Exception("Too many temporary registers! Refine your code!")

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

	def make_jump_label(self):
		self.instructions.append(f".jmp{self.jumps}")
		self.jumps += 1

		return self.jumps - 1

	def noVisitMethod(self, node):
		raise Exception(f"Unknown AST node type: {type(node).__name__}")

	def visitStatements(self, node: Statements):
		for stmt in node.body:
			self.generate_code(stmt) # Visit line by line

	def visitBinaryOperation(self, node: BinaryOperation):
		op_map = {
			"ADD": "D+M",
			"SUB": "D-M",
			"AND": "D&M",
			"OR":  "D|M",
			"XOR": "D^M"
		}
		
		# Constant folding
		folding = False
		if isinstance(node.left, (IntLiteral, Identifier)) and isinstance(node.right, (IntLiteral, Identifier)):
			folding = True
			value: str

			if isinstance(node.left, Identifier):
				if node.left.symbol in self.constants:
					value = f"{self.constants[node.left.symbol]}"
				else: folding = False
			else: value = f"{node.left.value}"

		if folding:
			value += f"{op_map[str(node.op.token_type)][1]}"

			if isinstance(node.right, (IntLiteral, Identifier)):
				if isinstance(node.right, Identifier) and node.right.symbol in self.constants:
					value += f"{self.constants[node.right.symbol]}"
				else: folding = False
			else: value += f"{node.right.value}"

			if folding:
				self.instructions.append(f"LDIA {eval(value)}")
				self.instructions.append(f"COMP A D")
				self.a_reg = eval(value)
				return eval(value)

		# Recursively fold constants
		start_pos = len(self.instructions)

		left = self.generate_code(node.left)
		# Allocate a register for left side
		reg1 = tuple(self.available_registers - self.allocated_registers)[0]
		self.allocate_register(reg1)

		right = self.generate_code(node.right)
		# Allocate a register for right side
		reg2 = tuple(self.available_registers - self.allocated_registers)[0]
		self.allocate_register(reg2)

		# Fold if necessary
		if isinstance(left, int) and isinstance(right, int):
			value = f"{left}"
			value += f"{op_map[str(node.op.token_type)][1]}"
			value += f"{right}"

			self.instructions = self.instructions[:start_pos]
			result = eval(value)

			self.a_reg = result

			if result in (0, 1, -1): # Known values in the ISA
				self.instructions.append(f"COMP {result} D")
			else:
				self.instructions.append(f"LDIA {result}")
				self.instructions.append(f"COMP A D")

			# Free temporary registers allocated earlier
			self.free_register(reg1)
			self.free_register(reg2)
			return result

		# Unable to fold
		operation = op_map.get(str(node.op.token_type))
		if not operation:
			raise Exception(f"Unsupported binary operation: {node.op}")

		self.instructions += [
			f"LDIA r{reg1}",
			"COMP M D",
			f"LDIA r{reg2}",
			f"COMP {operation} D"
		]

		# Free temporary registers allocated earlier
		self.free_register(reg1)
		self.free_register(reg2)

	def visitUnaryOperation(self, node: UnaryOperation):
		if str(node.op.token_type) == "SUB": # Negation
			self.generate_code(node.value)
			self.instructions.append("COMP -D D")  # Negate the value in A
		
		elif str(node.op.token_type) == "ADD": # Does nothing
			pass
		
		else: # Other unary operations
			self.generate_code(node.value)

			op_map = {
				"NOT": "!D",
				"INC": "D++",
				"DEC": "D--",
			}

			operation = op_map.get(str(node.op.token_type))
			if not operation:
				raise Exception(f"Unsupported unary operation: {node.op}")

			self.instructions.append(f"COMP {operation} D")

	def visitIntLiteral(self, node: IntLiteral):
		if node.value in (0, 1, -1): # Known values in the ISA
			self.instructions.append(f"COMP {node.value} D")
		
		else:
			self.instructions.append(f"LDIA {node.value}")
			self.a_reg = node.value
			self.instructions.append("COMP A D")
		
		return node.value

	def visitIdentifier(self, node: Identifier):
		# Load a symbol's value into the A register.
		symbols = {**self.constants, **self.variables}

		if node.symbol not in symbols:
			raise Exception(f"Undefined symbol: {node.symbol}")

		if node.symbol in self.constants:
			# Value is already known, so just load it into A register
			value = self.constants[node.symbol]
			if value in (0, 1, -1): # Known values in the ISA
				self.instructions.append(f"COMP {value} D")
			
			else:
				self.instructions.append(f"LDIA {value}")
				self.a_reg = value
				self.instructions.append("COMP A D")
			return value

		else: # Value must be a variable, in this case it's value is not known
			addr = self.variables[node.symbol]

			if self.instructions[-1] == "COMP D M" and self.a_reg == addr:
				pass

			else:
				self.instructions += [f"LDIA {addr} // {node.symbol}", "COMP M D"]
				self.a_reg = addr

	def visitConstDefinition(self, node: ConstDefinition):
		# Check if symbol is already defined
		if node.symbol.symbol in {**self.constants, **self.variables}:
			raise Exception(f"Symbol {node.symbol.symbol} is already defined.")
		
		self.constants[node.symbol.symbol] = node.value.value

	def visitVarDeclaration(self, node: VarDeclaration):
		# Check if symbol is already defined
		if node.identifier in {**self.constants, **self.variables}:
			raise Exception(f"Symbol {node.identifier} is already defined.")

		self.generate_code(node.value)

		self.variables[node.identifier] = 16 + self.vars # Memory addresses start at location 16
		self.instructions += [
			f"LDIA {16 + self.vars} // {node.identifier}",
			"COMP D M"
		] # Store result in D register to memory
		self.a_reg = 16 + self.vars
		self.vars += 1

	def visitAssignment(self, node: Assignment):
		self.generate_code(node.expr)
		if node.identifier.symbol not in self.variables:
			raise Exception(f"Undefined symbol: {node.identifier.symbol}.")
		
		addr = self.variables[node.identifier.symbol]
		
		self.instructions += [
			f"LDIA {addr} // {node.identifier.symbol}",
			"COMP D M"
		] # Store result in D register to memory
		self.a_reg = addr

	def visitForLoop(self, node: ForLoop):
		# Check if identifier is a variable
		if node.identifier not in self.variables:
			raise Exception(f"Symbol {node.identifier} is not defined.")
		
		jump: int = self.make_jump_label()

		# Set iterator to start value
		location = self.variables[node.identifier]
		self.instructions += [
			f"LDIA {node.start} // Start value (.jmp{jump})",
			"COMP A D",
			f"LDIA {location} // {node.identifier}",
			"COMP M D"
		]
		self.a_reg = node.start

		self.generate_code(node.body)
		self.instructions += [
			f"LDIA {node.step} // Step value (.jmp{jump})",
			"COMP D+A D",
			f"LDIA {location} // {node.identifier}",
			"COMP M D",
			f"LDIA {node.end} // End value (.jmp{jump})",
			"COMP A-D D",
			f"LDIA .jmp{jump}",
			"COMP D JLT"
		]
		self.a_reg = node.end
