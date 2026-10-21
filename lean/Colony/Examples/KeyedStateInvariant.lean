import Colony.Tactic

namespace Colony.Examples.KeyedStateInvariant

abbrev State := List (Nat × Nat)

/-- Replace the value for the first matching key. If the key is absent, leave
the list unchanged. Structural recursion bounds the work by the list length. -/
def update (key value : Nat) : State → State
  | [] => []
  | (storedKey, storedValue) :: rest =>
      if storedKey = key then (storedKey, value) :: rest
      else (storedKey, storedValue) :: update key value rest

/-- Sum the values associated with keys other than `excluded`. -/
def sumExcept (excluded : Nat) : State → Nat
  | [] => 0
  | (key, value) :: rest =>
      (if key = excluded then 0 else value) + sumExcept excluded rest

/-- Updating one key preserves the sum of values at every other key. -/
theorem update_preserves_sum_except (state : State) (key value : Nat) :
    sumExcept key (update key value state) = sumExcept key state := by
  fail_if_success
    (have preserved : sumExcept key (update key value state) =
        sumExcept key state := by
      colony)
  induction state with
  | nil => rfl
  | cons entry rest ih =>
      rcases entry with ⟨storedKey, storedValue⟩
      by_cases hkey : storedKey = key
      · simp [update, sumExcept, hkey]
      · simp [update, sumExcept, hkey, ih]

/-- A concrete update changes the selected value while keeping the other
value in the sum. -/
example : sumExcept 2 (update 2 99 [(1, 7), (2, 5), (3, 11)]) = 18 := by
  decide

/-- A nearby false property is not established by `colony`. -/
example (state : State) (key value : Nat) : True := by
  fail_if_success
    (have wrong : sumExcept key (update key value state) =
        sumExcept key state + 1 := by
      colony)
  trivial

end Colony.Examples.KeyedStateInvariant
