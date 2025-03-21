# This file is for Discord bots that interface with the compiler, assembler, and VM.

from xsharp_shell import xs_compile
from xasm_assembler import assemble
from xenon_vm import VirtualMachine
from screen_writer import write_screen
from typing import Literal
from enum import Enum
import re

from PyQt6.QtWidgets import QApplication

class Responses(Enum):
	SUCCESS = 0
	ERROR = 1
	HELP = 2

def get_response(user_input: str) -> tuple[str, Literal[Responses.SUCCESS, Responses.ERROR, Responses.HELP], bool]:
	user_input = user_input.strip()

	# Help command
	if user_input == "$xs_help":
		help_message: str =\
		"""Here are my commands:
- `$xs_help`: Shows this message.
- `$xs_compile`: Compiles X# Code to XAssembly.
- `$xs_rcompile`: Same as above, but removes the last line.
- `$xs_assemble`: Assembles XAssmebly to Xenon's machine code.
- `$xs_compile_assemble`: Compiles X# Code directly to Xenon's machine code.
- `$xs_rcompile_assemble`: Same as above, but removes the last line.
- `$xs_run`: Runs Xenon's machine code.
- `$xs_runcode`: Runs X# Code directly.
- `$xs_repo`: Shows the X# repository.
"""
		return help_message, Responses.HELP, False
	
	if user_input == "$xs_repo":
		return "[X# Repository](<https://github.com/creeperDoesRedstone/XSharp/tree/main>)", Responses.HELP, False

	# Compile X# into XAssembly
	if re.findall(r"\$xs_compile\n?```\n(.*\n?)*?```", user_input):
		code: str = "\n".join(user_input.replace("```", "").splitlines()[1:])
		result, error = xs_compile("<code>", code)
		
		if error:
			return repr(error), Responses.ERROR, False
		return "\n".join(result), Responses.SUCCESS, False
	elif user_input.startswith("$xs_compile") and user_input.count("```") != 2:
		return "Compilation requires a code block!", Responses.ERROR, False
	
	# Compile X# into XAssembly but remove that one line
	if re.findall(r"\$xs_rcompile\n?```\n(.*\n?)*?```", user_input):
		code: str = "\n".join(user_input.replace("```", "").splitlines()[1:])
		result, error = xs_compile("<code>", code, True)
		
		if error:
			return repr(error), Responses.ERROR, False
		return "\n".join(result), Responses.SUCCESS, False
	elif user_input.startswith("$xs_rcompile") and user_input.count("```") != 2:
		return "Compilation requires a code block!", Responses.ERROR, False
	
	# Compile XAssembly to Xenon's machine code
	if re.findall(r"\$xs_assemble\n?```\n(.*\n?)*?```", user_input):
		assembly: str = "\n".join(user_input.replace("```", "").splitlines()[2:])
		result = assemble(assembly)

		if isinstance(result, list):
			return "\n".join(result), Responses.SUCCESS, False
		return repr(result), Responses.ERROR, False
	elif user_input.startswith("$xs_assemble") and user_input.count("```") != 2:
		return "Assembly requires a code block!", Responses.ERROR, False
	
	# Compile X# directly to machine code
	if re.findall(r"\$xs_compile_assemble\n?```\n(.*\n?)*?```", user_input):
		code: str = "\n".join(user_input.replace("```", "").splitlines()[1:])
		result, error = xs_compile("<code>", code)
		if error:
			return repr(error), Responses.ERROR, False
		
		assembly: str = "\n".join(result)
		result = assemble(assembly)

		if isinstance(result, list):
			return "\n".join(result), Responses.SUCCESS, False
		return repr(result), Responses.ERROR, False
	elif user_input.startswith("$xs_compile_assemble") and user_input.count("```") != 2:
		return "Compilation requires a code block!", Responses.ERROR, False
	
	# Compile X# directly to machine code but remove that one line
	if re.findall(r"\$xs_rcompile_assemble\n?```\n(.*\n?)*?```", user_input):
		code: str = "\n".join(user_input.replace("```", "").splitlines()[1:])
		result, error = xs_compile("<code>", code, True)
		if error:
			return repr(error), Responses.ERROR, False
		
		assembly: str = "\n".join(result)
		result = assemble(assembly)

		if isinstance(result, list):
			return "\n".join(result), Responses.SUCCESS, False
		return repr(result), Responses.ERROR, False
	elif user_input.startswith("$xs_rcompile_assemble") and user_input.count("```") != 2:
		return "Compilation requires a code block!", Responses.ERROR, False
	
	# Run Xenon's machine code
	if re.findall(r"\$xs_run\n?```\n(.*\n?)*?```", user_input):
		machine_code: str = "\n".join(user_input.replace("```", "").splitlines()[1:])

		# Create a new virtual machine
		app = QApplication([])
		vm = VirtualMachine()
		vm.program_counter = 0

		if "0000000000000100" not in machine_code:
			return f"HALT instruction ({'0' * 13}100) not found!", Responses.ERROR, False
		
		try:
			timeout = vm.run(machine_code, 100_000)
			if timeout:
				return "Timeout Error", Responses.ERROR, False
			
			result: str = vm.a_reg.text()
			result += f"\n{vm.d_reg.text()}"
			result += f"\n{vm.memory.text()}"

			if vm.lit_pixels:
				write_screen(vm.lit_pixels)

			return result, Responses.SUCCESS, len(vm.lit_pixels) > 0
		
		except Exception as e:
			return f"{e}", Responses.ERROR, False
	elif user_input.startswith("$xs_run") and user_input.count("```") != 2:
		return "Running Xenon's machine code requires a code block!", Responses.ERROR, False

	# Run X# directly
	if re.findall(r"\$xs_runcode\n?```\n(.*\n?)*?```", user_input):
		code: str = "\n".join(user_input.replace("```", "").splitlines()[1:])
		result, error = xs_compile("<code>", code)
		if error:
			return repr(error), Responses.ERROR, False
		
		assembly: str = "\n".join(result)
		machine_code: list[str] = assemble(assembly)

		if not isinstance(result, list):
			return repr(result), Responses.ERROR, False
		
		machine_code: str = "\n".join(machine_code)

		# Create a new virtual machine
		app = QApplication([])
		vm = VirtualMachine()
		vm.program_counter = 0

		if "0000000000000100" not in machine_code:
			return f"HALT instruction ({'0' * 13}100) not found!", Responses.ERROR, False
		
		try:
			timeout = vm.run(machine_code, 100_000)
			if timeout:
				return "Timeout Error", Responses.ERROR, False
			
			result: str = f"Result: {vm.d_reg_value}"

			if vm.lit_pixels:
				write_screen(vm.lit_pixels)

			return result, Responses.SUCCESS, len(vm.lit_pixels) > 0
		
		except Exception as e:
			return f"{e}", Responses.ERROR, False
	elif user_input.startswith("$xs_runcode") and user_input.count("```") != 2:
		return "Running X# requires a code block!", Responses.ERROR, False

	return None, Responses.ERROR, False
