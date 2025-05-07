from PyQt6.QtWidgets import QMainWindow, QApplication, QLabel, QPushButton, QFileDialog, QSlider
from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor
from PyQt6.QtCore import QRegularExpression, QTimer
from PyQt6 import uic

from xsharp_compiler import Compiler
from screen_writer import write_screen

MAX_INSTRUCTIONS = 2 ** 12

class BinSyntaxHighlighter(QSyntaxHighlighter):
	def __init__(self, document):
		super().__init__(document)
		self.highlighting_rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

		self.create_format("comp_inst", QColor(120, 174, 255))
		self.create_format("load_inst", QColor(255, 170, 0))
		self.create_format("halt_inst", QColor(255, 150, 150), True)
		self.create_format("plot_inst", QColor(255, 225, 115), italic=True)
		self.create_format("plot_inst_off", QColor(117, 76, 19), italic=True)
		self.create_format("buffer_inst", QColor(213, 117, 157))

		self.add_rule(r"\b\d{14}10$\b", "load_inst")
		self.add_rule(r"\b\d{14}11$\b", "comp_inst")
		self.add_rule(r"\b\d{12}1101$\b", "plot_inst")
		self.add_rule(r"\b\d{12}0101$\b", "plot_inst_off")
		self.add_rule(r"\b\d{13}001\b", "buffer_inst")
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

