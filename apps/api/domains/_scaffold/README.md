Scaffold: copy this folder to `apps/api/domains/<name>/`, then rename symbols.

## Checklist

1. Rename `build_<name>_graph` in `graph.py`
2. Define typed State in `state.py` (see echo for an example)
3. Register tools + graph (+ input_builder) in `bootstrap.py`
4. Call `register(...)` from `apps/api/domains/bootstrap.py`
5. Set graph recursion_limit in `compile(...)` / runnable config if the graph can loop

Do **not** import other domains. Do **not** change `packages/core` for a new business route.
