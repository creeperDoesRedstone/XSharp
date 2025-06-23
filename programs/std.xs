include operations

sub min(a, b) {
  if a > b { b } else { a }
}

sub max(a, b) {
  if a > b { a } else { b }
}

var rng_seed: int = 1 // default seed

sub srand(s) {
  rng_seed = s
}

sub rand() {
  rng_seed = (2053 * rng_seed + 13849) // overflow wraps naturally at 65536
  // rng_seed now holds the new value
}