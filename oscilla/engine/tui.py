"""Textual TUI implementation for the adventure game.

Provides a full-screen persistent layout with a scrollable narrative log,
arrow-key choice menu, player status sidebar, and region context panel.

The TextualTUI class satisfies the async TUICallbacks protocol defined in
pipeline.py — step handlers call await tui.show_text() / show_menu() etc.
and this module handles all Textual widget interaction behind the scenes.
"""

from __future__ import annotations

import asyncio
import random
from logging import getLogger
from typing import TYPE_CHECKING, List

from rich.panel import Panel
from rich.table import Table
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, OptionList, RichLog, Static

if TYPE_CHECKING:
    from oscilla.engine.player import PlayerState
    from oscilla.engine.registry import ContentRegistry

logger = getLogger(__name__)

# ─── Widgets ────────────────────────────────────────────────────────────────


class NarrativeLog(RichLog):
    """Scrollable log of all narrative passages displayed during the session.

    Each show_text() call appends a new entry; history persists for the full
    session so the player can scroll up to review earlier narrative.
    """

    DEFAULT_CSS = """
    NarrativeLog {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
        min-height: 5;
    }
    """

    def append_text(self, text: str) -> None:
        """Append a narrative entry and scroll to the bottom."""
        self.write(Panel(text, padding=(0, 1)))


class ChoiceMenu(OptionList):
    """Arrow-key navigable choice widget.

    wait_for_selection() posts the choices and suspends the caller via
    asyncio.Event until the player presses Enter on a highlighted item.
    """

    DEFAULT_CSS = """
    ChoiceMenu {
        border: solid $accent;
        height: auto;
        min-height: 3;
        max-height: 12;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._selection_event: asyncio.Event | None = None
        self._selected_index: int = 1

    async def wait_for_selection(self, options: List[str]) -> int:
        """Set options and suspend until the player confirms a selection.

        Returns the 1-based index of the chosen option.
        """
        self.set_options(options)
        self.display = True
        # OptionList.highlighted is reliable after set_options(); setting it
        # to 0 pre-selects the first item so Enter works without navigating.
        self.highlighted = 0
        # Focus the menu so arrow keys work immediately.
        self.focus()
        self._selection_event = asyncio.Event()
        self._selected_index = 1
        await self._selection_event.wait()
        self._selection_event = None
        self.clear_options()
        self.display = False
        return self._selected_index

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Fire when the player presses Enter on a highlighted option."""
        if self._selection_event is not None:
            # option_index is 0-based; we return 1-based.
            self._selected_index = event.option_index + 1
            self._selection_event.set()
        event.stop()


class StatusPanel(Static):
    """Right-panel widget displaying live player stats.

    refresh_player() re-renders the panel from a PlayerState snapshot.
    Only stats declared in public_stats of CharacterConfig are shown;
    hidden stats are never displayed.
    """

    DEFAULT_CSS = """
    StatusPanel {
        border: solid $success;
        padding: 1;
        height: 1fr;
        min-height: 8;
    }
    """

    def __init__(self) -> None:
        super().__init__("")
        self._registry: ContentRegistry | None = None

    def set_registry(self, registry: ContentRegistry) -> None:
        self._registry = registry

    def refresh_player(self, player: PlayerState) -> None:
        """Re-render the status panel from the current PlayerState."""
        if self._registry is None:
            self.update("(status unavailable)")
            return

        game = self._registry.game
        char_config = self._registry.character_config
        if game is None or char_config is None:
            self.update("(status unavailable)")
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
            f"HP:  [green]{player.hp}[/green] / {player.max_hp}",
            xp_line,
            "",
            *stat_lines,
        ]
        self.update("\n".join(lines))


class RegionPanel(Static):
    """Right-panel widget showing the currently active region.

    set_region() updates the display when the player navigates to a new region.
    """

    DEFAULT_CSS = """
    RegionPanel {
        border: solid $warning;
        padding: 1;
        height: auto;
        min-height: 5;
    }
    """

    def __init__(self) -> None:
        super().__init__("[dim]No region selected[/dim]")

    def set_region(self, name: str, description: str) -> None:
        """Update the panel with the new region name and description."""
        self.update(f"[bold]{name}[/bold]\n\n{description}")


