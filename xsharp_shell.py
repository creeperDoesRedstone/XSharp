from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QTextCursor
from PyQt6.QtCore import QRegularExpression, Qt, QEvent, QObject
from PyQt6.QtWidgets import QMainWindow, QApplication, QFileDialog, QTextEdit, QPushButton
from PyQt6 import uic

from xsharp_lexer import Lexer, KEYWORDS, DATA_TYPES
from xsharp_parser import Parser
from xsharp_compiler import Compiler
from xasm_assembler import ASMSyntaxHighlighter
from xsharp_helper import SyntaxHighlighter

def xs_compile(fn: str, ftxt: str, remove_that_one_line: bool = False):
	lexer = Lexer(fn, ftxt)
	tokens, error = lexer.lex()
	if error: return None, error

	parser = Parser(tokens)
	ast = parser.parse()
	if ast.error: return None, ast.error

	compiler = Compiler()
	res = compiler.compile(ast.node, remove_that_one_line)
	return res.value, res.error

class XSharpSyntaxHighlighter(SyntaxHighlighter):
	def __init__(self, document):
		super().__init__(document)

		self.create_format("keyword", QColor(213, 117, 157), bold=True)
		self.create_format("keyword2", QColor(217, 101, 50), italic=True)
		self.create_format("library", QColor(101, 171, 235))
		self.create_format("operation", QColor(213, 117, 157), bold=True)
		self.create_format("brackets", QColor(247, 217, 27))
		self.create_format("comment", QColor(98, 133, 139), italic=True)
		self.create_format("number", QColor(85, 91, 239))
		self.create_format("constant", QColor(204, 152, 0), bold=True)
		self.create_format("subroutine", QColor(70, 163, 183))
		self.create_format("nativesub", QColor(110, 214, 234))

		self.add_rule(r"\b\d+(\.\d+)?\b", "number")
		self.add_rule(r"\b(true|false|N_BITS)\b", "number")
		self.add_rule(r"\b[a-zA-Z_][a-zA-Z0-9_]*\s*(?=\()", "subroutine")
		self.add_rule(r"\b" + r"\b|\b".join(KEYWORDS) + r"\b", "keyword")
		self.add_rule(r"\b(update|flip|halt|plot)\b", "nativesub")
		self.add_rule(r"\b(start|end|step)\b", "keyword2")
		self.add_rule(r"\b" + r"\b|\b".join(DATA_TYPES) + r"\b", "keyword2")
		self.add_rule(r"(\+|-|\*|&|\||~|\^|=|:|<|>|<=|>=|!=|==|<<|>>)", "operation")
		self.add_rule(r"(?<=include )[^\n\r]+", "library")
		self.add_rule(r"\(|\)|\{|\}|\[|\]", "brackets")
		self.add_rule(r"//.*", "comment")
		self.add_rule(r"/\*.*?\*/", "comment", True)

		self.comment_start_expr = QRegularExpression(r"/\*")
		self.comment_end_expr = QRegularExpression(r"\*/")
		self.constant_regex = QRegularExpression(r"\bconst\s+(\w+)\s+.*")
		self.comment_regex = QRegularExpression(r"//.*|/\*[\s\S]*?\*/")
		self.constants: set = set()
	
	def highlightBlock(self, text):
		# Extract comments
		comment_matches = []
		match_iterator = self.comment_regex.globalMatch(text)
		while match_iterator.hasNext():
			match = match_iterator.next()
			comment_matches.append((match.capturedStart(), match.capturedEnd()))
		
		# Extract constant names
		new_constants: set = set()
		match_iter = self.constant_regex.globalMatch(text)
		while match_iter.hasNext():
			match = match_iter.next()
			start, end = match.capturedStart(1), match.capturedEnd(1)
			if any(c_start <= start <= c_end for c_start, c_end in comment_matches):
				continue
			new_constants.add(match.captured(1))
		
		# Update constants
		all_text = self.document().toPlainText()
		valid_constants = set()
		lines = all_text.splitlines()

		for line in lines:
			# Skip lines that are fully inside comments
			if self.comment_regex.match(line).hasMatch():
				continue

			match = self.constant_regex.match(line)
			if match.hasMatch():
				valid_constants.add(match.captured(1))

		# Remove constants that are ONLY inside comments
		self.constants = valid_constants

		# Highlight stored constants dynamically
		for constant in self.constants:
			const_regex = QRegularExpression(rf"\b{constant}\b")
			match_iterator = const_regex.globalMatch(text)
			while match_iterator.hasNext():
				match = match_iterator.next()
				start, end = match.capturedStart(), match.capturedEnd()

				# Skip if inside a comment
				if any(c_start <= start <= c_end for c_start, c_end in comment_matches):
					continue

				self.setFormat(start, end - start, self.get_format("constant"))

		# Highlight other things
		super().highlightBlock(text)

		# Highlight multiline comments / block comments
		self.setCurrentBlockState(0)
		start_index: int = 0

		if self.previousBlockState() == 1: # Previous block was a comment
			start_index = 0
		else:
			# Find the start of a block comment
			matches = self.comment_start_expr.match(text)
			start_index = matches.capturedStart() if matches.hasMatch() else -1
		
		# Process all block comments
		while start_index >= 0:
			# Try to find the end of the block comment in this block.
			end_match = self.comment_end_expr.match(text, start_index)
			if end_match.hasMatch():
				# If the end of the comment is found in this block...
				end_index = end_match.capturedEnd()
				comment_length = end_index - start_index
				self.setFormat(start_index, comment_length, self.get_format("comment"))
				# Look for another comment start after the current comment.
				next_match = self.comment_start_expr.match(text, end_index)
				start_index = next_match.capturedStart() if next_match.hasMatch() else -1
			else:
				# If no end found, highlight to the end of the block and mark state.
				comment_length = len(text) - start_index
				self.setFormat(start_index, comment_length, self.get_format("comment"))
				self.setCurrentBlockState(1)
				break