class VirtualMachine(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setFixedSize(800, 600)
		self.init_GUI()
		self.init_memory()
		self.init_screen(48, 28)

	def init_GUI(self):
		uic.loadUi("GUI/vm.ui", self)
		self.process_button: QPushButton
		self.process_button.clicked.connect(lambda: self.run(self.file_text.toPlainText()))
		self.program_counter = 0

		self.step_button.clicked.connect(lambda: self.step(
			self.file_text.toPlainText().strip().splitlines()
		))

		self.export_button.clicked.connect(lambda: write_screen(self.screen))

		self.load_file_button.clicked.connect(self.load_file)

		self.file_text.setAcceptRichText(False)
		self.highlighter = BinSyntaxHighlighter(self.file_text.document())

		self.clock_speed: QSlider
		self.clock_speed_label: QLabel
		self.clock_speed.installEventFilter(self)

		self.run_timer = QTimer(self)
		self.run_timer.timeout.connect(lambda: self.run_step(
			self.file_text.toPlainText().strip().splitlines(), None
		))
		self.steps = 0

	def init_memory(self):
		self.memory_value = [0] * (Compiler.INPUT_ADDR + 1)
		self.call_stack: list[int] = []
		
		self.a_reg_value = 0
		self.d_reg_value = 0

		self.set_value(self.a_reg, 0, "A")
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

		self.screen: list[tuple[int, int]] = []
		self.buffer: list[tuple[int, int]] = []

		for x in range(self.screen_length):
			for y in range(self.screen_width):
				setattr(self, f"px[{x}][{y}]", QLabel(text="", parent=self))
				pixel: QLabel = getattr(self, f"px[{x}][{y}]")
				pixel.setObjectName(f"px[{x}][{y}]")

				pixel.setStyleSheet("background-color: rgb(117, 76, 19); border: 1px solid rgb(89, 52, 0)")
				pixel.setGeometry(x * self.PIXEL_SIZE + 12, 508 - y * self.PIXEL_SIZE, self.PIXEL_SIZE, self.PIXEL_SIZE)

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
			if self.a_reg_value >= 0 and self.a_reg_value < len(self.memory_value):
				self.memory.setText(f"M: {self.memory_value[self.a_reg_value]}")
			else:
				self.memory.setText(f"M: Unmapped")
		
		elif kind == "D":
			self.d_reg_value = value
		
		elif kind == "M" and self.a_reg_value >= 0 and self.a_reg_value < len(self.memory_value):
			self.memory_value[self.a_reg_value] = value

	def step(self, PROM: list[str]):
		NOOP = "0" * 16
		HALT = "0000000000000100"

		current_inst = PROM[self.program_counter]
		self.current_inst.setText(f"Instruction: {self.program_counter}")
		self.branch.setText("Branch not taken")

		op_code = current_inst[-2:]

		def raise_error(details: str):
			error_message = f"Instruction {self.program_counter}:\n{current_inst}\n{details}"
			raise Exception(error_message)

		if current_inst == NOOP:
			self.program_counter += 1
		
		elif current_inst == HALT:
			return True
		
		elif op_code == "00": # System instructions
			instruction: str = current_inst[12:14]
			match instruction:
				case "00": # NOOP
					self.program_counter += 1
				case "01": # HALT
					return True
				case "10": # CALL
					self.call_stack.append(self.program_counter + 1)
					if len(self.call_stack) >= 16: raise_error("Stack overflow!")

					address = int("0b" + current_inst[0:12], 2)
					self.program_counter = address
				case "11": # RETN
					if not self.call_stack: raise_error("Stack underflow!")
					address = self.call_stack.pop()

					self.program_counter = address

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
			A = self.a_reg_value if code[0] == "1" else self.memory_value[self.a_reg_value] if self.a_reg_value >= 0 and self.a_reg_value < len(self.memory_value) else 0
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
				if code[7] == "1": res >>= 1 # Right shift
			
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
				self.branch.setText("Branch taken")
			else:
				self.program_counter += 1

		elif op_code == "01": # I/O instruction
			ON_STYLESHEET: str = "background-color: rgb(255, 225, 115); border: 1px solid rgb(204, 171, 51);"
			OFF_STYLESHEET: str = "background-color: rgb(117, 76, 19); border: 1px solid rgb(89, 52, 0);"
			if current_inst[13] == "1": # Plot
				val = int(current_inst[12])
				x = self.memory_value[Compiler().X_ADDR]
				y = self.memory_value[Compiler().Y_ADDR]

				if x < 0: raise_error("X value cannot be negative!")
				if x >= 48: raise_error("X value cannot be greater than 47!")
				if y < 0: raise_error("Y value cannot be negative!")
				if y >= 28: raise_error("Y value cannot be greater than 27!")
				
				if val == 0:
					if (x, y) in self.buffer: self.buffer.remove((x, y))
				else:
					if (x, y) not in self.buffer: self.buffer.append((x, y))
			else: # Update buffer
				op_code = current_inst[11:13]

				if op_code[1] == "0":
					for x, y in self.screen:
						pixel: QLabel = getattr(self, f"px[{x}][{y}]")
						pixel.setStyleSheet(OFF_STYLESHEET)
					self.screen = self.buffer
					for x, y in self.screen:
						pixel: QLabel = getattr(self, f"px[{x}][{y}]")
						pixel.setStyleSheet(ON_STYLESHEET)

				if op_code[0] == "1":
					self.buffer = []
			
			self.program_counter += 1
		
		else:
			raise Exception(f"Unknown instruction: {current_inst}")

		return False

	def run_step(self, PROM: list[str], max_steps: int|None = None):
		halted: bool = self.step(PROM)
		self.steps += 1

		if halted:
			self.run_timer.stop()
		elif max_steps is not None and self.steps >= max_steps:
			self.run_timer.stop()

	def run(self, code: str, max_steps: int|None = None):
		NOOP = "000000000000"

		PROM = code.strip().splitlines()
		PROM.extend([NOOP] * (MAX_INSTRUCTIONS - len(PROM)))

		self.program_counter = 0
		self.steps = 0

		self.set_value(self.a_reg, 0, "A")
		self.set_value(self.d_reg, 0, "D")
		self.set_value(self.memory, 0, "M")

		# Clear screen
		for x, y in self.screen:
			pixel: QLabel = getattr(self, f"px[{x}][{y}]")
			pixel.setStyleSheet("background-color: rgb(117, 76, 19); border: 1px solid rgb(89, 52, 0)")
		
		self.screen.clear()
		self.buffer.clear()
		if not PROM: return False

		if self.clock_speed.value() > 0:
			interval_ms = int(1000 / self.clock_speed.value())
			self.run_timer.start(interval_ms)
		else:
			while not self.step(PROM): # step() function returns True when encountering a HALT instruction
				self.steps += 1
				if max_steps != None and self.steps > max_steps:
					return True # Timeout has occurred

		return False

	def eventFilter(self, a0, a1):
		if a0 == self.clock_speed:
			value = self.clock_speed.value()
			self.clock_speed_label.setText(f"Clock speed: {str(value)+'Hz' if value > 0 else 'Instant'}")
		return super().eventFilter(a0, a1)

if __name__ == "__main__":
	app = QApplication([])
	main = VirtualMachine()

	main.show()
	app.exec()