# ─── Help overlay ───────────────────────────────────────────────────────────

_HELP_TEXT = """\
[bold]Navigation[/bold]
  [cyan]↑ / ↓[/cyan]           Move selection up / down
  [cyan]Enter[/cyan]            Confirm selection

[bold]Narrative Log[/bold]
  [cyan]PgUp / PgDn[/cyan]      Scroll log up / down
  [cyan]Home / End[/cyan]        Jump to top / bottom

[bold]Application[/bold]
  [cyan]?[/cyan]                Toggle this help
  [cyan]ctrl+q / Escape[/cyan]  Quit game
"""


class HelpOverlay(ModalScreen[None]):
    """Modal help screen listing all key bindings grouped by category."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(_HELP_TEXT, id="help-content")


# ─── Main application ────────────────────────────────────────────────────────

_OUTCOME_MESSAGES = {
    "completed": "Adventure complete!",
    "defeated": "You were defeated and barely escaped...",
    "fled": "You fled from battle.",
}


class OscillaApp(App[None]):
    """Full-screen Textual application that drives the adventure game loop.

    Layout:
      Left panel  — NarrativeLog (scrollable history) + ChoiceMenu (current prompt)
      Right panel — StatusPanel (player stats) + RegionPanel (current region)
      Footer      — always-visible key binding hints

    The game loop runs as an exclusive Textual worker started in on_mount().
    """

    CSS = """
    Screen {
        layout: vertical;
    }
    #game-area {
        height: 1fr;
    }
    #left-panel {
        width: 3fr;
    }
    #right-panel {
        width: 1fr;
        min-width: 24;
    }
    #name-input {
        dock: bottom;
        display: none;
    }
    #help-content {
        background: $surface;
        border: double $primary;
        padding: 2 4;
        width: auto;
        height: auto;
        margin: 4 8;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("question_mark", "toggle_help", "Help", show=True),
    ]

    def __init__(self, registry: ContentRegistry) -> None:
        super().__init__()
        self._content_registry = registry
        self._name_event: asyncio.Event | None = None
        self._player_name: str = ""

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Vertical(
                NarrativeLog(highlight=True, markup=True),
                ChoiceMenu(),
                id="left-panel",
            ),
            Vertical(
                StatusPanel(),
                RegionPanel(),
                id="right-panel",
            ),
            id="game-area",
        )
        yield Footer()
        yield Input(placeholder="Enter your character name…", id="name-input")

    def on_mount(self) -> None:
        self._game_loop()

    # ── Name-prompt helpers ──────────────────────────────────────────────────

    async def _prompt_name(self) -> str:
        """Show the name Input widget and wait for a non-empty submission."""
        self._name_event = asyncio.Event()
        self._player_name = ""
        name_input = self.query_one("#name-input", Input)
        name_input.display = True
        name_input.focus()
        await self._name_event.wait()
        name_input.display = False
        self._name_event = None
        return self._player_name or "Hero"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if self._name_event is not None and value:
            self._player_name = value
            self._name_event.set()
        event.stop()

    # ── Key bindings ─────────────────────────────────────────────────────────

    async def action_toggle_help(self) -> None:
        await self.push_screen(HelpOverlay())

    # ── Game loop worker ─────────────────────────────────────────────────────

    @work(exclusive=True)
    async def _game_loop(self) -> None:
        """Drive the full game session — region/location selection and pipeline."""
        from oscilla.engine.conditions import evaluate
        from oscilla.engine.pipeline import AdventurePipeline
        from oscilla.engine.player import PlayerState

        registry = self._content_registry

        if registry.game is None or registry.character_config is None:
            self.query_one(NarrativeLog).append_text("[red]Error: content not loaded properly.[/red]")
            return

        # ── Character setup ──────────────────────────────────────────────────
        name = await self._prompt_name()
        player = PlayerState.new_player(
            name=name,
            game_manifest=registry.game,
            character_config=registry.character_config,
        )

        status_panel = self.query_one(StatusPanel)
        status_panel.set_registry(registry)
        status_panel.refresh_player(player)

        tui = TextualTUI(self)

        # ── Main adventure loop ──────────────────────────────────────────────
        while True:
            # Region selection
            accessible_regions = [
                region for region in registry.regions.all() if evaluate(region.spec.effective_unlock, player)
            ]
            if not accessible_regions:
                self.query_one(NarrativeLog).append_text(
                    "[red]Error: no accessible regions found.[/red] Ensure your root region has no unlock condition."
                )
                break

            region_options = [r.spec.displayName for r in accessible_regions] + ["Quit"]
            region_choice = await tui.show_menu("Where would you like to go?", region_options)
            if region_choice == len(region_options):
                self.query_one(NarrativeLog).append_text("\n[bold]Goodbye![/bold]")
                self.exit()
                return

            region_ref = accessible_regions[region_choice - 1].metadata.name
            region = registry.regions.require(region_ref, "Region")
            self.query_one(RegionPanel).set_region(
                name=region.spec.displayName,
                description=region.spec.description,
            )

            # Location selection — inner loop keeps player in region after adventures
            while True:
                accessible_locs = [
                    loc
                    for loc in registry.locations.all()
                    if loc.spec.region == region_ref and evaluate(loc.spec.effective_unlock, player)
                ]

                if not accessible_locs:
                    await tui.show_text(f"There are no accessible locations in {region.spec.displayName} yet.")
                    break

                loc_options = [loc.spec.displayName for loc in accessible_locs] + ["Back"]
                loc_choice = await tui.show_menu("Location:", loc_options)
                if loc_choice == len(loc_options):
                    # Player chose Back → return to region selection
                    break

                location_ref = accessible_locs[loc_choice - 1].metadata.name
                location = registry.locations.require(location_ref, "Location")

                # Adventure selection (weighted random from eligible pool)
                eligible = [entry for entry in location.spec.adventures if evaluate(entry.requires, player)]
                if not eligible:
                    await tui.show_text("No adventures are available here right now.")
                    continue

                weights = [entry.weight for entry in eligible]
                (chosen_entry,) = random.choices(population=eligible, weights=weights, k=1)
                adventure_ref = chosen_entry.ref

                player.statistics.record_location_visited(location_ref)

                pipeline = AdventurePipeline(registry=registry, player=player, tui=tui)
                outcome = await pipeline.run(adventure_ref)

                message = _OUTCOME_MESSAGES.get(outcome.value, f"Adventure ended: {outcome.value}")
                await tui.show_text(message)

                status_panel.refresh_player(player)


