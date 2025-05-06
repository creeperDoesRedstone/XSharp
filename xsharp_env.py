from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QTextEdit
from PyQt6.QtGui import QTextCursor
from PyQt6.QtCore import QObject, QEvent, QRegularExpression, Qt
from PyQt6 import uic

from xsharp_shell import xs_compile, XSharpSyntaxHighlighter
from xasm_assembler import assemble
from xenon_code_loader import load_from_prom

from mcschematic import Version

class Environment(QMainWindow):
	def __init__(self):
		super().__init__()
		uic.loadUi("GUI/shell.ui", self)
		self.setWindowTitle("X# Environment")

		self.load_file_button.clicked.connect(self.load_file)
		self.process_button.clicked.connect(self.compile)

		self.file_text: QTextEdit
		self.xsharp_text_highlighter = XSharpSyntaxHighlighter(self.file_text.document())
		self.file_text.installEventFilter(self)
		self.file_text.setAcceptRichText(False)

		self.result.setReadOnly(True)
		self.result.installEventFilter(self)
	
	def load_file(self):
		self.fn, _ = QFileDialog.getOpenFileName(self, "Open file", "programs", "X# Files (*.xs)")
		if not self.fn: return

		self.file_name.setText(self.fn.split("/")[-1])
		self.file_name.setReadOnly(True)
	
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
				self.xsharp_text_highlighter.highlighting_rules[4] = (QRegularExpression(
					r"(\+|-|\*|/|&|\||~|\^|=|:|#|\$)"
				), getattr(self.xsharp_text_highlighter, "operation_format"))
			else:
				self.xsharp_text_highlighter.highlighting_rules[4] = (QRegularExpression(
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
			return
		
		assembly: str = "\n".join(result)
		result = assemble(assembly)
		if isinstance(result, Exception):
			self.error.setText(f"{result}")
			return
		
		self.result.setText("\n".join(result))
		
		if self.file_name.text():
			with open(f"binary/{self.file_name.text().replace('.xs', '.bin')}", "w") as f:
				f.write("\n".join(result))
			with open(f"assembly/{self.file_name.text().replace('.xs', '.xasm')}", "w") as f:
				f.write(assembly)
			with open(f"programs/{self.file_name.text()}", "w") as f:
				f.write(self.file_text.toPlainText())
			
			program_schem = load_from_prom(result)
			program_schem.save("schematics", self.file_name.text(), Version.JE_1_19_4)

			self.fn = ""

if __name__ == "__main__":
	app = QApplication([])
	env = Environment()

	env.show()
	app.exec()
