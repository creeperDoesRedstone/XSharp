from enum import Enum
import string

## TOKENS AND POSITION
class TT(Enum):
	ADD, SUB, INC, DEC,\
	AND, OR, NOT, XOR,\
	LPR, RPR, \
	NUM, IDENTIFIER, KEYWORD, NEWLINE, EOF\
	= range(15)

	def __str__(self):
		return super().__str__().removeprefix("TT.")

class Position:
	def __init__(self, index: int, line: int, col: int, fn: str, ftxt: str):
		self.index = index
		self.line = line
		self.col = col
		self.fn = fn
		self.ftxt = ftxt
	
	def advance(self, current_char: str):
		self.index += 1
		self.col += 1

		if current_char == "\n":
			self.line += 1
			self.col = 0
		
		return self

	def copy(self):
		return Position(self.index, self.line, self.col, self.fn, self.ftxt)

class Token:
	def __init__(self, start_pos: Position, end_pos: Position, token_type: TT, value: str|int|None = None):
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.token_type = token_type
		self.value = value
	
	def __repr__(self):
		if self.value: return f"{self.token_type}:{self.value}"
		return f"{self.token_type}"

KEYWORDS = [
	"define", "var"
]

## ERRORS
class Error:
	def __init__(self, start_pos: Position, end_pos: Position, error_name: str, details: str):
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.error_name = error_name
		self.details = details

	def __repr__(self):
		return f"File {self.start_pos.fn}, line {self.start_pos.line + 1}:\n{self.error_name}: {self.details}"

class UnexpectedCharacter(Error):
	def __init__(self, start_pos: Position, end_pos: Position, details: str):
		super().__init__(start_pos, end_pos, "Unexpected Character", details)

class InvalidSyntax(Error):
	def __init__(self, start_pos: Position, end_pos: Position, details: str):
		super().__init__(start_pos, end_pos, "Invalid Syntax", details)

class CompilationError(Error):
	def __init__(self, start_pos: Position, end_pos: Position, details: str):
		super().__init__(start_pos, end_pos, "Compilation Error", details)

## LEXER
class Lexer:
	def __init__(self, fn: str, ftxt: str):
		self.fn = fn
		self.ftxt = ftxt
		self.pos = Position(-1, 0, -1, fn, ftxt)
		self.current_char = None
		self.advance()
	
	def advance(self):
		self.pos.advance(self.current_char)
		self.current_char = None if self.pos.index >= len(self.ftxt) else self.ftxt[self.pos.index]
	
	def lex(self):
		tokens: list[Token] = []

		while self.current_char is not None:

			if self.current_char in " \t": self.advance()
			
			elif self.current_char in "\n\r;":
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.NEWLINE))
			
			elif self.current_char == "&":
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.AND))
			
			elif self.current_char == "|":
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.OR))
			
			elif self.current_char == "~":
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.NOT))
			
			elif self.current_char == "^":
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.XOR))
			
			elif self.current_char == "+":
				start_pos = self.pos.copy()
				self.advance()
				if self.current_char == "+":
					self.advance()
					tokens.append(Token(start_pos, self.pos, TT.INC))
				else: tokens.append(Token(start_pos, self.pos, TT.ADD))
			
			elif self.current_char == "-":
				start_pos = self.pos.copy()
				self.advance()
				if self.current_char == "-":
					self.advance()
					tokens.append(Token(start_pos, self.pos, TT.DEC))
				else: tokens.append(Token(start_pos, self.pos, TT.SUB))
			
			elif self.current_char in string.digits:
				start_pos = self.pos.copy()
				num_str = ""
				while self.current_char is not None and self.current_char in string.digits:
					num_str += self.current_char
					self.advance()
				tokens.append(Token(start_pos, self.pos, TT.NUM, int(num_str)))
			
			elif self.current_char in string.ascii_letters or self.current_char == "_":
				start_pos = self.pos.copy()
				identifier = ""
				while self.current_char is not None and (self.current_char in string.ascii_letters + string.digits or self.current_char == "_"):
					identifier += self.current_char
					self.advance()
				tokens.append(Token(start_pos, self.pos, TT.KEYWORD if identifier in KEYWORDS else TT.IDENTIFIER, identifier))
			
			elif self.current_char == "/":
				start_pos = self.pos.copy()
				self.advance()
				if self.current_char != "/":
					return None, UnexpectedCharacter(start_pos, self.pos, "'/'")
				self.advance()
				while self.current_char is not None and self.current_char not in "\n\r":
					self.advance()
			
			else:
				start_pos = self.pos.copy()
				char = self.current_char
				self.advance()
				return None, UnexpectedCharacter(start_pos, self.pos, f"'{char}'")
		
		tokens.append(Token(self.pos, self.pos, TT.EOF))
		return tokens, None

## NODES
class IntLiteral:
	def __init__(self, value: int, start_pos: Position, end_pos: Position):
		self.value = value
		self.start_pos = start_pos
		self.end_pos = end_pos
	
	def __repr__(self):
		return f"Literal[{self.value}]"
	
class Identifier:
	def __init__(self, symbol: str, start_pos: Position, end_pos: Position):
		self.symbol = symbol
		self.start_pos = start_pos
		self.end_pos = end_pos
	
	def __repr__(self):
		return f"Identifier[{self.symbol}]"

class BinaryOperation:
	def __init__(self, left, op: Token, right):
		self.left = left
		self.op = op
		self.right = right
	
	def __repr__(self):
		return f"({self.left}, {self.op}, {self.right})"

class UnaryOperation:
	def __init__(self, op: Token, value):
		self.op = op
		self.value = value
	
	def __repr__(self):
		return f"({self.op}, {self.value})"

