# Binding Override Example Pack

This pack shows the difference between:

- the pack's default binding
- an explicit override binding selected by the caller or project

Suggested flow:

1. `linkar project init --name binding-demo`
2. `linkar pack add ./examples/packs/binding_overrides --binding default`
3. `linkar run produce_data --value project`
4. `linkar run consume_data`
5. `linkar run consume_data --binding ./examples/packs/binding_overrides/override_binding`

The default binding uses the latest `dataset_dir` output from `produce_data`.

The override binding ignores project output and resolves `source_dir` from its own function-backed path.
