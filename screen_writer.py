import png

PIXEL_SIZE = 8
WIDTH = 48 * PIXEL_SIZE
HEIGHT = 28 * PIXEL_SIZE

def write_screen(lit_pixels: list[tuple[int, int]]):
	img = []
	for y in range(HEIGHT):
		row = ()
		for x in range(WIDTH):
			pixel = (x // PIXEL_SIZE, 27 - y // PIXEL_SIZE)
			if pixel in lit_pixels:
				row += (255, 225, 115)
			else:
				row += (117, 76, 19)
		img.append(row)
	
	with open('screen.png', 'wb') as f:
		w = png.Writer(WIDTH, HEIGHT, greyscale=False)
		w.write(f, img)

if __name__ == "__main__":
	write_screen([
		(1, 2),
		(5, 2),
		(2, 1),
		(3, 1),
		(4, 1),
		(2, 4),
		(2, 5),
		(4, 4),
		(4, 5)
	])
