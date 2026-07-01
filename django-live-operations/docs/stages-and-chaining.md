# Stages and Chaining

## Stages (`p.stage()`)

Declare stages as a class attribute:

```python
class MyOp(LiveOperation):
    stages = ["Load", "Process", "Save"]

    def run(self, p):
        with p.stage("Load"):
            data = load_data()
        with p.stage("Process"):
            result = process(data)
        with p.stage("Save"):
            save(result)
        p.result({"count": len(result)})
```

Each `with p.stage(name):` block:

1. Sets `op.current_stage` (index) and `op.stage_states[name] = "active"`
2. Saves to DB (`update_fields=["current_stage", "stage_states"]`)
3. Pushes the updated stage stepper HTML (`#op-stages`)
4. Resets the progress bar to 0%

On exit:

- Success → `stage_states[name] = "done"`; stepper updated
- `OperationCancelled` → `stage_states[name] = "cancelled"`; stepper updated
- Other exception → `stage_states[name] = "failed"`; stepper updated

The stepper is rendered from `live_operations/_stages.html` which iterates
`op.stages` and looks up state via `{{ op.stage_states|get_item:name }}`.

## Stages must be flat

Each call to `p.stage(name)` looks up `name` in `op.stages` by index. The
`stages` list must be flat and match the exact names passed to `p.stage()`.
A name not in `op.stages` still runs the block but is not tracked in the
stepper.

## Chaining (`p.chain_to()`)

Chain two operations without a page reload:

```python
class StepA(LiveOperation):
    def run(self, p):
        p.log("Step A done")
        step_b = StepB.objects.create(owner=self.owner)
        p.chain_to(step_b)
```

What happens (web mode):

1. Current op is finalized (committed to DB as `finished_successfully=True`)
2. `step_b` is enqueued
3. Via `transaction.on_commit` (§19.4):
   - The DOM container is OOB-swapped to show `step_b`'s container
     (`hx-swap-oob="outerHTML:#op-<old_pk>"`)
   - A `liveop_chain` signal is sent so `live-operations.js` re-initialises
     the WebSocket subscription to `step_b`'s channel (idempotent init closes
     the old socket cleanly)

The page never reloads. The user sees the transition from step A to step B
seamlessly.

## Text mode chaining

In text/CLI mode, `chain_to()` runs the next operation inline in the same
thread with the same output stream (no socket handshake).

## Text mode stages

In text mode, stage boundaries are printed as section headers:

```
=== [1/3] Load ===
=== [2/3] Process ===
=== [3/3] Save ===
```
