from pathlib import Path


def resolve(ctx):
    return str(
        (
            Path(__file__).resolve().parents[2]
            / "fixtures"
            / "override_source"
        ).resolve()
    )
