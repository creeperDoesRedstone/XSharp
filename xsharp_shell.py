from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor
from PyQt6.QtCore import QRegularExpression
from PyQt6.QtWidgets import QMainWindow, QApplication, QPushButton, QTextEdit, QLabel, QFileDialog, QLineEdit
from xsharp_lexer import Lexer, KEYWORDS
from xsharp_parser import Parser
from xsharp_compiler import Compiler
from xasm_assembler import ASMSyntaxHighlighter

MAX_INSTRUCTIONS = 2 ** 13

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
	
	def add_rule(self, pattern: str, format_name: str):
		self.highlighting_rules.append((QRegularExpression(pattern), self.get_format(format_name)))
	
	def highlightBlock(self, text: str):
		for _pattern, _format in self.highlighting_rules:
			match_iterator = _pattern.globalMatch(text)  # Get the match iterator
			while match_iterator.hasNext():  # Use hasNext() and next()
				_match = match_iterator.next()
				self.setFormat(_match.capturedStart(), _match.capturedLength(), _format)

class XSharpSyntaxHighlighter(SyntaxHighlighter):
	def __init__(self, document):
		super().__init__(document)

		self.create_format("keyword", QColor(105, 205, 255), bold=True)
		self.create_format("keyword2", QColor(255, 170, 0), bold=True)
		self.create_format("operation", QColor(150, 150, 150))
		self.create_format("comment", QColor(85, 170, 127), italic=True)
		self.create_format("number", QColor(255, 135, 255))

		self.add_rule(r"\b" + r"\b|\b".join(KEYWORDS) + r"\b", "keyword")
		self.add_rule(r"\b(start|end|step)\b", "keyword2")
		self.add_rule(r"\b\d+(\.\d+)?\b", "number")
		self.add_rule(r"(\+|-|&|\||~|\^)", "operation")
		self.add_rule(r"//[^\n]*", "comment")

class Main(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setFixedSize(800, 600)
		self.setWindowTitle("X# Compiler")
		self.setFont(QFont(["JetBrains Mono", "Consolas"], 11))

		self.load_file_button = QPushButton(self)
		self.load_file_button.setGeometry(40, 40, 100, 40)
		self.load_file_button.setText("Load File")
		self.load_file_button.clicked.connect(self.load_file)
		self.fn = ""

		self.file_name = QLineEdit(self)
		self.file_name.setGeometry(180, 40, 440, 40)
		self.file_name.setPlaceholderText("File name")

		self.compile_button = QPushButton(self)
		self.compile_button.setGeometry(660, 40, 100, 40)
		self.compile_button.setText("Compile")
		self.compile_button.clicked.connect(self.compile)

		panel_stylesheet: str = f'padding: 6px; font: 10pt "JetBrains Mono"'

		self.xsharp_text = QTextEdit(self)
		self.xsharp_text.setGeometry(40, 100, 360, 420)
		self.xsharp_text.setStyleSheet(panel_stylesheet)
		self.xsharp_text_highlighter = XSharpSyntaxHighlighter(self.xsharp_text.document())
		self.xsharp_text.installEventFilter(self)
		self.xsharp_text.setTabStopDistance(31)
		self.xsharp_text.setAcceptRichText(False)

		self.line_count_xsharp = QLabel(self)
		self.line_count_xsharp.setGeometry(40, 520, 360, 40)
		self.line_count_xsharp.setFont(QFont(["JetBrains Mono", "Consolas"], 10))
		self.line_count_xsharp.setText("Line count: 0")

		self.result = QTextEdit(self)
		self.result.setReadOnly(True)
		self.result.setGeometry(400, 100, 360, 420)
		self.result.setStyleSheet(panel_stylesheet)
		self.result_highlighter = ASMSyntaxHighlighter(self.result.document())
		self.result.installEventFilter(self)

		self.line_count_result = QLabel(self)
		self.line_count_result.setGeometry(400, 520, 360, 40)
		self.line_count_result.setFont(QFont(["JetBrains Mono", "Consolas"], 10))
		self.line_count_result.setText("Line count: 0")
	
	def load_file(self):
		self.fn, _ = QFileDialog.getOpenFileName(self, "Open file", "programs", "X# Files (*.xs)")
		if not self.fn: return

		self.file_name.setText(self.fn.split("/")[-1])
		self.file_name.setReadOnly(True)

		with open(self.fn, "r") as f:
			self.xsharp_text.setText(f.read())

	def eventFilter(self, a0, a1):
		if a0 == self.xsharp_text:
			self.line_count_xsharp.setText(
				f"Line count: {len(self.xsharp_text.toPlainText().splitlines())}"
			)
		
		if a0 == self.result:
			self.line_count_result.setText(
				f"Line count: {len(self.result.toPlainText().splitlines())}"
			)

		return super().eventFilter(a0, a1)
	
	def compile(self):
		result, error = xs_compile("<terminal>", self.xsharp_text.toPlainText().strip())
		if error:
			print(error)
			self.result.setText("")
		else:
			assembly: str = "\n".join(result)

			self.result.setText(assembly)
			if self.file_name.text():
				with open(f"assembly/{self.file_name.text().replace('.xs', '.xasm')}", "w") as f:
					f.write(assembly)
				self.fn = ""

if __name__ == "__main__":
	app = QApplication([])
	main = Main()

	main.show()
	app.exec()
