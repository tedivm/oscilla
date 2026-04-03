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
from typing import TYPE_CHECKING, Any, Dict, List
from uuid import UUID

from rich.panel import Panel
from rich.table import Table
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.stylesheet import StylesheetParseError
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, Label, OptionList, RichLog, Static, TabbedContent, TabPane

from oscilla.engine.character import cascade_unequip_invalid, validate_equipped_requires
from oscilla.engine.conditions import evaluate
from oscilla.engine.session import GameSession
from oscilla.engine.steps.effects import run_effect
from oscilla.services.crash import _GITHUB_ISSUES_URL, write_crash_report
from oscilla.services.db import get_session

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
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

    refresh_player() re-renders the panel from a CharacterState snapshot.
    Only stats declared in public_stats of CharacterConfig are shown;
    hidden stats are never displayed.
    """

    DEFAULT_CSS = """
    StatusPanel {
        border: solid $success;
        padding: 1;
        height: 100%;
        min-height: 8;
    }
    """

    def __init__(self) -> None:
        super().__init__("")
        self._registry: ContentRegistry | None = None

    def set_registry(self, registry: ContentRegistry) -> None:
        self._registry = registry

    def refresh_player(self, player: CharacterState) -> None:
        """Re-render the status panel from the current CharacterState."""
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

        # Warn about any equipped items whose requirements are no longer met.
        invalid_refs = validate_equipped_requires(player=player, registry=self._registry)
        if invalid_refs:
            lines.append("")
            lines.append("[bold red]⚠ Invalid equipment:[/bold red]")
            for ref in invalid_refs:
                item_mf = self._registry.items.get(ref)
                name = item_mf.spec.displayName if item_mf else ref
                lines.append(f"  [red]• {name}[/red]")

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


class InventoryScreen(ModalScreen[None]):
    """Modal inventory screen showing equipped items and backpack contents.

    Equip buttons are hidden when the player is inside an active adventure
    (in_adventure=True) since equipping mid-combat is not permitted.
    """

    BINDINGS = [
        Binding("escape", "dismiss_inventory", "Close"),
        Binding("i", "dismiss_inventory", "Close"),
    ]

    CSS = """
    #inventory-container {
        background: $surface;
        border: double $primary;
        padding: 1 2;
        width: 80%;
        height: auto;
        max-height: 80%;
        margin: 4 8;
    }
    #inventory-title {
        text-style: bold;
        margin-bottom: 1;
    }
    .item-row {
        height: 3;
        align: left middle;
    }
    .item-name {
        width: 1fr;
        content-align: left middle;
    }
    .item-action {
        width: auto;
        min-width: 9;
        margin-left: 1;
    }
    """

    def __init__(
        self,
        player: "CharacterState",
        registry: "ContentRegistry",
        in_adventure: bool = False,
    ) -> None:
        super().__init__()
        self._player = player
        self._registry = registry
        self._in_adventure = in_adventure

    def compose(self) -> ComposeResult:  # noqa: C901
        equipped_ids = set(v for v in self._player.equipment.values() if v is not None)

        # Build label display maps from GameSpec if available.
        label_color_map: Dict[str, str] = {}
        label_sort_map: Dict[str, int] = {}
        if self._registry.game is not None:
            for lbl_def in self._registry.game.spec.item_labels:
                label_color_map[lbl_def.name] = lbl_def.color
                label_sort_map[lbl_def.name] = lbl_def.sort_priority

        def _label_badges(labels: List[str]) -> str:
            """Render label names as Rich markup badges, coloured when a colour is declared."""
            parts: List[str] = []
            for lbl in labels:
                color = label_color_map.get(lbl, "")
                if color:
                    parts.append(f"[{color}][{lbl}][/{color}]")
                else:
                    parts.append(f"[dim][{lbl}][/dim]")
            return " ".join(parts)

        def _item_sort_key(kind_data: tuple[str, Any]) -> tuple[int, str]:
            """Sort by lowest label sort_priority among the item's labels, then display name."""
            kind, data = kind_data
            if kind == "stack":
                item_ref, qty, item_mf = data
                labels = item_mf.spec.labels if item_mf else []
                name = item_mf.spec.displayName if item_mf else item_ref
            else:
                inst, item_mf = data
                labels = item_mf.spec.labels if item_mf else []
                name = item_mf.spec.displayName if item_mf else inst.item_ref
            prio = min((label_sort_map.get(lbl, 0) for lbl in labels), default=0)
            return (prio, name)

        # Collect items by category
        categories: Dict[str, List[tuple[str, Any]]] = {}  # category -> [(kind, data)]
        for item_ref, qty in self._player.stacks.items():
            item_mf = self._registry.items.get(item_ref)
            cat = item_mf.spec.category if item_mf else "misc"
            categories.setdefault(cat, []).append(("stack", (item_ref, qty, item_mf)))
        for inst in self._player.instances:
            item_mf = self._registry.items.get(inst.item_ref)
            cat = item_mf.spec.category if item_mf else "misc"
            categories.setdefault(cat, []).append(("instance", (inst, item_mf)))

        with Vertical(id="inventory-container"):
            yield Label("[bold]Inventory[/bold]", id="inventory-title")

            if not categories:
                yield Label("  [dim](empty)[/dim]")
            else:
                with TabbedContent():
                    for cat_name, items in sorted(categories.items()):
                        sorted_items = sorted(items, key=_item_sort_key)
                        with TabPane(cat_name.capitalize(), id=f"cat-{cat_name}"):
                            for kind, data in sorted_items:
                                if kind == "stack":
                                    item_ref, qty, item_mf = data
                                    item_name = item_mf.spec.displayName if item_mf else item_ref
                                    labels = item_mf.spec.labels if item_mf else []
                                    badges = f" {_label_badges(labels)}" if labels else ""
                                    with Horizontal(classes="item-row"):
                                        yield Label(
                                            f"[bold]{item_name}[/bold]{badges} [dim]x{qty}[/dim]",
                                            classes="item-name",
                                        )
                                        if item_mf and item_mf.spec.use_effects:
                                            yield Button(
                                                "Use",
                                                name=f"use_stack:{item_ref}",
                                                variant="success",
                                                classes="item-action",
                                            )
                                        if item_mf and item_mf.spec.droppable:
                                            yield Button(
                                                "Discard",
                                                name=f"discard_stack:{item_ref}",
                                                variant="error",
                                                classes="item-action",
                                            )
                                else:
                                    inst, item_mf = data
                                    is_equipped = inst.instance_id in equipped_ids
                                    item_name = item_mf.spec.displayName if item_mf else inst.item_ref
                                    labels = item_mf.spec.labels if item_mf else []
                                    badges = f" {_label_badges(labels)}" if labels else ""
                                    status = " [dim][equipped][/dim]" if is_equipped else ""
                                    charges_text = ""
                                    if inst.charges_remaining is not None:
                                        charges_text = f" [dim]({inst.charges_remaining} charges)[/dim]"
                                    with Horizontal(classes="item-row"):
                                        yield Label(
                                            f"[bold]{item_name}[/bold]{badges}{status}{charges_text}",
                                            classes="item-name",
                                        )
                                        if is_equipped:
                                            # Find which slot this instance occupies
                                            slot_name = next(
                                                (
                                                    s
                                                    for s, iid in self._player.equipment.items()
                                                    if iid == inst.instance_id
                                                ),
                                                None,
                                            )
                                            if slot_name:
                                                yield Button(
                                                    "Unequip",
                                                    name=f"unequip:{slot_name}",
                                                    variant="warning",
                                                    classes="item-action",
                                                )
                                        elif not self._in_adventure and item_mf and item_mf.spec.equip:
                                            yield Button(
                                                "Equip",
                                                name=f"equip:{str(inst.instance_id)}",
                                                variant="primary",
                                                classes="item-action",
                                            )
                                        if item_mf and item_mf.spec.use_effects:
                                            yield Button(
                                                "Use",
                                                name=f"use_instance:{str(inst.instance_id)}",
                                                variant="success",
                                                classes="item-action",
                                            )
                                        if item_mf and item_mf.spec.droppable and not is_equipped:
                                            yield Button(
                                                "Discard",
                                                name=f"discard_instance:{str(inst.instance_id)}",
                                                variant="error",
                                                classes="item-action",
                                            )

            yield Button("Close", id="close-inventory-btn", variant="default")

    async def _recompose_preserving_state(self, acted_button: Button) -> None:
        """Recompose widget tree while restoring active tab and nearest focus position.

        Saves the active TabbedContent tab and the index of the acted-upon button
        within that tab's button list, then restores both after the recompose.
        """
        active_tab: str | None = None
        focus_idx: int = 0
        try:
            tc = self.query_one(TabbedContent)
            active_tab = tc.active
            if active_tab:
                pane = self.query_one(f"#{active_tab}")
                buttons = list(pane.query(Button))
                if acted_button in buttons:
                    focus_idx = buttons.index(acted_button)
        except Exception:
            pass

        await self.recompose()

        try:
            if active_tab:
                self.query_one(TabbedContent).active = active_tab
                pane = self.query_one(f"#{active_tab}")
                buttons = list(pane.query(Button))
                if buttons:
                    buttons[min(focus_idx, len(buttons) - 1)].focus()
        except Exception:
            pass

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch equip/unequip/use actions from inventory buttons."""
        try:
            await self._handle_button(event)
        except Exception:
            logger.exception("Inventory button handler raised an unhandled exception")

    async def _handle_button(self, event: Button.Pressed) -> None:
        """Inner dispatch for on_button_pressed — exceptions bubble to the caller's logger."""
        if event.button.id == "close-inventory-btn":
            self.dismiss()
            return

        btn_name = event.button.name or ""
        if ":" not in btn_name:
            return

        action, _, arg = btn_name.partition(":")

        if action == "unequip":
            self._player.unequip_slot(arg)
            cascaded = cascade_unequip_invalid(player=self._player, registry=self._registry)
            if cascaded:
                names = ", ".join(cascaded)
                self.notify(f"Also unequipped: {names} (requirements no longer met)", severity="warning")
            await self._recompose_preserving_state(event.button)
        elif action == "equip":
            instance_id = UUID(arg)
            inst = next((i for i in self._player.instances if i.instance_id == instance_id), None)
            if inst is not None:
                item_mf = self._registry.items.get(inst.item_ref)
                if item_mf is not None and item_mf.spec.equip is not None:
                    # Check equip requirements before allowing equip.
                    requires = item_mf.spec.equip.requires
                    if requires is None or evaluate(
                        condition=requires,
                        player=self._player,
                        registry=self._registry,
                        exclude_item=inst.item_ref,
                    ):
                        self._player.equip_instance(instance_id=instance_id, slots=item_mf.spec.equip.slots)
                    else:
                        self.notify(
                            f"Cannot equip {item_mf.spec.displayName}: requirements not met.",
                            severity="error",
                        )
            await self._recompose_preserving_state(event.button)
        elif action == "use_stack":
            await self._use_stack(arg)
            await self._recompose_preserving_state(event.button)
        elif action == "use_instance":
            await self._use_instance(UUID(arg))
            await self._recompose_preserving_state(event.button)
        elif action == "discard_stack":
            self._player.remove_item(ref=arg, quantity=1)
            await self._recompose_preserving_state(event.button)
        elif action == "discard_instance":
            self._player.remove_instance(UUID(arg))
            await self._recompose_preserving_state(event.button)

        # Refresh status panel after any inventory change
        app = self.app
        if isinstance(app, OscillaApp):
            app.query_one(StatusPanel).refresh_player(self._player)

    async def _use_stack(self, item_ref: str) -> None:
        """Run use_effects for a stackable item and consume it if needed."""
        item_mf = self._registry.items.get(item_ref)
        if item_mf is None:
            return
        app = self.app
        if not isinstance(app, OscillaApp) or app._tui is None:
            return
        for eff in item_mf.spec.use_effects:
            await run_effect(player=self._player, effect=eff, registry=self._registry, tui=app._tui)
        if item_mf.spec.consumed_on_use:
            self._player.remove_item(ref=item_ref, quantity=1)

    async def _use_instance(self, instance_id: UUID) -> None:
        """Run use_effects for a non-stackable item instance and consume it if needed."""
        inst = next((i for i in self._player.instances if i.instance_id == instance_id), None)
        if inst is None:
            return
        item_mf = self._registry.items.get(inst.item_ref)
        if item_mf is None:
            return
        app = self.app
        if not isinstance(app, OscillaApp) or app._tui is None:
            return
        for eff in item_mf.spec.use_effects:
            await run_effect(player=self._player, effect=eff, registry=self._registry, tui=app._tui)
        if item_mf.spec.consumed_on_use:
            self._player.remove_instance(instance_id=instance_id)

    def action_dismiss_inventory(self) -> None:
        self.dismiss()


