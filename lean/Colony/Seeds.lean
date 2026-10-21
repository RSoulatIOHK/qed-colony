import Colony.Tactic

/-!
Small, human-readable seed models. These are not the Cardano ledger, UPLC, or
compiled Plutus scripts. Benchmark claims must retain this scope.
-/
namespace Colony.Seed

/-- A tail-recursive list program, with an arbitrary initial accumulator. -/
@[simp] def reverseAcc (xs acc : List Nat) : List Nat :=
  match xs with
  | [] => acc
  | x :: rest => reverseAcc rest (x :: acc)

/-- A tail-recursive counter; the accumulator represents already processed items. -/
@[simp] def countAcc (xs : List Nat) (count : Nat) : Nat :=
  match xs with
  | [] => count
  | _ :: rest => countAcc rest (count + 1)

/-- A tiny balance transition model, unrelated to actual ledger semantics. -/
structure Account where
  balance : Nat
  received : Nat
  deriving DecidableEq, Repr

@[simp] def deposit (state : Account) (amount : Nat) : Account :=
  ⟨state.balance + amount, state.received + amount⟩

/-- Two sales allocate separate payments. The validator checks each allocation. -/
@[simp] def allocatedSales (priceA priceB paidA paidB : Nat) : Prop :=
  priceA ≤ paidA ∧ priceB ≤ paidB

/-- An intentionally unsafe rule reuses the same payment for both sales. -/
@[simp] def sharedPaymentSales (priceA priceB paid : Nat) : Prop :=
  priceA ≤ paid ∧ priceB ≤ paid

end Colony.Seed
