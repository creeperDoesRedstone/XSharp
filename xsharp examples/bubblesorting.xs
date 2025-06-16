const length 10
var array: int[10] = [7, 2, 1, 6, 10, 9, 4, 3, 8, 5]
var i: int
var j: int
var temp: int

// Plot starting array
for i start: 0 end: length step: 1 {
	for j start: 0 end: array[i] step: 1 {
		plot(i, j, 1)
	}
}
flip()

// Sort
for i start: length-- end: 0 step: -1 {
	for j start: 0 end: i step: 1 {
		if array[j] > array[j++] {
			// Swap
			temp = array[j]
			array[j] = array[j++]
			array[j++] = temp
		}
	}
}

// Plot resulting array
for i start: 0 end: length step: 1 {
	for j start: 0 end: array[i] step: 1 {
		plot(i, j, 1)
	}
}
flip()
