# Chaining Example Pack

This pack shows how one template can produce output and another template can consume it through a pack-provided default binding.

Suggested flow:

1. `linkar project init --name chaining-demo`
2. `linkar pack add ./examples/packs/chaining --binding default`
3. `linkar run produce_message --message "hello"`
4. `linkar run consume_message`
