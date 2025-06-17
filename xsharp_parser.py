from xsharp_helper import InvalidSyntax, Position
from xsharp_lexer import TT, Token, DATA_TYPES
from typing import Any

## NODES
class Statements:
	def __init__(self, start_pos: Position, end_pos: Position, body: list):
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.body = body

	def __repr__(self):
		res: str = "[\n"
		for line in self.body:
			res += "  " + repr(line) + "\n"
		return res + "]"

class IntLiteral:
	def __init__(self, value: int, start_pos: Position, end_pos: Position):
		self.value = value
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.in_parentheses = False
	
	def __repr__(self):
		return f"Literal[{self.value}]"

class ArrayLiteral:
	def __init__(self, elements: list, start_pos: Position, end_pos: Position):
		self.elements = elements
		self.start_pos = start_pos
		self.end_pos = end_pos
	
	def __repr__(self):
		return "Array[" + ", ".join([f"{element}" for element in self.elements]) + "]"

class Identifier:
	def __init__(self, symbol: str, start_pos: Position, end_pos: Position):
		self.symbol = symbol
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.in_parentheses = False
	
	def __repr__(self):
		return f"Identifier[{self.symbol}]"

class BinaryOperation:
	def __init__(self, left, op: Token, right):
		self.left = left
		self.op = op
		self.right = right
		self.in_parentheses = False

		self.start_pos = left.start_pos
		self.end_pos = right.end_pos
	
	def __repr__(self):
		return f"({self.left}, {self.op}, {self.right})"

class UnaryOperation:
	def __init__(self, op: Token, value):
		self.op = op
		self.value = value
		self.in_parentheses = False

		self.start_pos = op.start_pos
		self.end_pos = value.end_pos
	
	def __repr__(self):
		return f"({self.op}, {self.value})"

class ConstDefinition:
	def __init__(self, symbol: Identifier, value: IntLiteral, start_pos: Position, end_pos: Position):
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.symbol = symbol
		self.value = value
	
	def __repr__(self):
		return f"ConstDef[{self.symbol} -> {self.value}]"

class VarDeclaration:
	def __init__(self, identifier: str, value, data_type: str, start_pos: Position, end_pos: Position, length: int|str|None):
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.identifier = identifier
		self.value = value
		self.data_type = data_type
		self.length = length

	def __repr__(self):
		return f"VarDeclaration[{self.identifier}] -> {self.value}"

class Assignment:
	def __init__(self, identifier: Identifier, expr, start_pos: Position, end_pos: Position):
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.identifier = identifier
		self.expr = expr

class ForLoop:
	def __init__(self, start_pos: Position, end_pos: Position, identifier: str, start: Any, end: Any, step: Any, body: Statements):
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.identifier = identifier
		self.start = start
		self.end = end
		self.step = step
		self.body = body

class CForLoop:
	def __init__(self, start_pos: Position, end_pos: Position, identifier: str, start: Any, end_op: Token, end: Any, step_op: Token, step: Any, body: Statements):
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.identifier = identifier
		self.start = start
		self.end = end
		self.end_op = end_op
		self.step = step
		self.step_op = step_op
		self.body = body

class WhileLoop:
	def __init__(self, start_pos: Position, end_pos: Position, condition, body: Statements):
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.condition = condition
		self.body = body

class PlotExpr:
	def __init__(self, x, y, value: int, start_pos: Position, end_pos: Position):
		self.x = x
		self.y = y
		self.value = value
		self.start_pos = start_pos
		self.end_pos = end_pos

class ArrayAccess:
	def __init__(self, array: ArrayLiteral|Identifier, index, end_pos: Position):
		self.array = array
		self.index = index
		self.start_pos = array.start_pos
		self.end_pos = end_pos

class ArraySet:
	def __init__(self, array: ArrayLiteral|Identifier, index, value):
		self.array = array
		self.index = index
		self.value = value
		self.start_pos = array.start_pos
		self.end_pos = value.end_pos

class IfStatement:
	def __init__(self, cases: list[tuple[Any, Statements]], else_case: Statements|None, start_pos: Position, end_pos: Position):
		self.cases = cases
		self.else_case = else_case
		self.start_pos = start_pos
		self.end_pos = end_pos

class SubroutineDef:
	def __init__(self, start_pos: Position, end_pos: Position, name: str, parameters: list[str], body: Statements):
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.name = name
		self.parameters = parameters
		self.body = body

