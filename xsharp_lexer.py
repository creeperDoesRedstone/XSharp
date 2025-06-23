from enum import Enum
from xsharp_helper import Position, UnexpectedCharacter, UnknownImport
import string
from os.path import exists

KEYWORDS = [
	"const", "var",
	"for", "start", "end", "step",
	"while",
	"if", "elseif", "else",
	"include",
	"sub"
]
DATA_TYPES = [
	"int", "bool"
]

# Token types
class TT(Enum):
	LT, LE, EQ, NE, GT, GE,\
	ADD, SUB, INC, DEC,\
	AND, OR, NOT, XOR,\
	LPR, RPR, LBR, RBR, LSQ, RSQ,\
	COL, ASSIGN, COMMA,\
	MUL, DIV, RSHIFT, LSHIFT,\
	ABS, SIGN, AT,\
	NUM, IDENTIFIER, KEYWORD, NEWLINE, EOF\
	= range(35)

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
	def __init__(self, fn: str, ftxt: str, running_from_bot: bool = False):
		self.fn = fn
		self.ftxt = ftxt
		self.from_bot = running_from_bot

		self.pos = Position(-1, 0, -1, fn, ftxt)
		self.libraries: list[str] = []
		self.current_char = None
		self.advance()

	# Advance to the next character
	def advance(self):
		self.pos.advance(self.current_char)
		self.current_char = None if self.pos.index >= len(self.ftxt) else self.ftxt[self.pos.index]

	# Standard libraries
	def process_file(self):
		txt_lines = self.ftxt.splitlines()
		result: list[str] = []

		for i in txt_lines:
			newlines = i.split(";")
			for j in newlines:
				result += [j.strip()]

		libraries: list[str] = []
		files: list[str] = []
		
		for line in result:
			line = line.split("//")[0].strip()
			if line.startswith("include "):
				libraries += line[7:].replace(" ", "").split(",")
		
		for lib in libraries:
			if lib.endswith(".xs") and exists(f"programs/{lib}"):
				if self.from_bot:
					index = self.ftxt.index(f"{lib}")
					start_pos = Position(
						index, self.ftxt[:index].count("\n"), 8, self.fn, self.ftxt
					)
					end_pos = Position(
	    				index + len(lib), self.ftxt[:index].count("\n"), 8, self.fn, self.ftxt
          			)
					return UnknownImport(start_pos, end_pos, f"{lib} (cannot import files when running from Compilation Bot)")
				
				files.append(lib)
			elif lib == "operations":
				self.libraries.append("operations")
			else:
				index = self.ftxt.index(f"{lib}")
				start_pos = Position(
					index, self.ftxt[:index].count("\n"), 8, self.fn, self.ftxt
				)
				end_pos = Position(
					index + len(lib), self.ftxt[:index].count("\n"), 8, self.fn, self.ftxt
				)
				return UnknownImport(start_pos, end_pos, lib)
		
		module_txt: str = ""
		for file in files:
			with open(f"programs/{file}", "r") as module:
				text = "".join(module.readlines())
				module_txt += text + "\n"
		
		self.ftxt = module_txt + self.ftxt

	# Lexes the file text and returns a list of tokens
	def lex(self):
		tokens: list[Token] = []

		lib_error = self.process_file()
		if lib_error is not None:
			return None, lib_error
		
		# Reinitialize, as this messes up the current character
		self.pos = Position(-1, 0, -1, self.fn, self.ftxt)
		self.advance()

		while self.current_char is not None:
			if self.ftxt.splitlines(keepends=True)[self.pos.line].strip().startswith("include "):
				self.advance()
				continue

			if self.current_char in " \t": # Ignore whitespace
				self.advance()
			
			elif self.current_char in "\n\r;": # Newlines
				char = self.current_char
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.NEWLINE, char))
			
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
			
			elif self.current_char == "#": # Absolute value
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.ABS))
			
			elif self.current_char == "$": # Sign
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.SIGN))
			
			elif self.current_char == "@": # At
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.AT))
			
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

			elif self.current_char == "[":
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.LSQ))
			
			elif self.current_char == "]":
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.RSQ))
			
			elif self.current_char == ":":
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.COL))
			
			elif self.current_char == ",":
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.COMMA))
			
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
				if self.current_char == "=":
					self.advance()
					tokens.append(Token(start_pos, self.pos, TT.EQ))
				else:
					tokens.append(Token(start_pos, self.pos, TT.ASSIGN))
			
			elif self.current_char == "<":
				start_pos = self.pos.copy()
				self.advance()
				if self.current_char == "=":
					self.advance()
					tokens.append(Token(start_pos, self.pos, TT.LE))
				elif self.current_char == "<":
					self.advance()
					tokens.append(Token(start_pos, self.pos, TT.LSHIFT))
				else:
					tokens.append(Token(start_pos, self.pos, TT.LT))
			
			elif self.current_char == ">":
				start_pos = self.pos.copy()
				self.advance()
				if self.current_char == "=":
					self.advance()
					tokens.append(Token(start_pos, self.pos, TT.GE))
				elif self.current_char == ">":
					self.advance()
					tokens.append(Token(start_pos, self.pos, TT.RSHIFT))
				else:
					tokens.append(Token(start_pos, self.pos, TT.GT))

			elif self.current_char == "!":
				start_pos = self.pos.copy()
				self.advance()
				if self.current_char == "=":
					self.advance()
					tokens.append(Token(start_pos, self.pos, TT.NE))
				else:
					return None, UnexpectedCharacter(start_pos, self.pos, "'!'")

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
				tokens.append(Token(
					start_pos, self.pos,
					TT.KEYWORD if identifier in KEYWORDS+DATA_TYPES else TT.IDENTIFIER,
					identifier
				))
			
			elif self.current_char == "*" and "operations" in self.libraries:
				start_pos = self.pos.copy()
				self.advance()
				tokens.append(Token(start_pos, self.pos, TT.MUL))

			elif self.current_char == "/":
				# Try to make a comment
				start_pos = self.pos.copy()
				self.advance()
				if self.current_char == "/":
					self.advance()
					while self.current_char is not None and self.current_char not in "\n\r":
						self.advance()
				
				elif self.current_char == "*":
					self.advance()
					while self.pos.index <= len(self.ftxt) - 2 and \
					self.current_char + self.ftxt[self.pos.index + 1] != "*/":
						self.advance()
					
					self.advance()
					self.advance()
				
				elif "operations" in self.libraries:
					start_pos = self.pos.copy()
					self.advance()
					tokens.append(Token(start_pos, self.pos, TT.DIV))

				else:
					return None, UnexpectedCharacter(start_pos, self.pos, "'/'")
			
			else: # Unrecognized character
				start_pos = self.pos.copy()
				char = self.current_char
				self.advance()
				return None, UnexpectedCharacter(start_pos, self.pos, f"'{char}'")
		
		tokens.append(Token(self.pos, self.pos, TT.EOF))
		return tokens, None
