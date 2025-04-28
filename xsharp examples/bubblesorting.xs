var array: int[10] = {7, 2, 1, 6, 10, 9, 4, 3, 8, 5}
const length 10

var i: int = 0
var j: int = 0
var temp: int = 0

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

for i start: 0 end: length step: 1 {
    for j start: 0 end: array[i] step: 1 {
        plot i j 1
    }
    update()
}
