from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QTextCharFormat, QSyntaxHighlighter, QFont, QColor

# Position class
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

# Base Error class, all instances of errors inherit from this.
class Error:
	def __init__(self, start_pos: Position, end_pos: Position, error_name: str, details: str):
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.error_name = error_name
		self.details = details

	def __repr__(self):
		return f"File {self.start_pos.fn}, line {self.start_pos.line + 1}, column {self.start_pos.col + 1}:\n\n{self.error_name}: {self.details}"

# Occurs when the lexer finds an unknown character.
class UnexpectedCharacter(Error):
	def __init__(self, start_pos: Position, end_pos: Position, details: str):
		super().__init__(start_pos, end_pos, "Unexpected Character", details)

# Occurs when the lexer finds an unknown library.
class UnknownLibrary(Error):
	def __init__(self, start_pos: Position, end_pos: Position, details: str):
		super().__init__(start_pos, end_pos, "Unknown Library", details)

# Occurs when the parser encounters incorrect syntax.
class InvalidSyntax(Error):
	def __init__(self, start_pos: Position, end_pos: Position, details: str):
		super().__init__(start_pos, end_pos, "Invalid Syntax", details)

# Occurs when an error occurs during the compilation process.
class CompilationError(Error):
	def __init__(self, start_pos: Position, end_pos: Position, details: str):
		super().__init__(start_pos, end_pos, "Compilation Error", details)

# A general-purpose syntax highlighter.
class SyntaxHighlighter(QSyntaxHighlighter):
	def __init__(self, document):
		super().__init__(document)
		self.highlighting_rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

	def create_format(self, name: str, color: QColor, bold: bool = False, italic: bool = False):
		fmt = QTextCharFormat()
		fmt.setForeground(color)
		if bold: fmt.setFontWeight(QFont.Weight.Bold)
		if italic: fmt.setFontItalic(True)

		setattr(self, f"{name}_format", fmt)
	
	def get_format(self, name: str):
		return getattr(self, f"{name}_format")
	
	def add_rule(self, pattern: str, fmt_name: str, dot_matches_everything: bool = False):
		regex = QRegularExpression(pattern)
		if dot_matches_everything:
			regex.setPatternOptions(QRegularExpression.PatternOption.DotMatchesEverythingOption)
		self.highlighting_rules.append((regex, self.get_format(fmt_name)))
	
	def highlightBlock(self, text: str):
		for _pattern, _format in self.highlighting_rules:
			match_iterator = _pattern.globalMatch(text)  # Get the match iterator
			while match_iterator.hasNext():  # Use hasNext() and next()
				_match = match_iterator.next()
				self.setFormat(_match.capturedStart(), _match.capturedLength(), _format)
