from __future__ import annotations


class LinkarError(Exception):
    code = "linkar_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ProjectValidationError(LinkarError):
    code = "invalid_project"


class TemplateValidationError(LinkarError):
    code = "invalid_template"


class ParameterResolutionError(LinkarError):
    code = "param_resolution_error"


class AssetResolutionError(LinkarError):
    code = "asset_resolution_error"


class ExecutionError(LinkarError):
    code = "execution_error"