class GameSelectScreen(ModalScreen[str]):
    """Modal screen for selecting a game when multiple games are available."""

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
    ]

    CSS = """
    #game-select {
        background: $surface;
        border: double $primary;
        padding: 2 4;
        width: auto;
        height: auto;
        margin: 4 8;
    }
    #game-list {
        min-height: 10;
        max-height: 20;
    }
    """

    def __init__(self, games: "Dict[str, ContentRegistry]") -> None:
        super().__init__()
        self.games = games

    def compose(self) -> ComposeResult:
        # Build options list with display names and descriptions
        options = []
        self.game_keys = []  # Keep track of the order for selection
        for game_key, registry in sorted(self.games.items()):
            if registry.game is not None:
                display_name = registry.game.spec.displayName
                description = getattr(registry.game.spec, "description", "")
                if description:
                    option_text = f"{display_name} — {description}"
                else:
                    option_text = display_name
                options.append(option_text)
                self.game_keys.append(game_key)
            else:
                # Fallback if no game manifest
                options.append(f"{game_key} (no game manifest)")
                self.game_keys.append(game_key)

        yield Static("Select a game to play:", id="game-select")
        yield OptionList(*options, id="game-list")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle game selection."""
        selected_index = event.option_list.highlighted
        if selected_index is not None and selected_index < len(self.game_keys):
            selected_game = self.game_keys[selected_index]
            self.dismiss(selected_game)


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
        height: 100%;
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
        Binding("i", "open_inventory", "Inventory"),
        Binding("question_mark", "toggle_help", "Help", show=True),
    ]

    def __init__(
        self,
        games: "Dict[str, ContentRegistry] | None" = None,
        registry: "ContentRegistry | None" = None,
        game_name: str | None = None,
        character_name: str | None = None,
    ) -> None:
        super().__init__()
        self._games = games
        self._content_registry = registry
        self._game_name = game_name
        self._character_name = character_name
        self._name_event: asyncio.Event | None = None
        self._player_name: str = ""
        self._player: "CharacterState | None" = None
        self._tui: "TextualTUI | None" = None
        self._in_adventure: bool = False

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

    async def action_open_inventory(self) -> None:
        """Open the inventory modal if a game session is active."""
        if self._player is not None and self._content_registry is not None:
            try:
                self.push_screen(InventoryScreen(self._player, self._content_registry, self._in_adventure))
            except StylesheetParseError as exc:
                logger.exception("CSS parse error when loading inventory screen")
                # Try to extract more details about the parse error
                error_details = f"StylesheetParseError: {exc}"
                if hasattr(exc, "errors") and exc.errors:
                    error_details += f"\nCSS Errors: {exc.errors}"
                if hasattr(exc, "error_renderable") and exc.error_renderable:
                    error_details += f"\nError Renderable: {exc.error_renderable}"
                logger.error(f"CSS Parse Error Details: {error_details}")
                crash_path = write_crash_report(exc)
                self.query_one(NarrativeLog).append_text(
                    "[bold red]CSS parsing error in inventory screen.[/bold red]\n"
                    f"This is a stylesheet syntax issue.\n"
                    f"Crash report with details saved to: [bold]{crash_path}[/bold]\n"
                    f"Please report this bug at {_GITHUB_ISSUES_URL}"
                )
                return
            except Exception as exc:
                logger.exception("Inventory screen raised an unhandled exception")
                crash_path = write_crash_report(exc)
                self.query_one(NarrativeLog).append_text(
                    "[bold red]The inventory screen encountered an error.[/bold red]\n"
                    f"Crash report saved to: [bold]{crash_path}[/bold]\n"
                    f"Please report this bug at {_GITHUB_ISSUES_URL}"
                )
                return
            # Note: Status panel will be refreshed when inventory buttons
            # modify player state, not when inventory opens

    # ── Cleanup ──────────────────────────────────────────────────────────────

    async def on_unmount(self) -> None:
        """Handle app shutdown cleanup.

        This ensures database connections are properly closed when the app
        exits unexpectedly (e.g., Ctrl+C). Without this, SQLAlchemy may try
        to rollback connections after the asyncio event loop is cancelled,
        causing a spurious CancelledError.
        """
        try:
            from oscilla.services.db import engine

            await engine.dispose()
        except Exception:
            # Suppress any errors during cleanup - the app is already shutting down
            pass

    # ── Game loop worker ─────────────────────────────────────────────────────

    @work(exclusive=True)
    async def _game_loop(self) -> None:
        """Drive the full game session — character setup, region/location selection, and pipeline."""
        try:
            await self._run_game()
        except Exception as exc:
            logger.exception("Unhandled exception in game loop")
            crash_path = write_crash_report(exc)
            # Try to surface the error inside the TUI so the player can read it
            # before pressing Ctrl+Q.  If even this fails the exception will
            # propagate to Textual and eventually out of run_async().
            self.query_one(NarrativeLog).append_text(
                "[bold red]An unexpected error occurred.[/bold red]\n"
                f"Crash report saved to: [bold]{crash_path}[/bold]\n"
                f"Please report this bug at {_GITHUB_ISSUES_URL}\n"
                "Press [bold]Ctrl+Q[/bold] to exit."
            )

    async def _run_game(self) -> None:
        """Inner game loop — separated so _game_loop can wrap it cleanly."""
        # Handle game selection if needed
        if self._content_registry is None:
            if self._games is None:
                self.query_one(NarrativeLog).append_text("[red]Error: no games provided.[/red]")
                return

            if len(self._games) == 1:
                # Auto-select single game
                game_name = next(iter(self._games))
                registry = self._games[game_name]
            else:
                # Show game selection screen
                try:
                    game_name = await self.push_screen_wait(GameSelectScreen(self._games))
                    if game_name is None:  # User cancelled
                        return
                    registry = self._games[game_name]
                except Exception:
                    # User cancelled or other error
                    return

            self._content_registry = registry
            self._game_name = game_name

        registry = self._content_registry

        if registry.game is None or registry.character_config is None:
            self.query_one(NarrativeLog).append_text("[red]Error: content not loaded properly.[/red]")
            return

        status_panel = self.query_one(StatusPanel)
        status_panel.set_registry(registry)

        tui = TextualTUI(self)
        self._tui = tui
        # Track whether the player explicitly quit so self.exit() is called only
        # after both async-with blocks have exited cleanly.  Calling self.exit()
        # inside the context managers can cause Textual to cancel the worker
        # before SQLAlchemy's connection-pool rollback completes, producing a
        # spurious CancelledError on shutdown.
        user_quit = False

        async with get_session() as db_session:
            assert self._game_name is not None  # Guaranteed by game selection logic above
            try:
                async with GameSession(
                    registry=registry,
                    tui=tui,
                    db_session=db_session,
                    game_name=self._game_name,
                    character_name=self._character_name,
                ) as session:
                    await session.start()
                    player = session._character
                    if player is None:
                        self.query_one(NarrativeLog).append_text("[red]Error: character setup failed.[/red]")
                        return

                    status_panel.refresh_player(player)
                    self._player = player

                    while True:
                        # Region selection
                        accessible_regions = [
                            region
                            for region in registry.regions.all()
                            if evaluate(region.spec.effective_unlock, player, registry)
                        ]
                        if not accessible_regions:
                            self.query_one(NarrativeLog).append_text(
                                "[red]Error: no accessible regions found.[/red] "
                                "Ensure your root region has no unlock condition."
                            )
                            break

                        region_options = [r.spec.displayName for r in accessible_regions] + ["Quit"]
                        region_choice = await tui.show_menu("Where would you like to go?", region_options)
                        if region_choice == len(region_options):
                            self.query_one(NarrativeLog).append_text("\n[bold]Goodbye![/bold]")
                            user_quit = True
                            break

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
                                if loc.spec.region == region_ref
                                and evaluate(loc.spec.effective_unlock, player, registry)
                            ]

                            if not accessible_locs:
                                await tui.show_text(
                                    f"There are no accessible locations in {region.spec.displayName} yet."
                                )
                                break

                            loc_options = [loc.spec.displayName for loc in accessible_locs] + ["Back"]
                            loc_choice = await tui.show_menu("Location:", loc_options)
                            if loc_choice == len(loc_options):
                                # Player chose Back → return to region selection
                                break

                            location_ref = accessible_locs[loc_choice - 1].metadata.name
                            location = registry.locations.require(location_ref, "Location")

                            # Adventure selection (weighted random from eligible pool)
                            eligible = [
                                entry
                                for entry in location.spec.adventures
                                if evaluate(entry.requires, player, registry)
                            ]
                            if not eligible:
                                await tui.show_text("No adventures are available here right now.")
                                continue

                            weights = [entry.weight for entry in eligible]
                            (chosen_entry,) = random.choices(population=eligible, weights=weights, k=1)
                            adventure_ref = chosen_entry.ref

                            player.statistics.record_location_visited(location_ref)

                            self._in_adventure = True
                            outcome = await session.run_adventure(adventure_ref)
                            self._in_adventure = False

                            message = _OUTCOME_MESSAGES.get(outcome.value, f"Adventure ended: {outcome.value}")
                            await tui.show_text(message)

                            status_panel.refresh_player(player)
            except asyncio.CancelledError:
                # App is shutting down - suppress the cancellation to allow
                # clean database connection cleanup. Without this, SQLAlchemy
                # may attempt rollback after the event loop is cancelled.
                logger.debug("Game session cancelled during shutdown")
                raise

        # Both async-with blocks have now exited and their cleanup (session
        # commit/rollback, connection-pool reset) has completed successfully.
        if user_quit:
            self.exit()


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

    async def input_text(self, prompt: str) -> str:
        """Show the prompt in the narrative log then collect a single-line text response.

        Delegates to OscillaApp._prompt_name() which shows the Input widget
        and waits for the player to type and press Enter.
        """
        await self.show_text(prompt)
        return await self._app._prompt_name()

    async def show_skill_menu(self, skills: List[Dict[str, Any]]) -> int | None:
        """Display a skill selection menu and return the 1-based index of the chosen skill.

        Returns None if the player cancels without selecting.
        """
        if not skills:
            return None
        options = [f"{s['name']} — {s.get('description', '')}" for s in skills]
        options.append("Cancel")
        choice = await self.show_menu(prompt="Choose a skill:", options=options)
        if choice == len(options):
            return None
        return choice
