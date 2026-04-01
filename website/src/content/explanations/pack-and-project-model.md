---
title: Pack and project model
description: Packs distribute reusable templates. Projects record local run history and chosen defaults.
order: 2
---

A pack is an external asset. A project is local state.

That separation keeps template sharing independent from project history. It also keeps
`project.yaml` small and readable instead of turning it into a workflow language.
