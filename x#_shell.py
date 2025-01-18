from xenon_xsharp import Lexer, Parser, Compiler
from os import system

MAX_INSTRUCTIONS = 2 ** 14

def run(fn: str, ftxt: str):
	lexer = Lexer(fn, ftxt)
	tokens, error = lexer.lex()
	if error: return None, error

	parser = Parser(tokens)
	ast = parser.parse()
	if ast.error: return None, ast.error

	compiler = Compiler()
	res = compiler.visit(ast.node)
	return res.value, res.error

print("\t--- X# COMPILER ---")

while True:
	ftxt: str = input(">>> ").strip()
	if ftxt == "":
		continue

	if ftxt == "exit":
		break

	if ftxt == "clear":
		system("cls")
		print("\t--- X# COMPILER ---")
		continue

	result, error = run("<stdin>", ftxt)
	if error:
		print(error)
	else:
		print("\n".join(result[:MAX_INSTRUCTIONS-1] + ["HALT"]) + "\n")