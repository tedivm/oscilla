"""Rich TUI implementation for the adventure game.

This is the only module in the engine that imports rich directly.
All step handlers consume TUICallbacks (pipeline.py Protocol) so
they remain decoupled from Rich and can be exercised with MockTUI
in tests.
"""

from __future__ import annotations

from logging import getLogger
from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from rich.table import Table

from oscilla.engine.player import PlayerState
from oscilla.engine.registry import ContentRegistry

logger = getLogger(__name__)

# Shared console instance — used by both RichTUI methods and the standalone
# show_status helper so all output goes through the same stream.
console = Console()


class RichTUI:
    """Concrete TUICallbacks implementation backed by the Rich library.

    Satisfies the TUICallbacks Protocol defined in pipeline.py.
    """

    def show_text(self, text: str) -> None:
        """Render a narrative passage inside a bordered panel."""
        console.print(Panel(text, padding=(1, 2)))

    def show_menu(self, prompt: str, options: List[str]) -> int:
        """Display a numbered menu and return the 1-based index of the chosen option.

        Loops on invalid input so the player cannot advance without a valid choice.
        """
        console.print()
        for i, option in enumerate(options, start=1):
            console.print(f"  [bold cyan][{i}][/bold cyan] {option}")
        console.print()
        while True:
            choice = IntPrompt.ask(f"[bold]{prompt}[/bold]")
            if 1 <= choice <= len(options):
                return choice
            console.print(f"[red]Invalid choice. Enter a number between 1 and {len(options)}.[/red]")

    def show_combat_round(
        self,
        player_hp: int,
        enemy_hp: int,
        player_name: str,
        enemy_name: str,
    ) -> None:
        """Render a two-row HP table before each player action in the combat loop."""
        table = Table(title="Combat", show_header=True, header_style="bold red")
        table.add_column("Combatant", style="bold")
        table.add_column("HP", justify="right", style="green")
        table.add_row(player_name, str(player_hp))
        table.add_row(enemy_name, str(enemy_hp))
        console.print(table)

    def wait_for_ack(self) -> None:
        """Pause for the player to acknowledge before advancing."""
        Prompt.ask(
            "[dim]Press Enter to continue[/dim]",
            default="",
            show_default=False,
        )


def show_status(player: PlayerState, registry: ContentRegistry) -> None:
    """Render the player status panel to the shared console.

    Reads public_stats from CharacterConfig dynamically — the engine does not
    hard-code any stat names. Hidden stats are never displayed.
    XP-to-next-level is derived from the game manifest's xp_thresholds list.
    """
    game = registry.game
    char_config = registry.character_config

    if game is None or char_config is None:
        console.print("[yellow]Warning: game or character config not loaded.[/yellow]")
        return

    thresholds = game.spec.xp_thresholds
    if player.level - 1 < len(thresholds):
        xp_needed = thresholds[player.level - 1]
        xp_line = f"XP: [cyan]{player.xp}[/cyan] / {xp_needed}"
    else:
        xp_line = f"XP: [cyan]{player.xp}[/cyan]  [dim](max level)[/dim]"

    stat_lines: List[str] = []
    for stat_def in char_config.spec.public_stats:
        value = player.stats.get(stat_def.name, stat_def.default)
        label = stat_def.description or stat_def.name
        stat_lines.append(f"  {label}: [yellow]{value}[/yellow]")

    lines: List[str] = [
        f"[bold]{player.name}[/bold]   Level [bold cyan]{player.level}[/bold cyan]",
        f"HP: [green]{player.hp}[/green] / {player.max_hp}",
        xp_line,
        "",
        *stat_lines,
    ]
    console.print(
        Panel(
            "\n".join(lines),
            title="[bold]Player Status[/bold]",
            padding=(1, 2),
        )
    )
