from PyQt6.QtWidgets import QMainWindow, QApplication, QLineEdit, QLabel, QPushButton, QTextEdit
from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor
from PyQt6.QtCore import QRegularExpression

# Lookup table for codes
# Format: A? NotD ZeroD And|Add NotOutPut ZeroA|M NotA|M DisableCarry
ALU_CODES = {
	"0": 36,
	"1": 126,
	"-1": 44,
	"D": 6,
	"A": 224,
	"M": 96,
	"!D": 14,
	"!A": 232,
	"!M": 104,
	"-D": 30,
	"-A": 248,
	"-M": 120,
	"D++": 94,
	"A++": 251,
	"M++": 123,
	"D--": 22,
	"A--": 248,
	"M--": 120,
	"D+A": 144,
	"D+M": 16,
	"D-A": 216,
	"D-M": 88,
	"A-D": 154,
	"M-D": 26,
	"D&A": 128,
	"D&M": 0,
	"!(D&A)": 136,
	"!(D&M)": 8,
	"D|A": 202,
	"D|M": 74,
	"!(D|A)": 194,
	"!(D|M)": 66,
	"D^A": 129,
	"D^M": 1,
	"!(D^A)": 137,
	"!(D^M)": 9,
}

JUMPS = {
	"JLT": 1, "JEQ": 2, "JLE": 3, "JGT": 4, "JNE": 5, "JGE": 6, "JMP": 7
}

def assemble(ftxt: str):
	try:
		binary_file = []
		file_text = ftxt
		for i in range(16):
			file_text = file_text.replace(f"r{i}", f"{i}")

		for line_num, line in enumerate(file_text.splitlines()):
			try: comment_index = line.index("//")
			except: pass
			else: line = line[:comment_index]

			if line.strip() == "": continue

			ln = line.strip().split(" ")
			inst = ln[0]

			match inst:
				case "NOOP":
					if len(ln) != 1: raise SyntaxError(f"Line {line_num + 1}: Expected 0 arguments for instruction NOOP, found {len(ln) - 1} arguments instead.")
					binary_file.append("0" * 16)
				
				case "HALT":
					if len(ln) != 1: raise SyntaxError(f"Line {line_num + 1}: Expected 0 arguments for instruction HALT, found {len(ln) - 1} arguments instead.")
					binary_file.append("0" * 15 + "1")
				
				case "LDIA": # Load immediate value into A register
					if len(ln) != 2: raise SyntaxError(f"Line {line_num + 1}: Expected 1 argument for instruction LDIA, found {len(ln) - 1} arguments instead.")

					value = bin(int(ln[1]))[2:].zfill(14)
					binary_file.append(f"10{value}")
				
				case "COMP": # Compute ALU instruction
					if len(ln) not in (2, 3, 4): raise SyntaxError(f"Line {line_num + 1}: Expected 1 - 3 arguments for instruction COMP, found {len(ln) - 1} arguments instead.")

					code = ALU_CODES.get(ln[1], None)
					if code == None: raise ValueError(f"Code '{ln[1]}' is not in the available codes.")

					jump: int = 0
					dest: list[str] = ["0"] * 3
					if len(ln) > 2:
						if ln[2] in JUMPS.keys():
							# Jump
							jump = JUMPS.get(ln[2])
						else:
							for i, location in enumerate("DAM"):
								if location in ln[2]: dest[i] = "1"

					binary_file.append(f"11{bin(code)[2:].zfill(8)}{''.join(dest)}{bin(jump)[2:].zfill(3)}")

				case _:
					raise NotImplementedError(f"Unknown instruction: {inst}.")
			

		return binary_file

	except SyntaxError as e: return e
	except ValueError as e: return e
	except NotImplementedError as e: return e

class ASMSyntaxHighlighter(QSyntaxHighlighter):
	def __init__(self, document):
		super().__init__(document)
		self.highlighting_rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

		self.create_format("instruction", QColor(105, 205, 255), bold=True)
		self.create_format("jump", QColor(255, 170, 0), bold=True)
		self.create_format("location", QColor(255, 255, 0), bold=True)
		self.create_format("operation", QColor(150, 150, 150))
		self.create_format("comment", QColor(85, 170, 127), italic=True)
		self.create_format("number", QColor(255, 135, 255))

		self.add_rule(r"(D|A|M)", "location")
		self.add_rule(r"\b(NOOP|HALT|LDIA|COMP)\b", "instruction")
		self.add_rule(r"\b(JLT|JEQ|JLE|JGT|JNE|JGE|JMP)\b", "jump")
		self.add_rule(r"\b\d+(\.\d+)?\b", "number")
		self.add_rule(r"(\+|-|&|\||~|\^)", "operation")
		self.add_rule(r"//[^\n]*", "comment")

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

class Main(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setFixedSize(800, 600)
		self.setWindowTitle("XAsm Assembler")
		self.setFont(QFont(["JetBrains Mono", "Consolas"], 11))

		self.assemble_button = QPushButton(self)
		self.assemble_button.setGeometry(660, 40, 100, 40)
		self.assemble_button.setText("Assemble!")
		self.assemble_button.clicked.connect(self.assemble)

		panel_stylesheet: str = f'padding: 12px; font: 10pt "JetBrains Mono"'

		self.result = QTextEdit(self)
		self.result.setReadOnly(True)
		self.result.setGeometry(400, 100, 360, 420)
		self.result.setStyleSheet(panel_stylesheet)

		self.file_text = QTextEdit(self)
		self.file_text.setGeometry(40, 100, 360, 420)
		self.file_text.setStyleSheet(panel_stylesheet)
		self.highlighter = ASMSyntaxHighlighter(self.file_text.document())

	def assemble(self):
		result = assemble(self.file_text.toPlainText())
		if isinstance(result, Exception):
			self.result.setText(f"{result}")
		else:
			self.result.setText("\n".join(result))

if __name__ == "__main__":
	app = QApplication([])
	main = Main()

	main.show()
	app.exec()
