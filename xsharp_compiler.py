from xsharp_parser import *
from xsharp_helper import CompilationError
from typing import Literal

# Error codes: [0..11]

class CompileResult:
	def __init__(self):
		self.value, self.error = None, None
	
	def register(self, res):
		self.error = res.error
		return res.value
	
	def success(self, value):
		self.value = value
		return self
	
	def fail(self, error: CompilationError):
		self.error = error
		return self

class Environment:
	def __init__(self):
		self.symbols = {
			"true": -1, "false": 0, "N_BITS": 16,
			"update": 0, "flip": 0, "halt": 0, "plot": 0,
		}
		self.constants = ["true", "false", "N_BITS"]
		self.subroutines = {}
		self.arrays = {}

		self.assign_address = 16

		self.native_subs = {
			"update": 0,
			"flip": 0,
			"halt": 0,
			"plot": 3,
		}
	
	def define_symbol(self, symbol: str, value: int|tuple[int, int], var_type: Literal["const", "sub", "var", "array"]):
		res = CompileResult()

		if symbol in self.symbols:
			return res.fail(CompilationError(
				None, None,
				f"Symbol {symbol} is already defined.", 3
			))
		if var_type == "const":
			self.constants.append(symbol)
		elif var_type == "sub":
			self.subroutines[symbol] = value[1]
		elif var_type == "array":
			self.arrays[symbol] = value[1]
		
		self.symbols[symbol] = value[0] if var_type in ("array", "sub") else value
		if var_type != "const": self.assign_address += 1
		return res.success(None)
	
	def get_symbol(self, iden: Identifier|str):
		res = CompileResult()
		symbol = iden.symbol if isinstance(iden, Identifier) else iden

		if symbol not in self.symbols:
			return res.fail(CompilationError(
				iden.start_pos, iden.end_pos,
				f"Symbol {symbol} is undefined.", 4
			))
		return res.success(self.symbols[symbol])

