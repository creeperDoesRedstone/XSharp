from PyQt6.QtWidgets import QMainWindow, QApplication, QLabel, QPushButton, QTextEdit, QFileDialog
from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor
from PyQt6.QtCore import QRegularExpression

MAX_INSTRUCTIONS = 8192

class BinSyntaxHighlighter(QSyntaxHighlighter):
	def __init__(self, document):
		super().__init__(document)
		self.highlighting_rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

		self.create_format("comp_inst", QColor(120, 174, 255))
		self.create_format("load_inst", QColor(150, 200, 255))
		self.create_format("halt", QColor(150, 175, 255))

		self.add_rule(r"\b^11\d+\b", "comp_inst")
		self.add_rule(r"\b^10\d+\b", "load_inst")
		self.add_rule(r"\b^0000000000000001\b", "halt")

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
		self.setWindowTitle("Xenon VM")
		self.setFont(QFont(["JetBrains Mono", "Consolas"], 11))

		self.step_button = QPushButton(self)
		self.step_button.setGeometry(660, 40, 100, 40)
		self.step_button.setText("Step")
		self.step_button.clicked.connect(lambda: self.run(self.file_text.toPlainText()))
		self.program_counter = 0

		self.load_file_button = QPushButton(self)
		self.load_file_button.setGeometry(40, 40, 100, 40)
		self.load_file_button.setText("Load File")
		self.load_file_button.clicked.connect(self.load_file)

		panel_stylesheet: str = f'padding: 12px; font: 10pt "JetBrains Mono";'

		self.file_text = QTextEdit(self)
		self.file_text.setGeometry(400, 100, 360, 420)
		self.file_text.setStyleSheet(panel_stylesheet)
		self.file_text.setAcceptRichText(False)
		self.highlighter = BinSyntaxHighlighter(self.file_text.document())

		self.a_reg = QLabel(self)
		self.a_reg.setGeometry(40, 100, 60, 40)
		self.a_reg.setStyleSheet("color: rgb(255, 170, 0)")

		self.d_reg = QLabel(self)
		self.d_reg.setGeometry(40, 140, 60, 40)
		self.d_reg.setStyleSheet("color: rgb(100, 200, 255)")
		self.memory = QLabel(self)
		self.memory.setGeometry(40, 180, 60, 40)

		self.memory_value = [0] * MAX_INSTRUCTIONS
		
		self.a_reg_value = 0
		self.set_value(self.a_reg, 0, "A")

		self.d_reg_value = 0
		self.set_value(self.d_reg, 0, "D")

		self.set_value(self.memory, 0, "M")

		self.current_inst = QLabel(self)
		self.current_inst.setGeometry(40, 220, 260, 40)
		self.current_inst.setStyleSheet("color: rgb(200, 100, 255)")
		self.current_inst.setText("Instruction: 0")
	
	def load_file(self):
		fn, _ = QFileDialog.getOpenFileName(self, "Open File", "binary", "Binary files (*.bin)")
		if fn:
			with open(fn, "r") as file:
				self.file_text.setPlainText(file.read())
			
			self.program_counter = 0
			self.current_inst.setText(f"Instruction: {self.program_counter}")
	
	def set_value(self, register: QLabel, value: int, kind: str):
		register.setText(f"{kind}: {value}")
		if kind == "A":
			self.a_reg_value = value
			self.memory.setText(f"M: {self.memory_value[self.a_reg_value]}")
		elif kind == "D":
			self.d_reg_value = value
		elif kind == "M":
			self.memory_value[self.a_reg_value] = value
	
	def step(self, PROM: list):
		NOOP = "0" * 16
		HALT = "0" * 15 + "1"

		current_inst = PROM[self.program_counter]
		self.current_inst.setText(f"Instruction: {self.program_counter}")

		if current_inst == NOOP:
			self.program_counter += 1
			return False
		
		elif current_inst == HALT:
			return True
		
		elif current_inst[0:2] == "10": # LDIA
			value = int(current_inst[3:], 2)
			if current_inst[2] == "1":
				value = -16384 + value # 2's complement
			self.set_value(self.a_reg, value, "A")
			self.program_counter += 1
			return False
		
		elif current_inst[0:2] == "11": # COMP
			code = current_inst[2:10]
			dest = current_inst[10:13]
			jumps = current_inst[13:]

			D = self.d_reg_value
			A = self.a_reg_value if code[0] == "1" else self.memory_value[self.a_reg_value]
			res = 0

			if code[2] == "1": D = 0 # Cancel D
			if code[1] == "1": D = ~D # Not D
			if code[5] == "1": A = 0 # Cancel A/M
			if code[6] == "1": A = ~A # Not A/M

			if code[3] == "1": # D + A/M
				res = D + A
				if code[7] == "1": res = D ^ A # D xor A/M
			else: # D and A/M
				res = D & A
			
			if res > 32767: res -= 65536 # Overflow
			if res < -32768: res += 65536
			if code[4] == "1": res = ~res # Not result

			if dest[0] == "1":
				self.set_value(self.d_reg, res, "D")
			if dest[1] == "1":
				self.set_value(self.a_reg, res, "A")
			if dest[2] == "1":
				self.set_value(self.memory, res, "M")

			conditions = (res > 0) * 4 + (res == 0) * 2 + (res < 0)
			jump = conditions & int(jumps, 2)

			if jump > 0:
				self.program_counter = self.a_reg_value
			else:
				self.program_counter += 1

			return False

		return False

	def run(self, code: str, max_steps: int|None = None):
		NOOP = "0" * 16
		HALT = "0" * 15 + "1"

		PROM = code.strip().splitlines()

		self.program_counter = 0
		steps: int = 0
		current_inst = PROM[self.program_counter]

		self.set_value(self.a_reg, 0, "A")
		self.set_value(self.d_reg, 0, "D")
		self.set_value(self.memory, 0, "M")

		if not PROM: return False

		while current_inst != HALT:
			self.current_inst.setText(f"Instruction: {self.program_counter}")
			current_inst = PROM[self.program_counter]
			self.step(PROM)

			steps += 1

			if max_steps != None and steps > max_steps:
				return True # Timeout has occured
		
		return False

if __name__ == "__main__":
	app = QApplication([])
	main = Main()

	main.show()
	app.exec()