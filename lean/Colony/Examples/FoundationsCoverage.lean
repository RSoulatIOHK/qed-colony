import Colony.Tactic

/-! Single-call coverage of ordinary foundational mathematics. -/

theorem math002_A1 (n : Nat) : n + 0 = n := by colony

theorem math002_A2 (n : Nat) : 0 + n = n := by colony

theorem math002_A3 (x y : Nat) : x + y = y + x := by colony

theorem math002_A4 (x y z : Nat) : (x + y) + z = x + (y + z) := by colony

theorem math002_O1 (x y z : Nat) : x ≤ y → x + z ≤ y + z := by colony

theorem math002_L1 (xs ys : List Nat) : (xs ++ ys).length = xs.length + ys.length := by colony

theorem math002_L2 (xs : List Nat) : xs.reverse.length = xs.length := by colony

theorem math002_L3 (xs : List Nat) : xs.reverse.reverse = xs := by colony