class CallExpression:
	def __init__(self, start_pos: Position, end_pos: Position, sub_name: str, arguments: list):
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.sub_name = sub_name
		self.arguments = arguments

## PARSE RESULT
class ParseResult:
	def __init__(self):
		self.node, self.error = None, None
	
	def register(self, res):
		if isinstance(res, ParseResult):
			self.error = res.error
		return res.node
	
	def success(self, node):
		self.node = node
		return self
	
	def fail(self, error):
		self.error = error
		return self

	def __str__(self):
		return f"{self.node}"

## PARSER
class Parser:
	def __init__(self, tokens: list[Token]):
		self.tokens = tokens
		self.current_token = None
		self.token_index = -1
		self.advance()

	def advance(self):
		self.token_index += 1
		if self.token_index < len(self.tokens):
			self.current_token = self.tokens[self.token_index]

	def parse(self):
		res = ParseResult()

		ast = res.register(self.statements())
		if res.error: return res

		if self.current_token.token_type != TT.EOF:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected an operator."
			))

		return res.success(ast)

	def statements(self, end=(TT.EOF, )):
		res = ParseResult()
		body = []
		more_statements = True

		while more_statements:
			while self.current_token.token_type == TT.NEWLINE: self.advance()
			start_pos = self.current_token.start_pos

			if self.current_token.token_type in end:
				end_pos = self.current_token.end_pos
				more_statements = False
				break

			stmt = res.register(self.statement())
			if res.error: return res

			body.append(stmt)

			if self.current_token.token_type in end:
				end_pos = self.current_token.end_pos
				more_statements = False
		
		return res.success(Statements(start_pos, end_pos, body))

	def statement(self):
		if self.current_token.token_type == TT.KEYWORD:
			match self.current_token.value:
				case "const": return self.const_definition()
				case "var": return self.var_declaration()
				case "for": return self.for_loop()
				case "while": return self.while_loop()
				case "if": return self.if_statement()
				case "sub": return self.subroutine_def()

		return self.expression()

	def const_definition(self):
		res = ParseResult()
		start_pos = self.current_token.start_pos
		self.advance()

		identifier = res.register(self.literal())
		if res.error: return res

		if not isinstance(identifier, Identifier):
			return res.fail(InvalidSyntax(
				identifier.start_pos, identifier.end_pos,
				"Expected an identifier after 'define' keyword."
			))
		
		value = res.register(self.expression())
		end_pos = self.current_token.end_pos
		if res.error: return res
		
		return res.success(ConstDefinition(identifier, value, start_pos, end_pos))

	def var_declaration(self):
		res = ParseResult()
		start_pos = self.current_token.start_pos
		length: int|None = None
		self.advance()

		if self.current_token.token_type != TT.IDENTIFIER:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected an identifier after 'var' keyword."
			))
		identifier = self.current_token.value
		self.advance()

		if self.current_token.token_type != TT.COL:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected ':' after variable."
			))
		self.advance()

		if not (self.current_token.token_type == TT.KEYWORD and self.current_token.value in DATA_TYPES):
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				f"Expected {', '.join(DATA_TYPES)} after ':'."
			))
		data_type = self.current_token.value
		self.advance()

		if self.current_token.token_type == TT.LSQ: # Array
			self.advance()
			
			if self.current_token.token_type not in (TT.NUM, TT.IDENTIFIER):
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected a number or constant for the array length."
				))
			length = self.current_token.value
			self.advance()

			if self.current_token.token_type != TT.RSQ:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected ']' after array length."
				))
			self.advance()

		expr = None
		if self.current_token.token_type != TT.ASSIGN:
			end_pos = self.current_token.end_pos
			if self.current_token.token_type not in (TT.NEWLINE, TT.EOF):
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected '=', a nwewline, or EOF after ':'."
				))
		else:
			self.advance()

			expr = res.register(self.expression())
			if res.error: return res
			end_pos = self.current_token.end_pos

			if self.current_token.token_type not in (TT.NEWLINE, TT.EOF):
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected a newline or EOF after variable declaration."
				))
			
		return res.success(VarDeclaration(identifier, expr, data_type, start_pos, end_pos, length))

	def for_loop(self):
		res = ParseResult()
		start_pos = self.current_token.start_pos
		self.advance()

		if self.current_token.token_type == TT.IDENTIFIER:
			identifier = self.current_token.value
			self.advance()

			if self.current_token != Token(None, None, TT.KEYWORD, "start"):
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected 'start' keyword after iterator."
				))
			self.advance()
			if self.current_token.token_type != TT.COL:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected ':' after 'start' keyword."
				))
			self.advance()
			start = res.register(self.comparison())
			if res.error: return res

			if self.current_token != Token(None, None, TT.KEYWORD, "end"):
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected 'end' keyword after start value."
				))
			self.advance()
			if self.current_token.token_type != TT.COL:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected ':' after 'end' keyword."
				))
			self.advance()
			end = res.register(self.comparison())
			if res.error: return res

			if self.current_token != Token(None, None, TT.KEYWORD, "step"):
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected 'step' keyword after iterator."
				))
			self.advance()
			if self.current_token.token_type != TT.COL:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected ':' after 'step' keyword."
				))
			self.advance()
			step = res.register(self.comparison())
			if res.error: return res

			if self.current_token.token_type != TT.LBR:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected '{' before for loop body."
				))
			self.advance()

			body = res.register(self.statements(end=(TT.EOF, TT.RBR)))
			if res.error: return res

			if self.current_token.token_type != TT.RBR:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected '}' after for loop body."
				))
			end_pos = self.current_token.end_pos
			self.advance()

			return res.success(ForLoop(start_pos, end_pos, identifier, start, end, step, body))
		elif self.current_token.token_type == TT.LPR:
			self.advance()
			if self.current_token.token_type != TT.IDENTIFIER:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected an identifier after '(' (after 'for' keyword)."
				))
			identifier = self.current_token.value
			self.advance()

			if self.current_token.token_type != TT.ASSIGN:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected '=' after iterator."
				))
			self.advance()

			start = res.register(self.comparison())
			if res.error: return res

			if self.current_token != Token(None, None, TT.NEWLINE, ";"):
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected ';' after start value."
				))
			self.advance()

			if self.current_token != Token(None, None, TT.IDENTIFIER, identifier):
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					f"Expected '{identifier}'."
				))
			self.advance()

			if self.current_token.token_type not in (TT.LT, TT.LE, TT.GT, TT.GE):
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected '<', '>', '<=', or '>='."
				))
			end_op = self.current_token
			self.advance()

			end = res.register(self.comparison())
			if res.error: return res

			if self.current_token != Token(None, None, TT.NEWLINE, ";"):
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected ';' after start value."
				))
			self.advance()

			if self.current_token != Token(None, None, TT.IDENTIFIER, identifier):
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					f"Expected '{identifier}'."
				))
			self.advance()

			if self.current_token.token_type not in (TT.ADD, TT.SUB):
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected '+' or '-'."
				))
			step_op = self.current_token
			self.advance()
			if self.current_token.token_type != TT.ASSIGN:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected '='."
				))
			self.advance()

			step = res.register(self.comparison())
			if res.error: return res

			if self.current_token.token_type != TT.RPR:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected '}' after step value."
				))
			self.advance()

			if self.current_token.token_type != TT.LBR:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected '{' before for loop body."
				))
			self.advance()

			body = res.register(self.statements(end=(TT.EOF, TT.RBR)))
			if res.error: return res

			if self.current_token.token_type != TT.RBR:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected '}' after for loop body."
				))
			end_pos = self.current_token.end_pos
			self.advance()

			return res.success(CForLoop(start_pos, end_pos, identifier, start, end_op, end, step_op, step, body))
		else:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected an identifier or '(' after 'for' keyword."
			))

	def while_loop(self):
		res = ParseResult()
		start_pos = self.current_token.start_pos
		self.advance()

		condition = res.register(self.expression())
		if res.error: return res

		if self.current_token.token_type != TT.LBR:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected '{' before while loop body."
			))
		self.advance()

		body = res.register(self.statements(end=(TT.EOF, TT.RBR)))
		if res.error: return res

		if self.current_token.token_type != TT.RBR:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected '}' after while loop body."
			))
		end_pos = self.current_token.end_pos
		self.advance()

		return res.success(WhileLoop(start_pos, end_pos, condition, body))

	def if_statement(self):
		res = ParseResult()
		start_pos: Position = self.current_token.start_pos
		self.advance()
		cases: list[tuple[Any, Statements]] = []
		else_case: Any|None = None

		condition = res.register(self.expression())
		if res.error: return res

		if self.current_token.token_type != TT.LBR:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected '{' after condition."
			))
		self.advance()

		body = res.register(self.statements((TT.EOF, TT.RBR)))
		if res.error: return res

		if self.current_token.token_type != TT.RBR:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected '}' after if body."
			))
		end_pos = self.current_token.end_pos
		self.advance()
		cases.append((condition, body))
		while self.current_token.token_type == TT.NEWLINE: self.advance()

		while self.current_token == Token(None, None, TT.KEYWORD, "elseif"):
			self.advance()
			condition = res.register(self.expression())
			if res.error: return res

			if self.current_token.token_type != TT.LBR:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected '{' after condition."
				))
			self.advance()
			body = res.register(self.statements((TT.EOF, TT.RBR)))
			if res.error: return res

			if self.current_token.token_type != TT.RBR:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected '}' after elseif body."
				))
			end_pos = self.current_token.end_pos
			self.advance()
			cases.append((condition, body))
			while self.current_token.token_type == TT.NEWLINE: self.advance()
		
		if self.current_token == Token(None, None, TT.KEYWORD, "else"):
			self.advance()
			if self.current_token.token_type != TT.LBR:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected '{' after 'else' keyword."
				))
			self.advance()
			body = res.register(self.statements((TT.EOF, TT.RBR)))
			if res.error: return res

			if self.current_token.token_type != TT.RBR:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected '}' after else body."
				))
			end_pos = self.current_token.end_pos
			self.advance()
			else_case = body
		
		return res.success(IfStatement(cases, else_case, start_pos, end_pos))

	def subroutine_def(self):
		res = ParseResult()
		start_pos: Position = self.current_token.start_pos
		self.advance()
		
		if self.current_token.token_type != TT.IDENTIFIER:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected a subroutine name."
			))
		name: str = self.current_token.value
		self.advance()

		if self.current_token.token_type != TT.LPR:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected '(' after subroutine name."
			))
		self.advance()

		parameters: list[str] = []

		if self.current_token.token_type == TT.IDENTIFIER:
			parameters.append(self.current_token.value)
			self.advance()

			while self.current_token.token_type == TT.COMMA:
				self.advance()
				if self.current_token.token_type != TT.IDENTIFIER:
					return res.fail(InvalidSyntax(
						self.current_token.start_pos, self.current_token.end_pos,
						"Expected a parameter name."
					))
				parameters.append(self.current_token.value)
				self.advance()
		
		if self.current_token.token_type != TT.RPR:
			supplement: str = "',' or "
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				f"Expected {supplement if parameters else ''}')'."
			))
		self.advance()

		if self.current_token.token_type != TT.LBR:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected '{' after subroutine definition."
			))
		self.advance()

		body = res.register(self.statements((TT.EOF, TT.RBR)))
		if res.error: return res

		if self.current_token.token_type != TT.RBR:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected '}' after subroutine body."
			))
		end_pos: Position = self.current_token.end_pos
		self.advance()

		return res.success(SubroutineDef(start_pos, end_pos, name, parameters, body))

	def expression(self):
		return self.assignment()

	def assignment(self):
		res = ParseResult()
		start_pos = self.current_token.start_pos
		value = res.register(self.comparison())
		if res.error: return res

		if self.current_token.token_type == TT.ASSIGN: # Assignment -> var = value
			self.advance()
			if not isinstance(value, Identifier):
				return res.fail(InvalidSyntax(
					value.start_pos, value.end_pos,
					"Expected an identifier before '='."
				))
			expr = res.register(self.expression())
			end_pos = self.current_token.end_pos
			if res.error: return res

			return res.success(Assignment(value, expr, start_pos, end_pos))

		return res.success(value)

	def binary_op(self, func, token_types: tuple[TT]):
		res = ParseResult()

		left = res.register(func())
		if res.error: return res

		while self.current_token.token_type in token_types:
			op = self.current_token
			self.advance()

			right = res.register(func())
			if res.error: return res

			left = BinaryOperation(left, op, right)
		
		return res.success(left)

	def comparison(self):
		return self.binary_op(self.bitwise, (TT.LT, TT.LE, TT.EQ, TT.NE, TT.GT, TT.GE))

	def bitwise(self):
		return self.binary_op(self.additive, (TT.AND, TT.OR, TT.XOR, TT.RSHIFT, TT.LSHIFT))

	def additive(self):
		return self.binary_op(self.multiplicative, (TT.ADD, TT.SUB))

	def multiplicative(self):
		return self.binary_op(self.unary, (TT.MUL, TT.DIV))

	def unary(self):
		res = ParseResult()

		if self.current_token.token_type in (TT.ADD, TT.SUB, TT.NOT, TT.AT, TT.ABS, TT.SIGN):
			tok = self.current_token
			self.advance()
			value = res.register(self.unary())
			if res.error: return res

			if tok.token_type == TT.AT and not isinstance(value, Identifier): # Address operator
				return res.fail(InvalidSyntax(
					tok.start_pos, tok.end_pos,
					"Expected an identifier after '@'."
				))

			return res.success(UnaryOperation(tok, value))
		
		value = res.register(self.access())
		if res.error: return res

		if self.current_token.token_type in (TT.INC, TT.DEC):
			tok = self.current_token
			self.advance()
			return res.success(UnaryOperation(tok, value))
		
		return res.success(value)

	def access(self):
		res = ParseResult()

		literal = res.register(self.call())
		if res.error: return res

		if self.current_token.token_type == TT.LSQ:
			if not isinstance(literal, (ArrayLiteral, Identifier)):
				return res.fail(InvalidSyntax(
					literal.start_pos, literal.end_pos,
					"Expected an array literal or identifier."
				))

			self.advance()
			index = res.register(self.comparison())
			if res.error: return res

			if self.current_token.token_type != TT.RSQ:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected ']' after index."
				))
			end_pos = self.current_token.end_pos
			self.advance()

			if self.current_token.token_type == TT.ASSIGN:
				self.advance()
				expr = res.register(self.comparison())
				if res.error: return res

				return res.success(ArraySet(literal, index, expr))

			return res.success(ArrayAccess(literal, index, end_pos))

		return res.success(literal)

	def call(self):
		res = ParseResult()

		literal = res.register(self.literal())
		if res.error: return res

		if self.current_token.token_type == TT.LPR:
			self.advance()

			arguments: list = []
			if self.current_token.token_type != TT.RPR:
				arg = res.register(self.expression())
				if res.error: return res

				arguments.append(arg)

				while self.current_token.token_type == TT.COMMA:
					self.advance()
					arg = res.register(self.expression())
					if res.error: return res

					arguments.append(arg)
				
			if self.current_token.token_type != TT.RPR:
				supplement: str = "',' or "
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					f"Expected {supplement if arguments else ''} ')'."
				))
			end_pos: Position = self.current_token.end_pos
			self.advance()

			return res.success(CallExpression(
				literal.start_pos, end_pos, literal.symbol, arguments
			))

		return res.success(literal)

	def literal(self):
		res = ParseResult()
		tok = self.current_token
		self.advance()

		if tok.token_type == TT.NUM:
			return res.success(IntLiteral(tok.value, tok.start_pos, tok.end_pos))
		
		if tok.token_type == TT.IDENTIFIER:
			return res.success(Identifier(tok.value, tok.start_pos, tok.end_pos))
		
		if tok.token_type == TT.LPR:
			expr = res.register(self.expression())
			if res.error: return res

			if self.current_token.token_type != TT.RPR:
				return res.fail(InvalidSyntax(self.current_token.start_pos, self.current_token.end_pos, "Expected a matching right parenthesis."))
			self.advance()

			expr.in_parentheses = True
			return res.success(expr)

		if tok.token_type == TT.LSQ:
			elements = []
			
			# First element
			expr = res.register(self.comparison())
			if res.error: return res
			elements.append(expr)

			while self.current_token.token_type == TT.COMMA:
				self.advance()
				expr = res.register(self.comparison())
				if res.error: return res
				elements.append(expr)
			
			if self.current_token.token_type != TT.RSQ:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected ',' or '}' after array elements."
				))
			end_token = self.current_token

			self.advance()
			return res.success(ArrayLiteral(elements, tok.start_pos, end_token.end_pos))

		return res.fail(InvalidSyntax(tok.start_pos, tok.end_pos, f"Expected a number, an identifier, '(' or '[', found token '{tok.token_type}' instead."))
