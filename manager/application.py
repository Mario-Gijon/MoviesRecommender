"""Application service lifecycle operations."""

from __future__ import annotations

from manager.compose import DockerCompose, Environment, profiles_for
from manager.config import Configuration


SERVICE_SETS = {
    "backend": ("api",),
    "frontend": ("frontend",),
    "both": ("api", "frontend"),
}


class ApplicationManager:
    def __init__(
        self,
        configuration: Configuration,
        environment: Environment,
        compose: DockerCompose,
    ) -> None:
        self.configuration = configuration
        self.environment = environment
        self.compose = compose

    def execute(self, target: str, action: str) -> int:
        services = SERVICE_SETS[target]
        profiles = profiles_for(self.environment, services)
        if action == "start":
            return self.compose.run(["up", "-d", *services], profiles=profiles)
        if action == "stop":
            return self.compose.run(["stop", *services], profiles=profiles)
        if action == "restart":
            return self.compose.run(["restart", *services], profiles=profiles)
        if action == "update":
            return self._update(services, profiles)
        if action == "status":
            self.show_status(services)
            return 0
        if action == "logs":
            return self.compose.run(["logs", "--follow", *services], profiles=profiles)
        raise ValueError(f"Unknown application action: {action}")

    def _update(self, services: tuple[str, ...], profiles: tuple[str, ...]) -> int:
        if self.environment.development:
            if self.compose.run(["build", *services], profiles=profiles):
                return 1
        elif self.compose.run(["pull", *services], profiles=profiles):
            return 1
        return self.compose.run(
            ["up", "-d", "--force-recreate", *services],
            profiles=profiles,
        )

    def show_status(self, services: tuple[str, ...] = ("api", "frontend")) -> None:
        for service in services:
            status = self.compose.service_status(
                service,
                profiles=profiles_for(self.environment, (service,)),
            )
            name = "Backend" if service == "api" else "Frontend"
            print(f"{name}: {status.label}")
            published = ", ".join(status.published_ports) or "sin publicar"
            if service == "api":
                print(f"  Puerto publicado: {published}")
                if status.health:
                    print(f"  Salud: {status.health}")
            else:
                print(f"  Puerto publicado: {published}")