class ConstDefinition:
	def __init__(self, symbol: Identifier, value: IntLiteral):
		self.symbol = symbol
		self.value = value
	
	def __repr__(self):
		return f"ConstDef[{self.symbol} -> {self.value}]"

class Statements:
	def __init__(self, body: list):
		self.body = body

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
	
	def statements(self):
		res = ParseResult()
		body = []
		more_statements = True

		while more_statements:
			while self.current_token.token_type == TT.NEWLINE: self.advance()

			stmt = res.register(self.statement())
			if res.error: return res

			body.append(stmt)

			if self.current_token.token_type == TT.EOF:
				more_statements = False
		
		return res.success(Statements(body))

	def statement(self):
		if self.current_token.token_type == TT.KEYWORD:
			match self.current_token.value:
				case "define": return self.const_definition()

		return self.expression()

	def const_definition(self):
		res = ParseResult()
		self.advance()

		identifier = res.register(self.literal())
		if res.error: return res

		if not isinstance(identifier, Identifier):
			return res.fail(InvalidSyntax(
				identifier.start_pos, identifier.end_pos,
				"Expected an identifier after 'define' keyword."
			))
		
		value = res.register(self.literal())
		if res.error: return res

		if not isinstance(value, IntLiteral):
			return res.fail(InvalidSyntax(
				value.start_pos, value.end_pos,
				"Expected an identifier after 'define' keyword."
			))
		
		return res.success(ConstDefinition(identifier, value))

	def expression(self):
		return self.logical()

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
	
	def logical(self):
		return self.binary_op(self.additive, (TT.AND, TT.OR, TT.XOR))
	
	def additive(self):
		return self.binary_op(self.unary, (TT.ADD, TT.SUB))
	
	def unary(self):
		res = ParseResult()

		if self.current_token.token_type in (TT.ADD, TT.SUB, TT.NOT):
			tok = self.current_token
			self.advance()
			value = res.register(self.unary())
			if res.error: return res
			return res.success(UnaryOperation(tok, value))
		
		value = res.register(self.literal())
		if res.error: return res

		if self.current_token.token_type in (TT.INC, TT.DEC):
			tok = self.current_token
			self.advance()
			return res.success(UnaryOperation(tok, value))
		
		return res.success(value)
	
	def literal(self):
		res = ParseResult()
		tok = self.current_token
		self.advance()

		if tok.token_type == TT.NUM:
			return res.success(IntLiteral(tok.value, tok.start_pos, tok.end_pos))
		
		if tok.token_type == TT.IDENTIFIER:
			return res.success(Identifier(tok.value, tok.start_pos, tok.end_pos))
		
		return res.fail(InvalidSyntax(tok.start_pos, tok.end_pos, f"Expected a number or an identifier, found token '{tok.token_type}' instead."))

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
		self.constants: dict[str, int] = {}

	def visit(self, node, hierachy: int) -> CompileResult:
		method_name = f"visit_{type(node).__name__}"
		method = getattr(self, method_name, self.no_visit_method)
		return method(node, hierachy)
	
	def no_visit_method(self, node, hierachy: int):
		raise Exception(f"No visit_{type(node).__name__}() method defined.")
	
	def visit_Statements(self, node: Statements, hierachy: int):
		res = CompileResult()
		result: list[str] = []

		for line in node.body:
			line_res = res.register(self.visit(line, 1))
			if res.error: return res

			result += line_res
		
		if result[-1].startswith("LDIA "): result += ["COMP A D"]
		return res.success(result + ["LDIA 0", "COMP D M"])

	def visit_IntLiteral(self, node: IntLiteral, hierachy: int):
		res = CompileResult()
		if node.value >= 2**15:
			return res.fail(CompilationError(
				node.start_pos, node.end_pos,
				f"Cannot parse integer literal {node.value}"
			))
		return res.success([f"LDIA {node.value}"])
	
	def visit_BinaryOperation(self, node: BinaryOperation, hierachy: int):
		res = CompileResult()

		left: list[str] = res.register(self.visit(node.left, hierachy + 1))
		if res.error: return res

		result = left + ["COMP A D"]

		right: list[str] = res.register(self.visit(node.right, hierachy + 1))
		if res.error: return res

		if node.op.token_type == TT.ADD:
			computation = "COMP D+A D"
		
		if node.op.token_type == TT.SUB:
			computation = "COMP D-A D"
		
		if node.op.token_type == TT.AND:
			computation = "COMP D&A D"
		
		if node.op.token_type == TT.OR:
			computation = "COMP D|A D"
		
		if node.op.token_type == TT.XOR:
			computation = "COMP D^A D"

		result += right + [computation]
		return res.success(result)
	
	def visit_UnaryOperation(self, node: UnaryOperation, hierachy: int):
		res = CompileResult()

		value: list[str] = res.register(self.visit(node.value, hierachy + 1))
		if res.error: return res

		result = value
		if node.op.token_type == TT.SUB:
			result += ["COMP -A D"]
		
		if node.op.token_type == TT.NOT:
			result += ["COMP !A D"]

		return res.success(result)
	
	def visit_ConstDefinition(self, node: ConstDefinition, hierachy: int):
		res = CompileResult()

		res.register(self.visit(node.value, hierachy + 1))
		if res.error: return res
		
		self.constants[node.symbol.symbol] = node.value.value
		return res.success([])
	
	def visit_Identifier(self, node: Identifier, hierachy: int):
		res = CompileResult()

		value = self.constants.get(node.symbol, None)
		if value is None:
			return res.fail(CompilationError(
				node.start_pos, node.end_pos,
				f"Symbol {node.symbol} does not exist."
			))
		return res.success([f"LDIA {value}"])
