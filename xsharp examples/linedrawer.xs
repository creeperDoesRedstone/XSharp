// Bresenham's line drawing algorithm!
const x1 5
const y1 5
const x2 30
const y2 21
var x: int = x1
var y: int = y1
var dx: int = #(x2 - x1)
var dy: int = #(y2 - y1)
const s1 $(x2 - x1)
const s2 $(y2 - y1)

var interchange: int = 0
var temp: int
if dy > dx {
	temp = dx
	dx = dy
	dy = temp
	interchange = 1
}

var a: int = dy + dy
var e: int = a - dx
var b: int = e - dx
var i: int

plot(x, y, 1)

for i start: 0 end: dx step: 1 {
	if e < 0 {
		if interchange == 1 {
			y = y + s2
		} else {
			x = x + s1
		}
		e = e + a
	} else {
		y = y + s2
		x = x + s1
		e = e + b
	}
	plot(x, y, 1)
	update()
}