class Compiler:
	MAX_RAM_ADDR = 2047
	X_ADDR = MAX_RAM_ADDR + 1
	Y_ADDR = MAX_RAM_ADDR + 2
	INPUT_ADDR = MAX_RAM_ADDR + 3

	KNOWN_VALUES = (-2, -1, 0, 1)

	def __init__(self):
		self.instructions: list[str] = []

		self.available_registers = {i for i in range(16)}
		self.allocated_registers = set()

	def compile(self, ast: Statements, remove_that_one_line: bool = False):
		res = CompileResult()
		env = Environment()
		
		self.jumps: int = 0
		self.tabs: int = 0
		self.address: int|str = 0

		if not ast.body + ast.subroutine_defs: return res.success(["HALT"])

		# Predefine subroutines
		for sub in ast.subroutine_defs:
			res.register(self.visitSubroutineDef(sub, env))
			if res.error: return res

		res.register(self.visit(ast, env))
		if res.error: return res
		self.write("HALT")

		# Generate subroutine bodies
		for sub in ast.subroutine_defs:
			self.write(f".sub_{sub.name}")
			self.comment(f"{len(sub.parameters)} params")

			self.tabs += 1
			res.register(self.visit(sub.body, env))
			if res.error: return res
			self.write("RETN")
			self.tabs -= 1

		return res.success(self.instructions)

	def visit(self, node, env: Environment):
		method_name = f"visit{type(node).__name__}"
		method = getattr(self, method_name, self.no_visit_method)
		return method(node, env)

	def no_visit_method(self, node, env: Environment):
		return CompileResult().fail(CompilationError(
			node.start_pos, node.end_pos,
			f"Undefined visit{type(node).__name__} method.", 0
		))

	def allocate(self, node) -> CompileResult:
		res = CompileResult()
		if not self.available_registers:
			return res.fail(CompilationError(
				node.start_pos, node.end_pos,
				"Allocation limit exceeded!", 1
			))
		
		free_register: int = tuple(self.available_registers - self.allocated_registers)[0]
		self.allocated_registers.add(free_register)
		self.available_registers.remove(free_register)

		return res.success(f"r{free_register}")

	def free_register(self, register: str) -> None:
		int_reg: int = int(register[1:])

		self.allocated_registers.remove(int_reg)
		self.available_registers.add(int_reg)

	def write(self, instruction: str) -> None:
		self.instructions.append("\t"*self.tabs + instruction)

	def truncate(self, pos: int) -> None:
		self.instructions = self.instructions[:pos]

	def make_jump(self) -> int:
		self.jumps += 1
		return self.jumps - 1

	def load_immediate(self, value: int|str, forced: bool = False) -> None:
		"""Load an immediate value into the A register."""
		if self.address != value or forced: self.write(f"LDIA {value}")

		if isinstance(value, int): self.address = value
		else:
			if value.startswith("r"): self.address = int(value[1:])
			else: self.address = value

	def comment(self, comment: str) -> None:
		"""Comments the last instruction."""
		self.instructions[-1] += f" // {comment}"

	def visitStatements(self, node: Statements, env: Environment) -> CompileResult:
		res = CompileResult()

		for stmt in node.body:
			res.register(self.visit(stmt, env))
			if res.error: return res
		
		return res.success(self.instructions)

	def visitIntLiteral(self, node: IntLiteral, env: Environment) -> CompileResult:
		if node.value in self.KNOWN_VALUES: self.write(f"COMP {node.value} D")
		else:
			self.load_immediate(node.value)
			self.write("COMP A D")
		return CompileResult().success(node.value)

	def visitArrayLiteral(self, node: ArrayLiteral, env: Environment) -> CompileResult:
		res = CompileResult()
		base_pointer = env.assign_address

		for element in node.elements:
			res.register(self.visit(element, env))
			if res.error: return res

			self.load_immediate(env.assign_address)
			self.comment(f"array[{env.assign_address - base_pointer}]")
			self.write("COMP D M")
			env.assign_address += 1
		
		return res.success(base_pointer)

	def visitBinaryOperation(self, node: BinaryOperation, env: Environment) -> CompileResult:
		res = CompileResult()
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
		operation: str = str(node.op.token_type)
		expr: str = op_map[operation]

		left_pos = len(self.instructions)
		left = res.register(self.visit(node.left, env))
		if res.error: return res
		reg_left: str = res.register(self.allocate(node.left))
		if res.error: return res

		self.load_immediate(reg_left)
		self.write("COMP D M")

		right_pos = len(self.instructions)
		right = res.register(self.visit(node.right, env))
		if res.error: return res
		reg_right: str = res.register(self.allocate(node.right))
		if res.error: return res

		if isinstance(left, int) and isinstance(right, int):
			self.truncate(left_pos)
			value = eval(
				expr.replace("D", f"{left}").replace("M", f"{right}")
			)
			if isinstance(value, bool): value = -int(value) # Ensures true = -1, false = 0
			if operation == "SUB": value = -value # Subtraction fix

			return self.visitIntLiteral(IntLiteral(value, None, None), env)
		
		def comparison(op: Literal["LT", "LE", "GT", "GE", "EQ", "NE"]) -> None:
			jmp = self.make_jump()

			if right == 0:
				self.truncate(right_pos)
			else:
				self.load_immediate(reg_left)
				self.write("COMP M-D D")
			
			self.load_immediate(f".true{jmp}")
			self.write(f"COMP D J{op}")
			self.load_immediate(f".end{jmp}")
			self.write("COMP 0 D JMP")

			self.write(f".true{jmp}")
			self.write("COMP -1 D")
			self.write(f".end{jmp}")

		if operation == "MUL":
			# Shift-and-add algorithm
			self.write("COMP 0 D")
			product: str = res.register(self.allocate(node))
			if res.error: return res

			self.visitIntLiteral(IntLiteral(16, None, None), env)
			bits: str = res.register(self.allocate(node))
			if res.error: return res

			mul_loop: int = self.make_jump()

			self.write(f".mul_loop{mul_loop}")
			self.write("COMP 1 D")
			self.load_immediate(reg_right); self.comment("Get LSB")
			self.write("COMP D&M D")
			self.load_immediate(f".mul_shift{mul_loop}")
			self.write("COMP D JEQ")

			# Add multiplier to product
			self.load_immediate(reg_left); self.comment("Multiplier")
			self.write("COMP M D")
			self.load_immediate(product); self.comment("Product")
			self.write("COMP D M")

			# Shift multiplier and multiplicand
			self.write(f".mul_shift{mul_loop}")
			self.load_immediate(reg_right)
			self.write("COMP >>M M")
			self.load_immediate(reg_left)
			self.write("COMP M D")
			self.write("COMP D+M M")

			# Looping
			self.load_immediate(f"{bits}")
			self.write("COMP M-- DM")
			self.load_immediate(f".mul_loop{mul_loop}")
			self.write("COMP D JGE")

			self.load_immediate(f"{product}", forced=True)
			self.write("COMP M D")
			self.free_register(product)
			self.free_register(bits)
		
		elif operation in ("LT", "LE", "GT", "GE", "EQ", "NE"):
			comparison(operation)
		
		else:
			self.load_immediate(reg_left)
			self.write(f"COMP {expr} D")
		
		self.free_register(reg_left)
		self.free_register(reg_right)
		return res.success(None)

	def visitUnaryOperation(self, node: UnaryOperation, env: Environment) -> CompileResult:
		res = CompileResult()
		operation: str = str(node.op.token_type)
		
		start_pos: int = len(self.instructions)
		value = res.register(self.visit(node.value, env))
		if res.error: return res

		if isinstance(value, int):
			self.truncate(start_pos)
			folded_value: int = value
			match operation:
				case "SUB": folded_value = -value
				case "ADD": ...
				case "NOT": folded_value = ~value
				case "INC": folded_value = value + 1
				case "DEC": folded_value = value - 1
				case "ABS": folded_value = abs(value)
				case "SIGN": folded_value = -1 if value < 0 else 0 if value == 0 else 1
				case _: return res.fail(CompilationError(
					node.op.start_pos, node.op.end_pos,
					f"Unsupported unary operator: {operation}", 2
				))

			return self.visitIntLiteral(IntLiteral(folded_value, None, None), env)
		else:
			match operation:
				case "SUB": self.write("COMP -D D")
				case "ADD": ...
				case "NOT": self.write("COMP !D D")
				case "INC": self.write("COMP D++ D")
				case "DEC": self.write("COMP D-- D")
				case "ABS":
					abs_jmp = self.make_jump()
					self.load_immediate(f".abs{abs_jmp}")
					self.write("COMP D JGE"); self.write("COMP -D D")
					self.write(f".abs{abs_jmp}")
				case "SIGN":
					neg = self.make_jump()
					pos = self.make_jump()
					end = self.make_jump()

					self.load_immediate(f".neg{neg}")
					self.write("COMP D JLT")
					self.load_immediate(f".pos{pos}")
					self.write("COMP D JGT")
					self.load_immediate(f".end{end}")
					self.write("COMP D JMP")

					self.write(f".neg{neg}")
					self.write("COMP -1 D")
					self.load_immediate(f".end{end}")
					self.write("COMP D JMP")
					self.write(f".pos{pos}")
					self.write("COMP 1 D")
					self.write(f".end{end}")
				case _: return res.fail(CompilationError(
					node.op.start_pos, node.op.end_pos,
					f"Unsupported unary operator: {operation}", 2
				))
			return res.success(None)

	def visitIdentifier(self, node: Identifier, env: Environment) -> CompileResult:
		res = CompileResult()

		value: int = res.register(env.get_symbol(node))
		if res.error: return res

		if node.symbol in env.constants + list(env.arrays.keys()):
			return self.visitIntLiteral(IntLiteral(value, None, None), env)
		
		self.load_immediate(value); self.comment(node.symbol)
		self.write("COMP M D")
		return res.success(None)

	def visitConstDefinition(self, node: ConstDefinition, env: Environment) -> CompileResult:
		res = CompileResult()
		start_pos = len(self.instructions)

		value = res.register(self.visit(node.value, env))
		if res.error: return res

		self.truncate(start_pos)
		result = env.define_symbol(node.symbol.symbol, value, "const")
		return result

	def visitVarDeclaration(self, node: VarDeclaration, env: Environment) -> CompileResult:
		res = CompileResult()
		location = env.assign_address

		value_pos = len(self.instructions)
		value = res.register(self.visit(node.value, env)) if node.value else None
		if res.error: return res

		if node.length is not None:
			length = node.length

			if isinstance(node.length, str):
				if node.length not in env.constants:
					return res.fail(CompilationError(
						node.start_pos, node.end_pos,
						f"Undefined constant: {node.length}", 7
					))
				length = res.register(env.get_symbol(node.length))
			
			if node.value is None:
				env.assign_address += length
			else:
				if length != len(node.value.elements):
					return res.fail(CompilationError(
						node.start_pos, node.end_pos,
						f"Expected {length} elements, got {len(node.value.elements)} elements instead.", 8
					))
			
			# print(location, env.assign_address)
			res.register(env.define_symbol(node.identifier, (location, env.assign_address), "array"))
			self.load_immediate(location)
			self.write("COMP A D")
			location = env.assign_address - 1
			if res.error: return res
				
		else:
			if node.data_type == "bool":
				if value not in (-1, 0): return res.fail(CompilationError(
					node.value.start_pos, node.value.end_pos,
					"Expected a boolean, found an integer instead.", 5
				))
			res.register(env.define_symbol(node.identifier, location, "var"))
			if res.error: return res
		
		if value in self.KNOWN_VALUES: self.truncate(value_pos)		
		self.load_immediate(location)
		self.comment(node.identifier)
		self.write("COMP D M" if value not in self.KNOWN_VALUES else f"COMP {value} M")

		return res.success(None)

	def visitAssignment(self, node: Assignment, env: Environment) -> CompileResult:
		res = CompileResult()

		if node.identifier.symbol in env.constants:
			return res.fail(CompilationError(
				node.identifier.start_pos, node.identifier.end_pos,
				f"Cannot assign to constant {node.identifier.symbol}.", 6
			))
		if node.identifier.symbol in env.subroutines:
			return res.fail(CompilationError(
				node.identifier.start_pos, node.identifier.end_pos,
				f"Cannot assign to subroutine {node.identifier.symbol}.", 6
			))

		start_pos = len(self.instructions)
		value = res.register(self.visit(node.expr, env))
		if res.error: return res

		address = res.register(env.get_symbol(node.identifier))
		if res.error: return res

		if value in self.KNOWN_VALUES: self.truncate(start_pos)

		self.load_immediate(address); self.comment(node.identifier.symbol)
		self.write("COMP D M" if value not in self.KNOWN_VALUES else f"COMP {value} M")

		return res.success(None)

	def visitCForLoop(self, node: CForLoop, env: Environment) -> CompileResult:
		res = CompileResult()

		address = res.register(env.get_symbol(node.identifier))
		if res.error: return res

		start_pos = len(self.instructions)
		start = res.register(self.visit(node.start, env))
		if res.error: return res
		if start in self.KNOWN_VALUES: self.truncate(start_pos)
		self.load_immediate(address, forced=True); self.comment(node.identifier)
		self.write("COMP D M" if start not in self.KNOWN_VALUES else f"COMP {start} M")

		for_jmp = self.make_jump()
		self.write(f".for{for_jmp}")
		self.tabs += 1

		res.register(self.visit(node.body, env))
		if res.error: return res

		step_pos = len(self.instructions)
		step = res.register(self.visit(node.step, env))
		if res.error: return res
		self.comment(f"Step value (.for{for_jmp})")

		# Optimizing step
		if node.step_op.token_type == TT.ADD:
			if step == 1:
				self.truncate(step_pos)
				self.load_immediate(address); self.comment(node.identifier)
				self.write("COMP M++ DM")
			elif step == -1:
				self.truncate(step_pos)
				self.load_immediate(address); self.comment(node.identifier)
				self.write("COMP M-- DM")
			else:
				self.write("COMP D+M DM")
		if node.step_op.token_type == TT.SUB:
			if step == 1:
				self.truncate(step_pos)
				self.load_immediate(address); self.comment(node.identifier)
				self.write("COMP M-- DM")
			elif step == -1:
				self.truncate(step_pos)
				self.load_immediate(address); self.comment(node.identifier)
				self.write("COMP M++ DM")
			else:
				self.write("COMP D+M DM")
		
		end = res.register(self.visit(node.end, env))
		if res.error: return res
		self.comment(f"End value (.for{for_jmp})")

		self.load_immediate(address); self.comment(node.identifier)
		self.write("COMP D-M D")

		self.load_immediate(f".for{for_jmp}")
		jump_type = ""
		match node.end_op.token_type:
			case TT.LT: jump_type = "JGT"
			case TT.LE: jump_type = "JGE"
			case TT.GT: jump_type = "JLT"
			case TT.GE: jump_type = "JLE"
		
		self.write(f"COMP D {jump_type}")
		self.tabs -= 1

		return res.success(None)

	def visitWhileLoop(self, node: WhileLoop, env: Environment) -> CompileResult:
		res = CompileResult()

		while_jmp = self.make_jump()
		self.write(f".while{while_jmp}")
		self.tabs += 1

		res.register(self.visit(node.condition, env))
		if res.error: return res
		self.load_immediate(f".endwhile{while_jmp}")
		self.write("COMP D JLE")

		res.register(self.visit(node.body, env))
		if res.error: return res

		self.load_immediate(f".while{while_jmp}")
		self.write("COMP 0 JMP")
		self.tabs -= 1
		self.write(f".endwhile{while_jmp}")
		return res.success(None)

	def visitIfStatement(self, node: IfStatement, env: Environment) -> CompileResult:
		res = CompileResult()

		end_jmp = self.make_jump()

		for condition, body in node.cases:
			res.register(self.visit(condition, env))
			if res.error: return res

			if_jmp = self.make_jump()
			self.load_immediate(f".if{if_jmp}")
			self.tabs += 1

			self.write("COMP D JEQ")
			res.register(self.visit(body, env))
			if res.error: return res
			self.load_immediate(f".endif{end_jmp}")
			self.write("COMP 0 JMP")

			self.tabs -= 1
			self.write(f".if{if_jmp}")

		if node.else_case:
			self.tabs += 1
			res.register(self.visit(node.else_case, env))
			if res.error: return res
			self.tabs -= 1
		
		self.write(f".endif{end_jmp}")
		return res.success(None)

	def visitArrayAccess(self, node: ArrayAccess, env: Environment):
		res = CompileResult()

		base_pos = len(self.instructions)
		base_pointer = res.register(self.visit(node.array, env))
		if res.error: return res

		if isinstance(node.array, Identifier):
			if node.array.symbol not in env.arrays:
				return res.fail(CompilationError(
					node.array.start_pos, node.array.end_pos,
					f"Undefined array: {node.array.symbol}", 7
				))

			self.truncate(base_pos)

		index_pos = len(self.instructions)
		index = res.register(self.visit(node.index, env))
		if res.error: return res

		# Error-checking
		if index is not None:
			if index < 0:
				return res.fail(CompilationError(
					node.index.start_pos, node.index.end_pos,
					"Out of bounds: index must be at least 0.", 9
				))
			if isinstance(node.array, ArrayLiteral):
				if index >= len(node.array.elements):
					return res.fail(CompilationError(
						node.index.start_pos, node.index.end_pos,
						f"Out of bounds: index must be less than {len(node.array.elements)}.", 9
					))
			else:
				address: int = env.arrays[node.array.symbol]
				if index >= address - base_pointer:
					return res.fail(CompilationError(
						node.index.start_pos, node.index.end_pos,
						f"Out of bounds: index must be less than {address - base_pointer}.", 9
					))

		if index == 0: self.truncate(index_pos)

		self.load_immediate(base_pointer, forced=True); self.comment("Base pointer")
		if index != 0: self.write("COMP D+A A")
		self.write("COMP M D")

		return res.success(None)

	def visitArraySet(self, node: ArraySet, env: Environment):
		res = CompileResult()

		base_pos = len(self.instructions)
		base_pointer = res.register(self.visit(node.array, env))
		if res.error: return res

		if isinstance(node.array, Identifier):
			if node.array.symbol not in env.arrays:
				return res.fail(CompilationError(
					node.array.start_pos, node.array.end_pos,
					f"Undefined array: {node.array.symbol}", 7
				))

			self.truncate(base_pos)

		index_pos = len(self.instructions)
		index = res.register(self.visit(node.index, env))
		if res.error: return res

		# Error-checking... again
		if index is not None:
			if index < 0:
				return res.fail(CompilationError(
					node.index.start_pos, node.index.end_pos,
					"Out of bounds: index must be at least 0.", 9
				))
			if isinstance(node.array, ArrayLiteral):
				if index >= len(node.array.elements):
					return res.fail(CompilationError(
						node.index.start_pos, node.index.end_pos,
						f"Out of bounds: index must be less than {len(node.array.elements)}.", 9
					))
			else:
				address: int = env.arrays[node.array.symbol]
				if index >= address - base_pointer:
					return res.fail(CompilationError(
						node.index.start_pos, node.index.end_pos,
						f"Out of bounds: index must be less than {address - base_pointer}.", 9
					))
				
		if index == 0: self.truncate(index_pos)

		self.load_immediate(base_pointer, forced=True); self.comment("Base pointer")
		if index != 0: self.write("COMP D+A D")
		pointer_reg = res.register(self.allocate(node.index))
		if res.error: return res

		self.load_immediate(pointer_reg)
		self.write("COMP D M")

		res.register(self.visit(node.value, env))
		if res.error: return res

		self.load_immediate(pointer_reg, forced=True)
		self.write("COMP M A")
		self.write("COMP D M")
		return res.success(None)
	
	def visitSubroutineDef(self, node: SubroutineDef, env: Environment):
		res = CompileResult()

		for param in node.parameters:
			location = env.assign_address
			res.register(env.define_symbol(param, location, "var"))
			if res.error: return res
		
		self.visitIntLiteral(IntLiteral(len(node.parameters), None, None), env)
		self.comment(f"{len(node.parameters)} params")

		location = env.assign_address
		res.register(env.define_symbol(node.name, (location, len(node.parameters)), "sub"))
		if res.error: return res

		self.load_immediate(location, forced=True)
		self.write("COMP D M")

		return res.success(None)

	def visitCallExpression(self, node: CallExpression, env: Environment):
		res = CompileResult()
		symb = node.sub_name.symbol

		address = res.register(env.get_symbol(node.sub_name))
		if res.error: return res

		if (symb not in env.subroutines) and (symb not in env.native_subs):
			return res.fail(CompilationError(
				node.start_pos, node.end_pos,
				f"Symbol {symb} is not a subroutine.", 10
			))
		
		args = env.subroutines[symb] if symb in env.subroutines else env.native_subs[symb]
		if args != len(node.arguments):
			return res.fail(CompilationError(
				node.start_pos, node.end_pos,
				f"Expected {args} arguments, got {len(node.arguments)} arguments instead.", 11
			))
		
		if symb in env.subroutines:
			# Populate arguments
			for i, arg in enumerate(node.arguments):
				res.register(self.visit(arg, env))
				if res.error: return res

				self.load_immediate(address - args + i)
				self.comment(f"arg_{i}")
				self.write("COMP D M")
			
			self.write(f"CALL .sub_{symb}")
		else:
			match symb:
				case "update": self.write("BUFR update")
				case "flip": self.write("BUFR move")
				case "halt": self.write("HALT")
				case "plot":
					pos = len(self.instructions)
					x = res.register(self.visit(node.arguments[0], env))
					if res.error: return res
					self.load_immediate(self.X_ADDR)
					self.comment("X Port")
					if x in self.KNOWN_VALUES: self.truncate(pos); self.write(f"COMP {x} M")
					else: self.write("COMP D M")

					y = res.register(self.visit(node.arguments[1], env))
					if res.error: return res
					self.load_immediate(self.Y_ADDR)
					self.comment("Y Port")
					if y in self.KNOWN_VALUES: self.truncate(pos); self.write(f"COMP {y} M")
					else: self.write("COMP D M")

					val = res.register(self.visit(node.arguments[2], env))
					if res.error: return res
					if val not in (0, 1):
						return res.fail(CompilationError(
							node.arguments[2].start_pos, node.arguments[2].end_pos,
							f"Expected 0 or 1.", 5
						))
					self.write(f"PLOT {val}")
					
		return res.success(None)
