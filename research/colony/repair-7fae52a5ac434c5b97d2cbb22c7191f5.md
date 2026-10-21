# Add the missing List.filter experiment artifact

Task `REPAIR-7fae52a5ac434c5b97d2cbb22c7191f5`; base revision `3b11188d52ad5ff8c1f1885508b44c1d6e584f66`.

I couldn’t create `research/experiments/list-filter-bound.md`: the workspace is mounted read-only. The public source material at candidate head `6e53914fe933c97fe4081ac3dcd87647c32359df` contains the proposed artifact text in `research/colony/auto-4c5c3726b7.md`; that commit changes only this report. Its embedded experiment records the commands as measured at `b43224dc2c8e1a928fc7dec1357d80bca61cb172`, not at `6e53914`.

The report records the unchanged generic `List.filter` length bound and a false `+1` control, both attempted directly with `by colony`. The positive attempt failed with “the initial proof portfolio could not close this goal”; a separate induction diagnostic failed because `α` could not be generalized. Separate sanity proofs were accepted, with `[propext, Quot.sound]` on the positive proof and no axioms on the false-control witness. No `by colony` success, exported replay, independent-kernel acceptance, or Cardano correspondence is claimed.

I verified the recorded source commit and read the existing artifact text. I could not rerun its commands or write the requested file in this read-only workspace. No repository files were changed; saving the artifact remains outstanding.
