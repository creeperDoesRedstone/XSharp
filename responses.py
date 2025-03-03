# This file is for Discord bots that interface with the compiler.

from xsharp_shell import xs_compile
from xasm_assembler import assemble
from xenon_vm import Main
from screen_writer import write_screen
import re

from PyQt6.QtWidgets import QApplication

SUCCESS = 0
ERROR = 1

def get_response(user_input: str) -> tuple[str, int, bool]:
	# Compile X# into XAssembly
	if re.findall(r"\$xs_compile\n?```\n(.*\n?)*?```", user_input):
		code: str = "\n".join(user_input.replace("```", "").splitlines()[1:])
		result, error = xs_compile("<code>", code)
		
		if error:
			return repr(error), ERROR, False
		return "\n".join(result), SUCCESS, False
	elif user_input.startswith("$xs_compile") and user_input.count("```") != 2:
		return "Compilation requires a code block!", ERROR, False
	
	# Compile X# into XAssembly but remove that one line
	if re.findall(r"\$xs_rcompile\n?```\n(.*\n?)*?```", user_input):
		code: str = "\n".join(user_input.replace("```", "").splitlines()[1:])
		result, error = xs_compile("<code>", code, True)
		
		if error:
			return repr(error), ERROR, False
		return "\n".join(result), SUCCESS, False
	elif user_input.startswith("$xs_rcompile") and user_input.count("```") != 2:
		return "Compilation requires a code block!", ERROR, False
	
	# Compile XAssembly to Xenon's machine code
	if re.findall(r"\$xs_assemble\n?```\n(.*\n?)*?```", user_input):
		assembly: str = "\n".join(user_input.replace("```", "").splitlines()[1:])
		result = assemble(assembly)

		if isinstance(result, list):
			return "\n".join(result), SUCCESS, False
		return repr(result), ERROR, False
	elif user_input.startswith("$xs_assemble") and user_input.count("```") != 2:
		return "Assembly requires a code block!", ERROR, False
	
	# Compile X# directly to machine code
	if re.findall(r"\$xs_compile_assemble\n?```\n(.*\n?)*?```", user_input):
		code: str = "\n".join(user_input.replace("```", "").splitlines()[1:])
		result, error = xs_compile("<code>", code)
		if error:
			return repr(error), ERROR, False
		
		assembly: str = "\n".join(result)
		result = assemble(assembly)

		if isinstance(result, list):
			return "\n".join(result), SUCCESS, False
		return repr(result), ERROR, False
	elif user_input.startswith("$xs_compile_assemble") and user_input.count("```") != 2:
		return "Compilation requires a code block!", ERROR, False
	
	# Compile X# directly to machine code but remove that one line
	if re.findall(r"\$xs_rcompile_assemble\n?```\n(.*\n?)*?```", user_input):
		code: str = "\n".join(user_input.replace("```", "").splitlines()[1:])
		result, error = xs_compile("<code>", code, True)
		if error:
			return repr(error), ERROR, False
		
		assembly: str = "\n".join(result)
		result = assemble(assembly)

		if isinstance(result, list):
			return "\n".join(result), SUCCESS, False
		return repr(result), ERROR, False
	elif user_input.startswith("$xs_rcompile_assemble") and user_input.count("```") != 2:
		return "Compilation requires a code block!", ERROR, False
	
	# Run Xenon's machine code
	if re.findall(r"\$xs_run\n?```\n(.*\n?)*?```", user_input):
		machine_code: str = "\n".join(user_input.replace("```", "").splitlines()[1:])

		# Create a new virtual machine
		app = QApplication([])
		vm = Main()
		vm.program_counter = 0

		if "0000000000000100" not in machine_code:
			return f"HALT instruction ({'0' * 13}100) not found!", ERROR, False
		
		timeout = vm.run(machine_code, 16384)
		if timeout:
			return "Timeout Error", ERROR, False
		
		result: str = vm.a_reg.text()
		result += f"\n{vm.d_reg.text()}"
		result += f"\n{vm.memory.text()}"

		if vm.lit_pixels:
			write_screen(vm.lit_pixels)

		return result, SUCCESS, len(vm.lit_pixels) > 0
	elif user_input.startswith("$xs_run") and user_input.count("```") != 2:
		return "Running Xenon's machine code requires a code block!", ERROR, False

	return "", ERROR, False
