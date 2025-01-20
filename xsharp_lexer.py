from enum import Enum
from xsharp_helper import Position, UnexpectedCharacter
import string

KEYWORDS = [
	"const", "var",
	"for", "start", "end", "step"
]

# Token types
class TT(Enum):
	ADD, SUB, INC, DEC,\
	AND, OR, NOT, XOR,\
	LPR, RPR, LBR, RBR, COL,\
	ASSIGN,\
	NUM, IDENTIFIER, KEYWORD, NEWLINE, EOF\
	= range(19)

	def __str__(self):
		return super().__str__().removeprefix("TT.")

class Token:
	def __init__(self, start_pos: Position, end_pos: Position, token_type: TT, value: str|int|None = None):
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.token_type = token_type
		self.value = value
	
	def __repr__(self):
		if self.value: return f"{self.token_type}:{self.value}"
		return f"{self.token_type}"

	def __eq__(self, value):
		if isinstance(value, Token):
			return self.value == value.value and self.token_type == value.token_type
		return False
	
	def __ne__(self, value):
		return not (self.__eq__(value))

class Lexer:
	def __init__(self, fn: str, ftxt: str):
		self.fn = fn
		self.ftxt = ftxt
		self.pos = Position(-1, 0, -1, fn, ftxt)
		self.current_char = None
		self.advance()
	
	# Advance to the next character
	def advance(self):
		self.pos.advance(self.current_char)
		self.current_char = None if self.pos.index >= len(self.ftxt) else self.ftxt[self.pos.index]
	
	# Lexes the file text and returns a list of tokens
	def lex(self):
		tokens: list[Token] = []

		while self.current_char is not None:

			if self.current_char in " \t": # Ignore whitespace
				self.advance()
			
			elif self.current_char in "\n\r;": # Newlines
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.NEWLINE))
			
			elif self.current_char == "&": # Bitwise AND
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.AND))
			
			elif self.current_char == "|": # Bitwise OR
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.OR))
			
			elif self.current_char == "~": # Bitwise NOT
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.NOT))
			
			elif self.current_char == "^": # Bitwise XOR
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.XOR))
			
			elif self.current_char == "(":
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.LPR))
			
			elif self.current_char == ")":
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.RPR))
			
			elif self.current_char == "{":
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.LBR))
			
			elif self.current_char == "}":
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.RBR))
			
			elif self.current_char == ":":
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.COL))
			
			elif self.current_char == "+":
				start_pos = self.pos.copy()
				self.advance()
				if self.current_char == "+": # Increment
					self.advance()
					tokens.append(Token(start_pos, self.pos, TT.INC))
				else: tokens.append(Token(start_pos, self.pos, TT.ADD)) # Addition
			
			elif self.current_char == "-":
				start_pos = self.pos.copy()
				self.advance()
				if self.current_char == "-":
					self.advance()
					tokens.append(Token(start_pos, self.pos, TT.DEC)) # Decrement
				else: tokens.append(Token(start_pos, self.pos, TT.SUB)) # Subtraction
			
			elif self.current_char == "=":
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.ASSIGN))

			elif self.current_char in string.digits:
				# Make number
				start_pos = self.pos.copy()
				num_str = ""
				while self.current_char is not None and self.current_char in string.digits:
					num_str += self.current_char
					self.advance()
				tokens.append(Token(start_pos, self.pos, TT.NUM, int(num_str)))
			
			elif self.current_char in string.ascii_letters or self.current_char == "_":
				# Make identifier/keyword
				start_pos = self.pos.copy()
				identifier = ""
				while self.current_char is not None and (self.current_char in string.ascii_letters + string.digits or self.current_char == "_"):
					identifier += self.current_char
					self.advance()
				tokens.append(Token(start_pos, self.pos, TT.KEYWORD if identifier in KEYWORDS else TT.IDENTIFIER, identifier))
			
			elif self.current_char == "/":
				# Try to make a comment
				start_pos = self.pos.copy()
				self.advance()
				if self.current_char != "/":
					return None, UnexpectedCharacter(start_pos, self.pos, "'/'")
				
				self.advance()
				while self.current_char is not None and self.current_char not in "\n\r":
					self.advance()
			
			else: # Unrecognized character
				start_pos = self.pos.copy()
				char = self.current_char
				self.advance()
				return None, UnexpectedCharacter(start_pos, self.pos, f"'{char}'")
		
		tokens.append(Token(self.pos, self.pos, TT.EOF))
		return tokens, None
