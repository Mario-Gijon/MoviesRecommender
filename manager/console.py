"""Small, interruption-safe Spanish console primitives."""

from __future__ import annotations

from collections.abc import Mapping


class Console:
    def menu(self, title: str, options: Mapping[str, str]) -> str | None:
        print(f"\n{title}\n")
        for key, label in options.items():
            print(f"{key}. {label}")
        while True:
            try:
                choice = input("Selecciona una opción: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nOperación cancelada.")
                return None
            if choice in options:
                return choice
            print("Opción no válida.")

    def confirm(self, message: str) -> bool:
        try:
            value = input(f"{message} [s/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nOperación cancelada.")
            return False
        return value in {"s", "si", "sí", "y", "yes"}
