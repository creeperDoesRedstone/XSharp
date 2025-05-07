from PyQt6.QtWidgets import QMainWindow, QApplication, QFileDialog
from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QIcon, QPixmap
from PyQt6.QtCore import QRegularExpression
from PyQt6 import uic
from xenon_vm import BinSyntaxHighlighter

# Lookup table for codes
# Format: A? NotD ZeroD And|Add NotOutPut ZeroA|M NotA|M DC|RShift
ALU_CODES = {
	"0": 36, "1": 126, "-1": 44, "-2": 118,
	"D": 6, "A": 224, "M": 96,
	"!D": 14, "!A": 232, "!M": 104, "-D": 30, "-A": 248, "-M": 120,
	"D++": 94, "A++": 250, "M++": 122, "D--": 22, "A--": 240, "M--": 112,
	"D+A": 144, "D+M": 16, "D-A": 216, "D-M": 88, "A-D": 154, "M-D": 26,
	"D&A": 128, "D&M": 0, "D|A": 202, "D|M": 74, "D^A": 145, "D^M": 17,
	"!(D&A)": 136, "!(D&M)": 8, "!(D|A)": 194, "!(D|M)": 66, "!(D^A)": 153, "!(D^M)": 25,
	">>D": 7, ">>A": 225, ">>M": 97,
}

JUMPS = { "JLT": 1, "JEQ": 2, "JLE": 3, "JGT": 4, "JNE": 5, "JGE": 6, "JMP": 7 }

def convert_to_bin(value: int, width: int = 14):
	if value >= 0: return bin(value)[2:].zfill(width)
	
	difference: int = 16384 + value
	return f"{bin(difference)[2:].zfill(width)}"

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
								if location in ln[2]:
									dest[i] = "1"
					
					if len(ln) == 4:
						if ln[3] in JUMPS.keys():
							# Jump
							jump = JUMPS.get(ln[3])
						else:
							raise ValueError(f"Unrecognized jump: {ln[3]}")

					binary_result.append(f"{bin(code)[2:].zfill(8)}{''.join(dest)}{bin(jump)[2:].zfill(3)}11")

				case "PLOT": # Plot pixel to buffer
					if len(ln) != 2: raise SyntaxError(f"Line {line_num + 1}: Expected 1 argument for instruction PLOT, found {len(ln) - 1} arguments instead.")

					binary_result.append(f"{'0' * 12}{ln[1]}101")

				case "BUFR": # Buffer instructions
					if len(ln) != 2: raise SyntaxError(f"Line {line_num + 1}: Expected 1 argument for instruction BUFR, found {len(ln) - 1} arguments instead.")

					op_code: str = ""
					match ln[1]:
						case "move": op_code = "10"
						case "update": op_code = "00"
						case _: raise ValueError(f"Line {line_num + 1}: Expected 'move' or 'update', got '{ln[1]}' instead.")
					
					binary_result.append(f"{'0' * 11}{op_code}001")

				case "CALL": # Call instruction
					if len(ln) != 2: raise SyntaxError(f"Line {line_num + 1}: Expected 1 argument for instruction CALL, found {len(ln) - 1} arguments instead.")

					address = ln[1]
					if address in labels: address = labels[address]

					try:
						value = int(address)
					except ValueError:
						return ValueError(f"Label '{address}' unbound.")

					binary_result.append(f"{convert_to_bin(value, 12)}1000")
				
				case "RETN": # Return instruction
					if len(ln) != 1: raise SyntaxError(f"Line {line_num + 1}: Expected 0 arguments for instruction RETN, found {len(ln) - 1} arguments instead.")

					binary_result.append("0" * 12 + "1100")

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

		self.create_format("instruction", QColor(213, 117, 157), bold=True)
		self.create_format("jump", QColor(204, 152, 13), bold=True)
		self.create_format("register", QColor(101, 171, 235))
		self.create_format("destination", QColor(109, 234, 161), bold=True)
		self.create_format("operation", QColor(213, 117, 157), bold=True)
		self.create_format("comment", QColor(98, 133, 139), italic=True)
		self.create_format("number", QColor(85, 91, 239))
		self.create_format("label", QColor("white"), italic=True)
		self.create_format("parameter", QColor(101, 171, 235))

		self.add_rule(r"\b(D|A|M|DA|AM|DM|DAM)\b", "destination")
		self.add_rule(r"\b(NOOP|HALT|LDIA|COMP|PLOT|BUFR|CALL|RETN)\b", "instruction")
		self.add_rule(r"\b(JLT|JEQ|JLE|JGT|JNE|JGE|JMP)\b", "jump")
		self.add_rule(r"\b(r\d+)\b", "register")
		self.add_rule(r"\b\d+(\.\d+)?\b", "number")
		self.add_rule(r"(\+|-|&|\||~|\^|>>)", "operation")
		self.add_rule(r"(?<!\S)\.\w+", "label")
		self.add_rule(r"\b(move|append|update|stamp)\b", "parameter")
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

class XAsmAssembler(QMainWindow):
	def __init__(self):
		super().__init__()
		uic.loadUi("GUI/shell.ui", self)
		self.setFixedSize(800, 600)
		self.setWindowTitle("XAsm Assembler")
		self.setWindowIcon(QIcon(QPixmap("Xenon.png")))

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
			
			self.file_name.setText(self.fn.split("/")[-1])
			self.file_name.setReadOnly(True)

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
				with open(f"programs/{self.file_name.text()}", "w") as f:
					f.write(self.file_text.toPlainText())
				self.fn = ""

if __name__ == "__main__":
	app = QApplication([])
	main = XAsmAssembler()

	main.show()
	app.exec()
