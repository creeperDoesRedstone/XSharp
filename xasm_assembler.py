from PyQt6.QtWidgets import QMainWindow, QApplication, QPushButton, QTextEdit, QFileDialog, QLabel
from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor
from PyQt6.QtCore import QRegularExpression
from PyQt6 import uic
from xenon_vm import BinSyntaxHighlighter

# Lookup table for codes
# Format: A? NotD ZeroD And|Add NotOutPut ZeroA|M NotA|M DisableCarry
ALU_CODES = {
	"0": 36,
	"1": 126,
	"-1": 44,
	"-2": 118,
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
	"A++": 250,
	"M++": 122,
	"D--": 22,
	"A--": 240,
	"M--": 112,
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

def convert_to_bin(value: int):
	if value >= 0: return bin(value)[2:].zfill(14)
	
	difference: int = 16384 + value
	return f"{bin(difference)[2:].zfill(14)}"

def assemble(ftxt: str):
	try:
		binary_result: list[str] = []
		labels: dict[str, int] = {}
		skips: int = 0

		file_text: str = ftxt
		for i in range(16): # Remove register labels r0 - r15
			file_text = file_text.replace(f"r{i}", f"{i}")

		# Preliminary scan
		for line_num, line in enumerate(file_text.splitlines()):
			if line.startswith(".") and " " not in line.strip():
				labels[line.strip()] = line_num - skips
				skips += 1

		# Assemble
		for line_num, line in enumerate(file_text.splitlines()):
			line = line.strip()

			try:
				comment_index = line.index("//")
			except:
				pass
			else:
				line = line[:comment_index] # Remove comments

			if line.strip() == "":
				binary_result.append("0" * 16) # NOOP
				continue # Skip empty lines

			ln = line.strip().split(" ")
			inst = ln[0]

			match inst:
				case "NOOP": # No operation
					if len(ln) != 1: raise SyntaxError(f"Line {line_num + 1}: Expected 0 arguments for instruction NOOP, found {len(ln) - 1} arguments instead.")
					binary_result.append("0" * 16)
				
				case "HALT": # Halts the execution of the program
					if len(ln) != 1: raise SyntaxError(f"Line {line_num + 1}: Expected 0 arguments for instruction HALT, found {len(ln) - 1} arguments instead.")
					binary_result.append("0" * 13 + "100")
				
				case "LDIA": # Load immediate value into A register
					if len(ln) != 2: raise SyntaxError(f"Line {line_num + 1}: Expected 1 argument for instruction LDIA, found {len(ln) - 1} arguments instead.")

					immediate = ln[1]
					if immediate in labels: immediate = labels[immediate]

					try:
						value = int(immediate)
					except ValueError:
						return ValueError(f"Label '{immediate}' unbound.")
					

					binary_result.append(f"{convert_to_bin(value)}10")
				
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

					binary_result.append(f"{bin(code)[2:].zfill(8)}{''.join(dest)}{bin(jump)[2:].zfill(3)}11")

				case "PLOT": # Plot pixel to screen
					if len(ln) != 2: raise SyntaxError(f"Line {line_num + 1}: Expected 1 argument for instruction NOOP, found {len(ln) - 1} arguments instead.")

					binary_result.append(f"{ln[1]}{'0' * 12}101")

				case _:
					if not (line.startswith(".") and len(ln) == 1):
						raise NotImplementedError(f"Unknown instruction: {inst}.")
			
		return binary_result

	except SyntaxError as e: return e
	except ValueError as e: return e
	except NotImplementedError as e: return e

class ASMSyntaxHighlighter(QSyntaxHighlighter):
	def __init__(self, document):
		super().__init__(document)
		self.highlighting_rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

		self.create_format("instruction", QColor(105, 205, 255), bold=True)
		self.create_format("jump", QColor(255, 170, 0), bold=True)
		self.create_format("register", QColor(170, 170, 255))
		self.create_format("destination", QColor(255, 255, 0), bold=True)
		self.create_format("operation", QColor(150, 150, 150))
		self.create_format("comment", QColor(85, 170, 127), italic=True)
		self.create_format("number", QColor(255, 135, 255))

		self.add_rule(r"\b(D|A|M|DA|AM|DM|DAM)\b", "destination")
		self.add_rule(r"\b(NOOP|HALT|LDIA|COMP|PLOT)\b", "instruction")
		self.add_rule(r"\b(JLT|JEQ|JLE|JGT|JNE|JGE|JMP)\b", "jump")
		self.add_rule(r"\b(r\d+)\b", "register")
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
		uic.loadUi("GUI/shell.ui", self)
		self.setFixedSize(800, 600)
		self.setWindowTitle("XAsm Assembler")

		self.process_button.setText("Assemble!")
		self.process_button.clicked.connect(self.assemble)

		self.load_file_button.clicked.connect(self.load_file)
		self.fn = ""

		self.result.installEventFilter(self)
		self.result_highlighter = BinSyntaxHighlighter(self.result.document())

		self.file_text.setAcceptRichText(False)
		self.file_text.installEventFilter(self)
		self.ftxt_highlighter = ASMSyntaxHighlighter(self.file_text.document())

	def load_file(self):
		self.fn, _ = QFileDialog.getOpenFileName(self, "Open File", "assembly", "XAsm Files (*.xasm)")
		if self.fn:
			with open(self.fn, "r") as file:
				self.file_text.setPlainText(file.read())

	def eventFilter(self, a0, a1):
		if a0 == self.file_text:
			self.ftxt_line_count.setText(
				f"Line count: {len(self.file_text.toPlainText().splitlines())}"
			)
		
		if a0 == self.result:
			self.result_line_count.setText(
				f"Line count: {len(self.result.toPlainText().splitlines())}"
			)

		return super().eventFilter(a0, a1)

	def assemble(self):
		self.error.setText("")
		self.result.setText("")

		result = assemble(self.file_text.toPlainText())
		if isinstance(result, Exception):
			self.error.setText(f"{result}")
		else:
			self.result.setText("\n".join(result))

			if self.fn:
				with open(self.fn.replace(".xasm", ".bin").replace("assembly", "binary", 1), "w") as file:
					file.write("\n".join(result))
				self.fn = ""

if __name__ == "__main__":
	app = QApplication([])
	main = Main()

	main.show()
	app.exec()
