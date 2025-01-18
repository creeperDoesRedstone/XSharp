from PyQt6.QtWidgets import QMainWindow, QApplication, QLineEdit, QLabel, QPushButton, QTextEdit
from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor
from PyQt6.QtCore import QRegularExpression

# Lookup table for codes
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
	"-D": 15,
	"-A": 248,
	"-M": 120,
	"D+A": 144,
	"D+M": 16
}

JUMPS = {
	"JLT": 1, "JEQ": 2, "JLE": 3, "JGT": 4, "JNE": 5, "JGE": 6, "JMP": 7
}

def assemble(fn: str):
	try:
		file = open(f"assembly\\{fn}.xasm", 'r')
		binary_file = open(f"binary\\{fn}.bin", 'w')

		for line_num, line in enumerate(file):
			try: comment_index = line.index("//")
			except: pass
			else: line = line[:comment_index]

			ln = line.strip().split(" ")
			inst = ln[0]

			match inst:
				case "NOOP":
					if len(ln) != 1: raise SyntaxError(f"Line {line_num + 1}: Expected 0 arguments for instruction NOOP, found {len(ln) - 1} arguments instead.")
					binary_file.write("0" * 16)
				
				case "HALT":
					if len(ln) != 1: raise SyntaxError(f"Line {line_num + 1}: Expected 0 arguments for instruction HALT, found {len(ln) - 1} arguments instead.")
					binary_file.write("0" * 15 + "1")
				
				case "LDIA": # Load immediate value into A register
					if len(ln) != 2: raise SyntaxError(f"Line {line_num + 1}: Expected 1 argument for instruction LDIA, found {len(ln) - 1} arguments instead.")

					value = bin(int(ln[1]))[2:].zfill(14)
					binary_file.write(f"10{value}")
				
				case "COMP": # Compute ALU instruction
					if len(ln) not in (2, 3, 4): raise SyntaxError(f"Line {line_num + 1}: Expected 1 - 3 arguments for instruction COMP, found {len(ln) - 1} arguments instead.")

					code = ALU_CODES.get(ln[1], None)
					if code == None: raise ValueError(f"Code '{code}' is not in the available codes.")

					jump: int = 0
					dest: list[str] = ["0"] * 3
					if len(ln) > 2:
						if ln[2] in JUMPS.keys():
							# Jump
							jump = JUMPS.get(ln[2])
						else:
							for i, location in enumerate("DAM"):
								if location in ln[2]: dest[i] = "1"

					binary_file.write(f"11{bin(code)[2:].zfill(8)}{''.join(dest)}{bin(jump)[2:].zfill(3)}")

				case _:
					raise NotImplementedError(f"Unknown instruction: {inst}.")
			
			binary_file.write("\n")

		file.close()
		binary_file.close()
		return True

	except FileNotFoundError:
		return FileNotFoundError(f"File '{fn}.xasm' cannot be located. Try moving it into the 'assembly' folder.")
	except SyntaxError as e: return e
	except ValueError as e: return e
	except NotImplementedError as e: return e

class SyntaxHighlighter(QSyntaxHighlighter):
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

		self.label = QLabel(self)
		self.label.setGeometry(40, 20, 600, 60)
		self.label.setText("Enter the file you want to assemble:")

		self.file = QLineEdit(self)
		self.file.setGeometry(40, 80, 600, 40)

		self.assemble_button = QPushButton(self)
		self.assemble_button.setGeometry(660, 80, 100, 40)
		self.assemble_button.setText("Assemble!")
		self.assemble_button.clicked.connect(self.assemble)

		self.result = QTextEdit(self)
		self.result.setReadOnly(True)
		self.result.setGeometry(400, 140, 360, 420)
		self.result.setStyleSheet(f"padding: 20px")

		self.file_text = QTextEdit(self)
		self.file_text.setReadOnly(True)
		self.file_text.setGeometry(40, 140, 360, 420)
		self.file_text.setStyleSheet(f"padding: 20px")
		self.highlighter = SyntaxHighlighter(self.file_text.document())

	def assemble(self):
		result = assemble(self.file.text())
		if result == True:
			with open(f"binary\\{self.file.text()}.bin", 'r') as bin_file:
				ftxt = "".join(bin_file.readlines())
			self.result.setText(ftxt)
			with open(f"assembly\\{self.file.text()}.xasm", 'r') as asm_file:
				ftxt = "".join(asm_file.readlines())
			self.file_text.setText(ftxt)
		else:
			self.result.setText(f"{result}")
			self.file_text.setText("")

if __name__ == "__main__":
	app = QApplication([])
	main = Main()

	main.show()
	app.exec()