class XSharpShell(QMainWindow):
	def __init__(self):
		super().__init__()
		uic.loadUi("GUI/shell.ui", self)
		self.setWindowTitle("X# Compiler")

		self.load_file_button.clicked.connect(self.load_file)
		self.fn = ""

		self.file_name.setPlaceholderText("File name...")

		self.process_button.clicked.connect(self.compile)
		self.process_button: QPushButton

		self.xsharp_text_highlighter = XSharpSyntaxHighlighter(self.file_text.document())
		self.file_text: QTextEdit
		self.file_text.installEventFilter(self)
		self.file_text.setAcceptRichText(False)

		self.result.setReadOnly(True)
		self.result.installEventFilter(self)

		self.result_highlighter = ASMSyntaxHighlighter(self.result.document())
	
	def load_file(self):
		self.fn, _ = QFileDialog.getOpenFileName(self, "Open file", "programs", "X# Files (*.xs)")
		if not self.fn: return

		self.file_name.setText(self.fn.split("/")[-1])
		self.file_name.setReadOnly(True)

		with open(self.fn, "r") as f:
			self.file_text.setText(f.read())

	def eventFilter(self, source: QObject, event: QEvent):
		code_cursor: QTextCursor = self.file_text.textCursor()
		cursor_pos: int = code_cursor.position()
		code: str = self.file_text.toPlainText()
		self.xsharp_text_highlighter.highlightBlock(self.file_text.toPlainText())

		if source == self.file_text:
			self.ftxt_line_count.setText(
				f"Line count: {len(self.file_text.toPlainText().splitlines())}"
			)

			lines = code.splitlines()
			result: list[str] = []
			for line in lines:
				result += line.strip().split(";")
			
			for i in range(len(result)):
				result[i] = result[i].strip()
			
			if "include operations" in result:
				self.xsharp_text_highlighter.highlighting_rules[7] = (QRegularExpression(
					r"(\+|-|\*|/|&|\||~|\^|=|:|#|\$)"
				), getattr(self.xsharp_text_highlighter, "operation_format"))
			else:
				self.xsharp_text_highlighter.highlighting_rules[7] = (QRegularExpression(
					r"(\+|-|&|\||~|\^|=|:|#|\$)"
				), getattr(self.xsharp_text_highlighter, "operation_format"))
		
		if source == self.file_text and event.type() == QEvent.Type.KeyPress:

			if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Slash:
				if not code_cursor.hasSelection():
					code_cursor.select(code_cursor.SelectionType.LineUnderCursor)

				selection_start: int = code_cursor.selectionStart()
				selection_end: int = code_cursor.selectionEnd()

				# Normalize selection to full lines
				code_cursor.setPosition(selection_start)
				code_cursor.movePosition(code_cursor.MoveOperation.StartOfBlock, code_cursor.MoveMode.KeepAnchor)
				selection_start = code_cursor.selectionStart()

				code_cursor.setPosition(selection_end)
				code_cursor.movePosition(code_cursor.MoveOperation.EndOfBlock, code_cursor.MoveMode.KeepAnchor)
				selection_end = code_cursor.selectionEnd()

				# Extract all lines
				code_cursor.setPosition(selection_start)
				code_cursor.setPosition(selection_end, code_cursor.MoveMode.KeepAnchor)
				selected_text: str = code_cursor.selection().toPlainText()
				lines: list[str] = selected_text.splitlines()

				# Toggle comment for each line
				for i, line_text in enumerate(lines):
					line_text: str = line_text.strip()
					if line_text.startswith("// "):
						lines[i] = (line_text.lstrip().replace("// ", "", 1))
					elif line_text.startswith("//"):
						lines[i] = (line_text.lstrip().replace("//", "", 1))
					else:
						lines[i] = ("// " + line_text)
				
				# Update line
				updated_text = '\n'.join(lines)
				code_cursor.insertText(updated_text)
				return True
			
			if event.key() == Qt.Key.Key_ParenLeft:
				# Auto-complete parentheses
				code_cursor.insertText('()')
				code_cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
				self.file_text.setTextCursor(code_cursor)
				return True
			
			if event.key() == Qt.Key.Key_ParenRight:
				# Check if the character after the cursor is a right parenthesis
				if cursor_pos > 0 and cursor_pos < len(code) and code[cursor_pos] == ')':
					code_cursor.movePosition(QTextCursor.MoveOperation.Right)
					self.file_text.setTextCursor(code_cursor)
					return True
				return super().eventFilter(source, event)
			
			if event.key() == Qt.Key.Key_BraceLeft:
				# Auto-complete braces
				code_cursor.insertText('{}')
				code_cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
				self.file_text.setTextCursor(code_cursor)
				return True
			
			if event.key() == Qt.Key.Key_BraceRight:
				# Check if the character after the cursor is a right brace
				if cursor_pos > 0 and cursor_pos < len(code) and code[cursor_pos] == '}':
					code_cursor.movePosition(QTextCursor.MoveOperation.Right)
					self.file_text.setTextCursor(code_cursor)
					return True
				return super().eventFilter(source, event)
			
			if event.key() == Qt.Key.Key_BracketLeft:
				# Auto-complete braces
				code_cursor.insertText('[]')
				code_cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
				self.file_text.setTextCursor(code_cursor)
				return True
			
			if event.key() == Qt.Key.Key_BracketRight:
				# Check if the character after the cursor is a right brace
				if cursor_pos > 0 and cursor_pos < len(code) and code[cursor_pos] == ']':
					code_cursor.movePosition(QTextCursor.MoveOperation.Right)
					self.file_text.setTextCursor(code_cursor)
					return True
				return super().eventFilter(source, event)

			if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
				# Auto indentation
				lines: list[str] = code.splitlines()
				tabs_num: int = 0

				if code_cursor.blockNumber() >= len(lines):
					return super().eventFilter(source, event)

				for i in lines[code_cursor.blockNumber()]:
					if i != "\t": break

					tabs_num += 1

				TAB = "\t"

				if cursor_pos > 0 and cursor_pos < len(code) and code[cursor_pos - 1] + code[cursor_pos] in ("{}", "()", "[]"):
					code_cursor.insertText(f"\n{TAB * (tabs_num+1)}\n{TAB * (tabs_num)}")
					
					for _ in range(tabs_num + 1):
						code_cursor.movePosition(QTextCursor.MoveOperation.Left)
					
					self.file_text.setTextCursor(code_cursor)
					return True
				return super().eventFilter(source, event)
		
		if source == self.result:
			self.result_line_count.setText(
				f"Line count: {len(self.result.toPlainText().splitlines())}"
			)

		return super().eventFilter(source, event)

	def compile(self):
		self.error.setText("")
		self.result.setText("")
		
		result, error = xs_compile("<shell>", self.file_text.toPlainText().strip())
		if error:
			self.error.setText(f"{error}")
		else:
			assembly: str = "\n".join(result)

			self.result.setText(assembly)
			if self.file_name.text():
				with open(f"assembly/{self.file_name.text().replace('.xs', '.xasm')}", "w") as f:
					f.write(assembly)
				with open(f"programs/{self.file_name.text()}", "w") as f:
					f.write(self.file_text.toPlainText())
				self.fn = ""

if __name__ == "__main__":
	app = QApplication([])
	main = XSharpShell()

	main.show()
	app.exec()
