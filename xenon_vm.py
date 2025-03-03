from PyQt6.QtWidgets import QMainWindow, QApplication, QLabel, QPushButton, QTextEdit, QFileDialog
from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor
from PyQt6.QtCore import QRegularExpression

from xsharp_compiler import Compiler
from screen_writer import write_screen

MAX_INSTRUCTIONS = 2 ** 12

class BinSyntaxHighlighter(QSyntaxHighlighter):
	def __init__(self, document):
		super().__init__(document)
		self.highlighting_rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

		self.create_format("comp_inst", QColor(120, 174, 255))
		self.create_format("load_inst", QColor(255, 200, 150))
		self.create_format("halt_inst", QColor(255, 150, 150), True)
		self.create_format("plot_inst", QColor(255, 225, 115), italic=True)
		self.create_format("plot_inst_off", QColor(117, 76, 19), italic=True)

		self.add_rule(r"\b\d{14}10$\b", "load_inst")
		self.add_rule(r"\b\d{14}11$\b", "comp_inst")
		self.add_rule(r"\b1\d{13}01$\b", "plot_inst")
		self.add_rule(r"\b0\d{13}01$\b", "plot_inst_off")
		self.add_rule(r"\b0000000000000100\b", "halt_inst")

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

		self.init_GUI()
		self.init_memory()
		self.init_screen(48, 28)

	def init_GUI(self):
		self.run_button = QPushButton(self)
		self.run_button.setGeometry(660, 40, 100, 40)
		self.run_button.setText("Run")
		self.run_button.clicked.connect(lambda: self.run(self.file_text.toPlainText()))
		self.program_counter = 0

		self.step_button = QPushButton(self)
		self.step_button.setGeometry(540, 40, 100, 40)
		self.step_button.setText("Step")
		self.step_button.clicked.connect(lambda: self.step(
			self.file_text.toPlainText().strip().splitlines()
		))

		self.export_button = QPushButton(self)
		self.export_button.setGeometry(420, 40, 100, 40)
		self.export_button.setText("Export")
		self.export_button.clicked.connect(lambda: write_screen(self.lit_pixels))

		self.load_file_button = QPushButton(self)
		self.load_file_button.setGeometry(40, 40, 100, 40)
		self.load_file_button.setText("Load File")
		self.load_file_button.clicked.connect(self.load_file)

		panel_stylesheet: str = f'padding: 12px; font: 10pt "JetBrains Mono";'

		self.file_text = QTextEdit(self)
		self.file_text.setGeometry(440, 100, 320, 420)
		self.file_text.setStyleSheet(panel_stylesheet)
		self.file_text.setAcceptRichText(False)
		self.highlighter = BinSyntaxHighlighter(self.file_text.document())

	def init_memory(self):
		self.a_reg = QLabel(self)
		self.a_reg.setGeometry(40, 100, 100, 40)
		self.a_reg.setStyleSheet("color: rgb(255, 170, 0)")

		self.d_reg = QLabel(self)
		self.d_reg.setGeometry(40, 140, 100, 40)
		self.d_reg.setStyleSheet("color: rgb(100, 200, 255)")
		self.memory = QLabel(self)
		self.memory.setGeometry(40, 180, 100, 40)

		self.memory_value = [0] * (Compiler().input_addr + 1)
		
		self.a_reg_value = 0
		self.set_value(self.a_reg, 0, "A")

		self.d_reg_value = 0
		self.set_value(self.d_reg, 0, "D")

		self.set_value(self.memory, 0, "M")

		self.current_inst = QLabel(self)
		self.current_inst.setGeometry(40, 220, 260, 40)
		self.current_inst.setStyleSheet("color: rgb(200, 100, 255)")
		self.current_inst.setText("Instruction: 0")

	def init_screen(self, length: int, width: int):
		self.PIXEL_SIZE = 8
		self.screen_length = length
		self.screen_width = width

		self.lit_pixels: list[tuple[int, int]] = []

		for x in range(self.screen_length):
			for y in range(self.screen_width):
				# print(x * PIXEL_SIZE + 40, y * PIXEL_SIZE + 300)
				setattr(self, f"px[{x}][{y}]", QLabel(text="", parent=self))
				pixel: QLabel = getattr(self, f"px[{x}][{y}]")
				pixel.setObjectName(f"px[{x}][{y}]")

				pixel.setStyleSheet("background-color: rgb(117, 76, 19); border: 1px solid rgb(89, 52, 0)")
				pixel.setGeometry(x * self.PIXEL_SIZE + 20, 508 - y * self.PIXEL_SIZE, self.PIXEL_SIZE, self.PIXEL_SIZE)

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

	def step(self, PROM: list[str]):
		NOOP = "0" * 16
		HALT = "0000000000000100"

		current_inst = PROM[self.program_counter]
		self.current_inst.setText(f"Instruction: {self.program_counter}")

		op_code = current_inst[-2:]

		if current_inst == NOOP:
			self.program_counter += 1
		
		elif current_inst == HALT:
			return True
		
		elif op_code == "10": # LDIA
			value = int(current_inst[:-2], 2)
			if current_inst[0] == "1":
				value = -16384 + value # 2's complement
			self.set_value(self.a_reg, value, "A")
			self.program_counter += 1
		
		elif op_code == "11": # COMP
			code = current_inst[0:8]
			dest = current_inst[8:11]
			jumps = current_inst[11:14]

			D = self.d_reg_value
			A = self.a_reg_value if code[0] == "1" else self.memory_value[self.a_reg_value]
			res = 0

			if code[2] == "1": D = 0 # Cancel D
			if code[1] == "1": D = ~D # Invert D
			if code[5] == "1": A = 0 # Cancel A/M
			if code[6] == "1": A = ~A # Invert A/M

			if code[3] == "1": # D + A/M
				res = D + A
				if code[7] == "1": res = D ^ A # D xor A/M
			else: # D & A/M
				res = D & A
			
			if res > 32767: res -= 65536 # Overflow
			if res < -32768: res += 65536
			if code[4] == "1": res = ~res # Invert result

			if dest[0] == "1":
				self.set_value(self.d_reg, res, "D")
			if dest[1] == "1":
				self.set_value(self.a_reg, res, "A")
			if dest[2] == "1":
				self.set_value(self.memory, res, "M")

			conditions = (res > 0, res == 0, res < 0)
			jump = False

			for i in range(3):
				if int(jumps[i]) & int(conditions[i]):
					jump = True

			if jump:
				self.program_counter = self.a_reg_value
			else:
				self.program_counter += 1

		elif op_code == "01": # I/O instruction
			if current_inst[13] == "1": # Output
				val = int(current_inst[0])
				x = self.memory_value[Compiler().x_addr]
				y = self.memory_value[Compiler().y_addr]
				
				pixel: QLabel = getattr(self, f"px[{x}][{y}]")
				
				if val == 0:
					pixel.setStyleSheet("background-color: rgb(117, 76, 19); border: 1px solid rgb(89, 52, 0);")
					if (x, y) in self.lit_pixels: self.lit_pixels.remove((x, y))
				else:
					pixel.setStyleSheet("background-color: rgb(255, 225, 115); border: 1px solid rgb(204, 171, 51);")
					self.lit_pixels.append((x, y))
			
			self.program_counter += 1
		
		else:
			raise Exception(f"Unknown instruction: {current_inst}")

		return False

	def run(self, code: str, max_steps: int|None = None):
		NOOP = "0" * 16

		PROM = code.strip().splitlines()
		PROM.extend([NOOP] * (MAX_INSTRUCTIONS - len(PROM)))

		self.program_counter = 0
		steps: int = 0

		self.set_value(self.a_reg, 0, "A")
		self.set_value(self.d_reg, 0, "D")
		self.set_value(self.memory, 0, "M")

		# Clear screen
		for x, y in self.lit_pixels:
			pixel: QLabel = getattr(self, f"px[{x}][{y}]")
			pixel.setStyleSheet("background-color: rgb(117, 76, 19); border: 1px solid rgb(89, 52, 0)")
		
		self.lit_pixels.clear()
		if not PROM: return False

		while not self.step(PROM): # step() function returns True when encountering a HALT instruction
			steps += 1
			if max_steps != None and steps > max_steps:
				return True # Timeout has occurred

		return False

if __name__ == "__main__":
	app = QApplication([])
	main = Main()

	main.show()
	app.exec()
