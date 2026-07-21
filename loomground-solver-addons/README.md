# solver-addons

Portable, provider-neutral skill package for optional Loomground Solver
add-ons. The canonical implementation remains in `flxk1/solver`; this package
calls its public deterministic advisor API and does not copy the algorithm.

Build Claude, Codex and generic distributions from the repository root with
`python3 tools/build_packages.py solver-addons --target all`.

Runtime requirement: install `loomground-solver` from
`https://github.com/flxk1/solver`. No graph, retriever, model, network service or
product-specific provider is required for advice.
