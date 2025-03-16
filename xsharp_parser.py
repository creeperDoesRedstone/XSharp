from xsharp_helper import InvalidSyntax, Position
from xsharp_lexer import TT, Token, DATA_TYPES

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
	def __init__(self, identifier: str, value, data_type: str, start_pos: Position, end_pos: Position, length: int|None):
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
	def __init__(self, start_pos: Position, end_pos: Position, identifier: str, start: int, end: int, step: int, body: Statements):
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.identifier = identifier
		self.start = start
		self.end = end
		self.step = step
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
				case "plot": return self.plot_expr()

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
			
			if self.current_token.token_type != TT.NUM:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected a number for the array length."
				))
			length = self.current_token.value
			self.advance()

			if self.current_token.token_type != TT.RSQ:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected ']' after array length."
				))
			self.advance()

		if self.current_token.token_type != TT.ASSIGN:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected '=' after ':'."
			))
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

		if self.current_token.token_type != TT.IDENTIFIER:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected an identifier after 'for' keyword."
			))
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
		if self.current_token.token_type != TT.NUM:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected a start value."
			))
		start = self.current_token.value
		self.advance()

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
		if self.current_token.token_type != TT.NUM:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected an end value."
			))
		end = self.current_token.value
		self.advance()

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
		if self.current_token.token_type not in (TT.NUM, TT.SUB):
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected a step value."
			))
		negative = self.current_token.token_type == TT.SUB
		if negative:
			self.advance()
			if self.current_token.token_type != TT.NUM:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected a step value."
				))

		step = self.current_token.value * (-1)**negative
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

		return res.success(ForLoop(start_pos, end_pos, identifier, start, end, step, body))

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

	def plot_expr(self):
		res = ParseResult()
		start_pos = self.current_token.start_pos
		self.advance()
		
		x = res.register(self.expression())
		if res.error: return res

		y = res.register(self.expression())
		if res.error: return res

		if self.current_token.token_type != TT.NUM:
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected an integer for plot value."
			))
		if self.current_token.value not in (0, 1):
			return res.fail(InvalidSyntax(
				self.current_token.start_pos, self.current_token.end_pos,
				"Expected 0 or 1 for plot value."
			))
		value = self.current_token.value
		end_pos = self.current_token.end_pos
		self.advance()

		return res.success(PlotExpr(x, y, value, start_pos, end_pos))

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
		return self.binary_op(self.unary, (TT.MUL,))

	def unary(self):
		res = ParseResult()

		if self.current_token.token_type in (TT.ADD, TT.SUB, TT.NOT, TT.AND):
			tok = self.current_token
			self.advance()
			value = res.register(self.unary())
			if res.error: return res

			if tok.token_type == TT.AND and not isinstance(value, Identifier): # Address operator
				return res.fail(InvalidSyntax(
					tok.start_pos, tok.end_pos,
					"Expected an identifier after '&'."
				))

			return res.success(UnaryOperation(tok, value))
		
		value = res.register(self.call_access())
		if res.error: return res

		if self.current_token.token_type in (TT.INC, TT.DEC):
			tok = self.current_token
			self.advance()
			return res.success(UnaryOperation(tok, value))
		
		return res.success(value)

	def call_access(self):
		res = ParseResult()

		literal = res.register(self.literal())
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

		if tok.token_type == TT.LBR:
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
			
			if self.current_token.token_type != TT.RBR:
				return res.fail(InvalidSyntax(
					self.current_token.start_pos, self.current_token.end_pos,
					"Expected ',' or '}' after array elements."
				))
			end_token = self.current_token

			self.advance()
			return res.success(ArrayLiteral(elements, tok.start_pos, end_token.end_pos))

		LBR = "{"
		return res.fail(InvalidSyntax(tok.start_pos, tok.end_pos, f"Expected a number, an identifier, '(' or '{LBR}', found token '{tok.token_type}' instead."))
