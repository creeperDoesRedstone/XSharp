include operations

const radius 8
const xc 15
const yc 10

var x: int = 0  
var y: int = radius  
var d: int = 1 - radius  // Initial decision variable

// Function to plot all 8 symmetric points
plot xc + x yc + y 1  
plot xc - x yc + y 1  
plot xc + x yc - y 1  
plot xc - x yc - y 1  
plot xc + y yc + x 1  
plot xc - y yc + x 1  
plot xc + y yc - x 1  
plot xc - y yc - x 1  

while y - x {  
    x = x + 1  
    if d < 0 {  
        d = d + (x << 1) + 1  // d = d + 2x + 1  
    } else {  
        y = y - 1  
        d = d + ((x - y) << 1) + 1  // d = d + 2(x - y) + 1  
    }  

    // Plot new symmetric points
    plot xc + x yc + y 1  
    plot xc - x yc + y 1  
    plot xc + x yc - y 1  
    plot xc - x yc - y 1  
    plot xc + y yc + x 1  
    plot xc - y yc + x 1  
    plot xc + y yc - x 1  
    plot xc - y yc - x 1  
}