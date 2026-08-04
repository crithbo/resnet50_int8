# LC2 last-index clarification

The claim that `dram_loop_configs.LC2.last_index=1` was a secondary structural
risk is withdrawn.

- LC2 is unchanged from the human-authored original.
- LC1 and LC2 are sibling child loops of LC0.
- `last_index` describes the terminal loop/tag level; it is not a connection
  identifier and is not incremented by adding identity LC_PE fanout nodes.
- The corrected-v2 LC_PE branch carries LC0's tag to the two stream index
  consumers but introduces no new loop nesting level.
- Consequently LC2's local terminal level remains `1`.
- The native quant reference's LC2 value `2` belongs to its own
  occurrence/lifetime contract and must not be transplanted without a matching
  stage-level proof.

No JSON was changed by this clarification. The only dynamically supported
next correction remains:

`general_array.outport.src_id: 1 → 0`.

