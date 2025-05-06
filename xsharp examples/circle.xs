const radius 13
const xc 23
const yc 13

var x: int = 0
var y: int = radius
var d: int = 1 - radius  // Initial decision variable

// Function to plot all 8 symmetric points
sub plot_points() {
	plot xc + x yc + y 1
	plot xc - x yc + y 1
	plot xc + x yc - y 1
	plot xc - x yc - y 1
	plot xc + y yc + x 1
	plot xc - y yc + x 1
	plot xc + y yc - x 1
	plot xc - y yc - x 1
	update()
}

plot_points()
while y - x {
	x = x++
	if d < 0 {
		d = d + (x << 1) + 1 // d = d + 2x + 1
	} else {
		y = y--
		d = d + ((x - y) << 1) + 1 // d = d + 2(x - y) + 1
	}

	plot_points()
}
