from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QTextCursor, QClipboard, QIcon
from PyQt6.QtCore import QRegularExpression, Qt, QEvent
from PyQt6.QtWidgets import QMainWindow, QApplication, QFileDialog, QTextEdit, QPushButton, QCompleter
from PyQt6 import uic

from xsharp_lexer import Lexer, KEYWORDS, DATA_TYPES
from xsharp_parser import Parser
from xsharp_compiler import Compiler
from xasm_assembler import ASMSyntaxHighlighter

def xs_compile(fn: str, ftxt: str, remove_that_one_line: bool = False):
    lexer = Lexer(fn, ftxt)
    tokens, error = lexer.lex()
    if error:
        return None, error

    parser = Parser(tokens)
    ast = parser.parse()
    if ast.error:
        return None, ast.error

    compiler = Compiler()
    res = compiler.compile(ast.node, remove_that_one_line)
    return res.value, res.error

class SyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.highlighting_rules = []

    def create_format(self, name: str, color: QColor, bold: bool = False, italic: bool = False):
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if italic:
            fmt.setFontItalic(True)
        setattr(self, f"{name}_format", fmt)

    def get_format(self, name: str):
        return getattr(self, f"{name}_format")

    def add_rule(self, pattern: str, format_name: str):
        self.highlighting_rules.append((QRegularExpression(pattern), self.get_format(format_name)))

    def highlightBlock(self, text: str):
        for _pattern, _format in self.highlighting_rules:
            match_iterator = _pattern.globalMatch(text)
            while match_iterator.hasNext():
                _match = match_iterator.next()
                self.setFormat(_match.capturedStart(), _match.capturedLength(), _format)

class XSharpSyntaxHighlighter(SyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)

        self.create_format("keyword", QColor(213, 117, 157), bold=True)
        self.create_format("keyword2", QColor(217, 101, 50), italic=True)
        self.create_format("operation", QColor(213, 117, 157), bold=True)
        self.create_format("brackets", QColor(247, 217, 27))
        self.create_format("comment", QColor(98, 133, 139), italic=True)
        self.create_format("number", QColor(85, 91, 239))

        # Exclude "true" and "false" from the general keywords rule using negative lookahead.
        self.add_rule(r"\b(?!(?:true|false)\b)(?:" + r"|".join(KEYWORDS) + r")\b", "keyword")
        
        self.add_rule(r'\b(?:true|false)\b', "keyword2")
        self.add_rule(r"\b(start|end|step)\b", "keyword2")
        self.add_rule(r"\b" + r"\b|\b".join(DATA_TYPES) + r"\b", "keyword2")
        self.add_rule(r"\b\d+(\.\d+)?\b", "number")
        self.add_rule(r"(\+|-|&|\||~|\^|=|:)", "operation")
        self.add_rule(r"\(|\)|\{|\}|\[|\]", "brackets")
        self.add_rule(r"//[^\n]*", "comment")

