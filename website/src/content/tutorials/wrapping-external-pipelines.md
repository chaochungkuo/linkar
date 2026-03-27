---
title: Wrapping an external pipeline
description: Turn an existing script or external repo into a Linkar template without copying all its code.
order: 4
status: draft
---

The recommended pattern is a thin Linkar template around the external tool or repo. The template declares the interface in `template.yaml`, while `run.sh` adapts Linkar's resolved parameters to the external entrypoint.