# ─── TextualTUI protocol implementation ──────────────────────────────────────


class TextualTUI:
    """Implements the async TUICallbacks protocol using the OscillaApp widgets.

    Each method updates the appropriate widget in the Textual tree and, where
    player input is required, suspends the caller via asyncio.Event until the
    widget signals completion. The game loop worker (running on the same event
    loop) resumes only after the event fires.

    To implement a future WebSocketTUI, satisfy the same four async methods
    (show_text, show_menu, show_combat_round, wait_for_ack) backed by
    WebSocket send/receive instead of Textual widget calls.
    """

    def __init__(self, app: OscillaApp) -> None:
        self._app = app

    async def show_text(self, text: str) -> None:
        """Append a narrative passage to the scrollable log. Does not wait."""
        self._app.query_one(NarrativeLog).append_text(text)

    async def show_menu(self, prompt: str, options: List[str]) -> int:
        """Show the prompt in the narrative log and wait for option selection.

        Returns the 1-based index of the chosen option.
        """
        if prompt:
            self._app.query_one(NarrativeLog).append_text(f"[bold]{prompt}[/bold]")
        return await self._app.query_one(ChoiceMenu).wait_for_selection(options)

    async def show_combat_round(
        self,
        player_hp: int,
        enemy_hp: int,
        player_name: str,
        enemy_name: str,
    ) -> None:
        """Append a HP table to the narrative log. Does not wait for input."""
        table = Table(title="Combat", show_header=True, header_style="bold red")
        table.add_column("Combatant", style="bold")
        table.add_column("HP", justify="right", style="green")
        table.add_row(player_name, str(player_hp))
        table.add_row(enemy_name, str(enemy_hp))
        self._app.query_one(NarrativeLog).write(table)

    async def wait_for_ack(self) -> None:
        """Show a Continue option in the choice widget and wait for confirmation."""
        await self._app.query_one(ChoiceMenu).wait_for_selection(["▶  Press Enter to continue"])