class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("GUI/shell.ui", self)
        self.setWindowTitle("X# Compiler")
        
        # Connect buttons and initialize variables.
        self.load_file_button.clicked.connect(self.load_file)
        self.fn = ""
        self.file_name.setPlaceholderText("File name...")
        self.process_button.clicked.connect(self.compile)
        self.process_button.clicked.connect(self.copy_to_clipboard)
        
        # Setup syntax highlighting.
        self.xsharp_text_highlighter = XSharpSyntaxHighlighter(self.file_text.document())
        self.file_text.installEventFilter(self)
        self.file_text.setAcceptRichText(False)
        
        self.result.setReadOnly(True)
        self.result.installEventFilter(self)
        self.result_highlighter = ASMSyntaxHighlighter(self.result.document())
        
        self.completer = QCompleter(KEYWORDS, self.file_text)
        self.completer.setWidget(self.file_text)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.activated.connect(self.insert_completion)

        popup = self.completer.popup()
        popup.setStyleSheet(
            "QListView {"
            "   background-color: #2b2b2b;"
            "   color: #f8f8f2;"
            "   font-family: Consolas, monospace;"
            "   font-size: 12px;"
            "   border: 1px solid #3d7aee;"
            "   border-radius: 5px;"
            "}"
            "QListView::item:selected {"
            "   background-color: #3d7aee;"
            "   color: #ffffff;"
            "}"
        )
    
    def insert_completion(self, completion: str):
        tc = self.file_text.textCursor()
        tc.movePosition(QTextCursor.MoveOperation.StartOfWord, QTextCursor.MoveMode.KeepAnchor)
        tc.insertText(completion)
        self.file_text.setTextCursor(tc)
    
    def load_file(self):
        self.fn, _ = QFileDialog.getOpenFileName(self, "Open file", "programs", "X# Files (*.xs)")
        if not self.fn:
            return
        
        self.file_name.setText(self.fn.split("/")[-1])
        self.file_name.setReadOnly(True)
        
        with open(self.fn, "r") as f:
            self.file_text.setText(f.read())
    
    def eventFilter(self, source, event):
        code_cursor = self.file_text.textCursor()
        cursor_pos = code_cursor.position()
        code = self.file_text.toPlainText()
        
        if source == self.file_text:
            self.ftxt_line_count.setText(
                f"Line count: {len(self.file_text.toPlainText().splitlines())}"
            )
        
        if source == self.file_text and event.type() == QEvent.Type.KeyPress:
            # --- Basic Intellisense (Completion) Logic ---
            if event.key() == Qt.Key.Key_Tab:
                if self.completer.popup().isVisible():
                    index = self.completer.popup().currentIndex()
                    if index.isValid():
                        self.insert_completion(index.data())
                        return True
                    
                tc = self.file_text.textCursor()
                tc.select(QTextCursor.SelectionType.WordUnderCursor)
                prefix = tc.selectedText()
                if prefix:
                    matches = [word for word in KEYWORDS if word.lower().startswith(prefix.lower())]
                    if matches:
                        if len(matches) == 1:
                            tc.removeSelectedText()
                            tc.insertText(matches[0])
                            self.file_text.setTextCursor(tc)
                        else:
                            self.completer.setCompletionPrefix(prefix)
                            cr = self.file_text.cursorRect()
                            cr.setWidth(self.completer.popup().sizeHintForColumn(0) +
                                        self.completer.popup().verticalScrollBar().sizeHint().width())
                            self.completer.complete(cr)
                        return True
                return super().eventFilter(source, event)
            # --- End Intellisense ---
            
            # Toggle comment on Ctrl+Slash.
            if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Slash:
                if not code_cursor.hasSelection():
                    code_cursor.select(QTextCursor.SelectionType.LineUnderCursor)
                
                selection_start = code_cursor.selectionStart()
                selection_end = code_cursor.selectionEnd()
                
                # Normalize selection to full lines.
                code_cursor.setPosition(selection_start)
                code_cursor.movePosition(code_cursor.MoveOperation.StartOfBlock, code_cursor.MoveMode.KeepAnchor)
                selection_start = code_cursor.selectionStart()
                
                code_cursor.setPosition(selection_end)
                code_cursor.movePosition(code_cursor.MoveOperation.EndOfBlock, code_cursor.MoveMode.KeepAnchor)
                selection_end = code_cursor.selectionEnd()
                
                code_cursor.setPosition(selection_start)
                code_cursor.setPosition(selection_end, code_cursor.MoveMode.KeepAnchor)
                selected_text = code_cursor.selection().toPlainText()
                lines = selected_text.splitlines()
                for i, line_text in enumerate(lines):
                    line_text = line_text.strip()
                    if line_text.startswith("// "):
                        lines[i] = line_text.lstrip().replace("// ", "", 1)
                    elif line_text.startswith("//"):
                        lines[i] = line_text.lstrip().replace("//", "", 1)
                    else:
                        lines[i] = "// " + line_text
                updated_text = "\n".join(lines)
                code_cursor.insertText(updated_text)
                return True
            
            if event.key() == Qt.Key.Key_ParenLeft:
                code_cursor.insertText("()")
                code_cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
                self.file_text.setTextCursor(code_cursor)
                return True
            
            if event.key() == Qt.Key.Key_ParenRight:
                if cursor_pos > 0 and cursor_pos < len(code) and code[cursor_pos] == ")":
                    code_cursor.movePosition(QTextCursor.MoveOperation.Right)
                    self.file_text.setTextCursor(code_cursor)
                    return True
                return super().eventFilter(source, event)
            
            if event.key() == Qt.Key.Key_BraceLeft:
                code_cursor.insertText("{}")
                code_cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
                self.file_text.setTextCursor(code_cursor)
                return True
            
            if event.key() == Qt.Key.Key_BraceRight:
                if cursor_pos > 0 and cursor_pos < len(code) and code[cursor_pos] == "}":
                    code_cursor.movePosition(QTextCursor.MoveOperation.Right)
                    self.file_text.setTextCursor(code_cursor)
                    return True
                return super().eventFilter(source, event)
            
            if event.key() == Qt.Key.Key_BracketLeft:
                code_cursor.insertText("[]")
                code_cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
                self.file_text.setTextCursor(code_cursor)
                return True
            
            if event.key() == Qt.Key.Key_BracketRight:
                if cursor_pos > 0 and cursor_pos < len(code) and code[cursor_pos] == "]":
                    code_cursor.movePosition(QTextCursor.MoveOperation.Right)
                    self.file_text.setTextCursor(code_cursor)
                    return True
                return super().eventFilter(source, event)
            
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                lines = code.splitlines()
                tabs_num = 0
                if code_cursor.blockNumber() >= len(lines):
                    return super().eventFilter(source, event)
                
                for i in lines[code_cursor.blockNumber()]:
                    if i != "\t":
                        break
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
    
    def copy_to_clipboard(self):
        text = self.result.toPlainText()
        if text:
            QApplication.clipboard().setText(text, QClipboard.Mode.Clipboard)
    
    def compile(self):
        self.error.setText("")
        self.result.setText("")
        result, error = xs_compile("<shell>", self.file_text.toPlainText().strip())
        if error:
            self.error.setText(f"{error}")
        else:
            assembly = "\n".join(result)
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
