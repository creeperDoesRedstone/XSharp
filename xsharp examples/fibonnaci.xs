var a: int = 0
var b: int = 1
var i: int = 0
var res: int = 0


for i start: 2 end: 11 step: 1 {
    res = a + b
    a = b
    b = res
}
res
