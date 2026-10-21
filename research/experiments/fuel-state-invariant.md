# AUTO-5a9683a643: Fuel-recursive state preservation

## Source identity

- Base Git revision: `3a7c71e41ba1a29df363e8847fbe5a01e3a96bf8`
- Final example SHA-256: `9fc24a779ab10254ffadb77c80c5fb08b08682a1f7a8070ba84367d7cfdff3dd` (`lean/Colony/Examples/FuelStateInvariant.lean`)
- Final import file SHA-256: `f26aaa010fd4a5ebc852c64860e7fb3fb2c3043d7ab4d786a0cad7eae2b8c152` (`lean/Colony.lean`)
- Toolchain: `leanprover/lean4:v4.35.0`; Lean `4.35.0`, commit `eb6cafb7290e8bd5f2937522d8d804f58f02bafc`; Lake `5.0.0-src+eb6cafb`.

## Probe

The example defines `run`, a structurally natural-fuel-recursive function that increments both `CounterState` fields on each recursive call. Its exact positive statement is `run_preserves_equality`: assuming `state.left = state.right`, the result has equal fields. The tactic attempt against that unchanged statement did not close: the reproducible `fail_if_success` around `colony` passes, after which ordinary induction proves the same theorem. The nearby target requiring the result's right field plus one to equal its left field also remains unproved by `colony`, as checked with `fail_if_success`.

## Commands and outcomes

- `cd lean && lake env lean Colony/Examples/FuelStateInvariant.lean` — initially failed because the imported `Colony.Tactic` module had not yet been built into Lake's search path. This was an invocation-order issue, not a source proof result.
- First `cd lean && lake build Colony` — failed in the manual successor proof: `omega` did not normalize projections from the constructed structure literal.
- After making the successor equality explicit, `cd lean && lake build Colony` — **passed**, `Build completed successfully (11 jobs)`. This command compiled the `fail_if_success` checks and the kernel-accepted induction proof.
- Final `cd lean && lake build Colony` — **passed**, with the same successful 11-job result.
- `git diff --check` — **passed**.

## Assurance and limits

Lean elaboration accepted the ordinary induction proof of the stated theorem, so the theorem is kernel-checked by this Lean toolchain. The experiment also records that `colony` failed on the exact positive target and that it failed on the deliberately false nearby target. No exported replay, independent-kernel check, or correspondence to Cardano execution was performed. These results establish neither completeness nor general behavior for fuel-recursive procedures.
