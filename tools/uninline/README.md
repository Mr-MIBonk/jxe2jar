# uninline - bytecode constant & accessor recovery

Self-contained ASM tool suite that turns the raw literals in a J9-converted jar back into
symbolic references, so the decompiled Java reads like source. **No regex over source text**;
every rewrite is value-preserving and verified. Run *after* `jxe2jar.py`, *before* Vineflower.

```
uninline/
  src/          the tools (Java, ASM)
  lib/          asm-9.7 (core/tree/analysis)
  uninline.jar  fat jar (built; tools + asm)
  build.sh      compile src/ -> uninline.jar
  uninline.sh   run: uninline.sh <command> <args>
```

## Build

```sh
tools/uninline/build.sh          # needs JDK 17+ (produces uninline.jar)
```

## Run

```sh
U=tools/uninline/uninline.sh

# full pipeline: base.jar -> recovered.jar (+ doubtful.tsv QA sidecar)
$U pipeline out/base.jar out/final.jar out/doubtful.tsv 100

# or step by step:
$U uninline out/base.jar      out/u.jar 100     # T1 closure / T2 global-distinctive / T3a co-ref
$U sink     out/u.jar         out/s.jar 100     # T3b sink-domain dataflow (fixpoint + field/switch)
$U refine   out/s.jar         out/r.jar out/doubtful.tsv   # 3-way QA (keep/revert/flag)
$U access   out/r.jar         out/final.jar     # inline synthetic access$NNN

# QA:
$U verify   out/base.jar out/u.jar              # prove 100% value-correct (0 mismatches)
$U audit    out/final.jar                       # type-ambiguity / jsr / utf-8 audit
```

## Tools

| command  | class          | what it does |
|----------|----------------|--------------|
| uninline | `Uninliner`    | rewrite literal-loads to `getstatic Owner.FIELD` for all constant types, tiered: T1 closure-unique, T2 global-unique+distinctive, T3a co-reference+distinctive. |
| sink     | `SinkResolve`  | T3b - learn each `(callee,method,argIndex)` slot's constant family from surviving getstatic args (self-seeded), resolve non-distinctive literals flowing into a learned slot. Fixpoint + field/switch domains. `--domains <md>` dumps the map. |
| refine   | `RefineResolve`| three-way QA: KEEP (family-cohesion / distinctiveness / lexical name-context), REVERT genuine collisions to honest numbers, FLAG the rest (-> `doubtful.tsv` QA sidecar of low-confidence resolutions). |
| access   | `AccessInline` | inline synthetic `access$NNN` accessors to the real field/method access (reads the body, stack-guarded). |
| verify   | `VerifyResolve`| instruction-diff original vs recovered: every replacement must be `literal V -> getstatic F where value(F)==V`. Reports 0 mismatches + a name-provenance audit. |
| audit    | `TypeAudit`    | correctness audit: field ConstantValue vs descriptor, `ldc2_w` long/double typing, `jsr`/`ret`, modified-UTF-8 edges. |

## Guarantees

- **100% value-correct** - a getstatic reads exactly the literal's value (`VerifyResolve` proves it).
- **Names are heuristic** - equal values can belong to different domains. `RefineResolve`
  reverts some doubtful matches and records them in `doubtful.tsv`; the value check
  cannot prove that a recovered name is semantically correct.
- **Decompile-only** - a `getstatic` can trigger class init, so the jar is a reading aid, not
  runnable bytecode.
- Bitmap resource IDs inside an `int[]` passed to `setBitmaps(int[])` remain numeric.
  A model-bank constant with the same value does not establish the bitmap's name.
