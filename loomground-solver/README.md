# loomground-solver

Portable analytic and probabilistic reasoning skills over the installed Loomground Solver kernel.
The package covers opponent modelling, probability tracking, strategic analysis, liability
estimation, litigation-risk assessment, and general risk analysis.

The skills are thin wrappers: they delegate calculations to `loomground-solver`, report the named
method and structured result, and fail closed when the kernel is unavailable. They do not copy or
reimplement the reasoner.

Governance policy authoring, authorization, enforcement, and audit belong to the separately
licensed RVND marketplace and are intentionally not distributed from this Apache-2.0 package.
