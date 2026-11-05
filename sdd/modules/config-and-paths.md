---
governs: [src/armance/config.py, src/armance/paths.py, src/armance/storage/, ":!src/armance/storage/rag_index.py",
  ":!src/armance/storage/rag_status.py", ":!src/armance/storage/ingestion.py"]
depends: [core-models]
---
# config-and-paths

Where Armance keeps things, split cleanly between the machine and the project. The global directory (platformdirs,
`~/.config/armance` on Linux) holds config, secrets, base agents and the project registry: one setup per machine. A
project's `.armance/` holds only its data (docs, sessions, runs, context, exports), as flat files with no database, so
deleting it forgets the project and nothing else.

Constraints and non-goals:

- No secret in `config.yaml` or in a project tree: API keys live only in the global `.env` and the environment.
- A project folder holds no config, secrets or base agents.
- `paths.py` knows where the roots are; `storage/paths.py` knows the layout under a root.

Criteria:

- `ARMANCE_CONFIG_DIR` redirects every global path:
  [test_global_config_dir_env_override](../../tests/unit/test_paths.py).
- Saving the config never writes an API key:
  [test_save_strips_api_keys](../../tests/unit/test_config.py),
  [test_overlay_never_takes_api_key](../../tests/test_provider_local_overlay.py).
- Environment variables override the YAML values of each provider:
  [test_round_trip_with_env_override](../../tests/unit/test_config.py),
  [test_load_config_overlays_per_instance_env](../../tests/test_provider_instances.py).
- A declared `default_provider` missing from `providers` is added before the env overlay:
  [test_default_provider_always_listed](../../tests/unit/test_config.py),
  [test_default_provider_gets_env_overlay](../../tests/unit/test_config.py).
- The global directory never gets a project data tree:
  [test_ensure_data_tree_skips_global_config_dir](../../tests/unit/test_config.py).
- A project may add provider instances and extend allowlists, never set a key:
  [test_overlay_adds_new_instance](../../tests/test_provider_local_overlay.py),
  [test_overlay_new_instance_ignores_api_key](../../tests/test_provider_local_overlay.py).
