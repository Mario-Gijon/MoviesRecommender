"""Docker Compose selection, execution and real service-state inspection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

from manager.config import Configuration


STATE_LABELS = {
    "running": "ejecutándose",
    "stopped": "detenido",
    "exited": "detenido",
    "missing": "no creado",
    "created": "creado",
    "restarting": "reiniciándose",
    "paused": "pausado",
    "dead": "finalizado con error",
    "starting": "iniciando",
    "unknown": "desconocido",
}
HEALTH_LABELS = {
    "healthy": "saludable",
    "unhealthy": "no saludable",
    "starting": "iniciando",
}


def format_service_state(raw_state: str) -> str:
    normalized = raw_state.lower()
    label = STATE_LABELS.get(normalized)
    return label if label is not None else f"Estado desconocido: {raw_state}"


def format_service_health(raw_health: str) -> str:
    normalized = raw_health.lower()
    label = HEALTH_LABELS.get(normalized)
    return label if label is not None else f"Salud desconocida: {raw_health}"


@dataclass(frozen=True)
class Environment:
    name: str
    label: str
    compose_file: str
    development: bool


DEVELOPMENT = Environment(
    name="development",
    label="Desarrollo",
    compose_file="compose.dev.yaml",
    development=True,
)
PRODUCTION = Environment(
    name="production",
    label="Producción",
    compose_file="compose.yaml",
    development=False,
)


@dataclass(frozen=True)
class PublishedPort:
    host: str
    published_port: str
    target_port: str
    protocol: str

    @property
    def external(self) -> str:
        formatted_host = (
            self.host
            if self.host.startswith("[") or ":" not in self.host
            else f"[{self.host}]"
        )
        return f"{formatted_host}:{self.published_port}"

    @property
    def internal(self) -> str:
        return f"{self.target_port}/{self.protocol}"


@dataclass(frozen=True)
class ServiceStatus:
    state: str
    health: str | None = None
    published_ports: tuple[PublishedPort, ...] = ()

    @property
    def is_running(self) -> bool:
        return self.state.lower() == "running"

    @property
    def label(self) -> str:
        return format_service_state(self.state)


class DockerCompose:
    def __init__(self, configuration: Configuration, environment: Environment) -> None:
        self.configuration = configuration
        self.environment = environment

    def command(self, arguments: list[str], *, profiles: tuple[str, ...] = ()) -> list[str]:
        command = [
            "docker",
            "compose",
            "--env-file",
            self.configuration.source.name,
        ]
        if self.environment.development:
            command.extend(["-p", "movies-recommender-dev"])
        command.extend(["-f", self.environment.compose_file])
        for profile in profiles:
            command.extend(["--profile", profile])
        return command + arguments

    def run(self, arguments: list[str], *, profiles: tuple[str, ...] = ()) -> int:
        try:
            return subprocess.run(
                self.command(arguments, profiles=profiles),
                cwd=self.configuration.root,
                check=False,
            ).returncode
        except OSError as exc:
            print(f"No se pudo ejecutar Docker Compose: {exc}", file=sys.stderr)
            return 1

    def run_with_log(
        self,
        arguments: list[str],
        log_path: Path,
        *,
        profiles: tuple[str, ...] = (),
    ) -> int:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with subprocess.Popen(
                self.command(arguments, profiles=profiles),
                cwd=self.configuration.root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            ) as process, log_path.open("w", encoding="utf-8") as log:
                assert process.stdout is not None
                for line in process.stdout:
                    print(line, end="")
                    log.write(line)
                return process.wait()
        except OSError as exc:
            print(f"No se pudo ejecutar Docker Compose: {exc}", file=sys.stderr)
            return 1

    def service_status(self, service: str, *, profiles: tuple[str, ...] = ()) -> ServiceStatus:
        try:
            result = subprocess.run(
                self.command(
                    ["ps", "--all", "--format", "json", service],
                    profiles=profiles,
                ),
                cwd=self.configuration.root,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return ServiceStatus("unknown")
        if result.returncode:
            return ServiceStatus("unknown")
        entries = _parse_compose_status(result.stdout)
        if not entries:
            return ServiceStatus("missing")
        entry = entries[0]
        state = str(entry.get("State", ""))
        health = str(entry.get("Health", "")) or None
        ports = _published_ports(entry)
        return ServiceStatus(state or "unknown", health, ports)


def profiles_for(
    environment: Environment,
    services: tuple[str, ...],
    *,
    maintenance: bool = False,
) -> tuple[str, ...]:
    if maintenance:
        return ("maintenance",)
    if not environment.development and "frontend" in services:
        return ("frontend",)
    return ()


def _parse_compose_status(output: str) -> list[dict[str, object]]:
    text = output.strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        entries: list[dict[str, object]] = []
        for line in text.splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                return []
            if isinstance(item, dict):
                entries.append(item)
        return entries
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    return [parsed] if isinstance(parsed, dict) else []


def _published_ports(entry: dict[str, object]) -> tuple[PublishedPort, ...]:
    publishers = entry.get("Publishers")
    if not isinstance(publishers, list):
        return ()
    ports: list[PublishedPort] = []
    for publisher in publishers:
        if not isinstance(publisher, dict):
            continue
        published_port = publisher.get("PublishedPort")
        target_port = publisher.get("TargetPort")
        if published_port is None or target_port is None:
            continue
        ports.append(
            PublishedPort(
                host=str(publisher.get("URL") or "0.0.0.0"),
                published_port=str(published_port),
                target_port=str(target_port),
                protocol=str(publisher.get("Protocol") or "tcp").lower(),
            )
        )
    return tuple(ports)
