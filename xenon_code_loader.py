import mcschematic

def load_from_prom(PROM: list[str]) -> mcschematic.MCSchematic:
	x: int = -2
	z: int = 0
	schem = mcschematic.MCSchematic()

	for i, line in enumerate(PROM):
		# Next instruction -> +X
		# Next 128 instruction -> -Z
		# Coordinates are relative

		x += 2

		# The offsets are due ot the PROM design
		if i != 0:
			if i % 256 == 0:
				x = 0
				z -= 2
			elif i % 128 == 0:
				x = 0
				z -= 10
			elif i % 64 == 0:
				x += 2
		
		for j, char in enumerate(line):
			if len(line) != 16:
				raise Exception(f"Expected a 16-bit instruction in line {i}.")
		
			position = (x, -2 * j, z)
			if char == "0":
				schem.setBlock(position, "minecraft:purple_stained_glass")
			if char == "1":
				direction = "north" if i % 256 < 128 else "south"
				schem.setBlock(position, f"minecraft:repeater[facing={direction}]")
		
	return schem


fn: str = input("Enter the file name of the program: ")
try:
	file = open(f"binary/{fn}", "r")
except FileNotFoundError:
	print(f"The path 'binary/{fn}' does not exist.")
else:
	program_memory: list[str] = file.read().splitlines()
	program = load_from_prom(program_memory)
	program.save("schematics", fn.replace(".bin", ""), mcschematic.Version.JE_1_19_4)
	file.close()