"""U8's PlatformControl parts (A6), beside U7's `platform_control` package.

U7's package keeps only its built files and two seams whose default is U7's built
behaviour: `executor.run_effect`'s `adapter_module` and `native_adapter.main`'s `effect`,
with one name more in `run_effect`'s child environment, DOCKER_HOST, kept when it is set
(L1-78).
U8 passes its parts in through them; no file of U7's package names this one. The operator
tool runs as `python -I -m docsuri_ops.u8_platform <command> <word>` (U8 plan Step 44, the
person's decisions of 2026-10-25, "Move U8's code out of U7" and "Its own package's name").
"""
