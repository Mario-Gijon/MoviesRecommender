"""Temporary bridge to the existing interactive dataset container flow."""

from __future__ import annotations

from manager.compose import DockerCompose


def run_existing_interactive_flow(compose: DockerCompose) -> int:
    print("La gestión completa del Dataset se implementará en la siguiente fase.")
    print("Se abrirá temporalmente el flujo interactivo existente de Dataset.")
    return compose.run(
        ["run", "--rm", "dataset"],
        profiles=("dataset",),
    )
