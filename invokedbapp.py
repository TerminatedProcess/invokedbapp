#!/usr/bin/env python3
"""InvokeAI Models Viewer - Terminal UI for browsing and filtering InvokeAI models."""

import sqlite3
import json
import yaml
from pathlib import Path
from typing import List, Dict, Any

import pyperclip
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, DataTable, Input, Static, Label
from textual.binding import Binding
from textual.reactive import reactive


class ModelDatabase:
    """Handle database operations for InvokeAI models."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._models = []

    def load_models(self) -> List[Dict[str, Any]]:
        """Load all models from the database."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found at: {self.db_path}")

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    json_extract(config, '$.name') AS model_name,
                    json_extract(config, '$.type') AS model_type,
                    json_extract(config, '$.base') AS model_base,
                    json_extract(config, '$.trigger_phrases') AS trigger_phrases,
                    json_extract(config, '$.path') AS model_path
                FROM models
                ORDER BY model_name COLLATE NOCASE ASC
                """
            )
            rows = cursor.fetchall()
            conn.close()

            models = []
            for row in rows:
                model_name, model_type, model_base, trigger_phrases_json, model_path = row

                # Parse trigger phrases
                triggers = []
                if trigger_phrases_json:
                    try:
                        triggers = json.loads(trigger_phrases_json)
                        if not isinstance(triggers, list):
                            triggers = [str(triggers)]
                    except (json.JSONDecodeError, TypeError):
                        triggers = []

                # Extract file extension from path and append to name
                ext = Path(model_path).suffix if model_path else ""
                display_name = f"{model_name or 'Unknown'}{ext}"

                models.append({
                    "name": display_name,
                    "type": model_type or "Unknown",
                    "subtype": model_base or "Unknown",
                    "triggers": ", ".join(triggers) if triggers else "",
                    "path": model_path or "",
                })

            self._models = models
            return models

        except sqlite3.Error as e:
            raise RuntimeError(f"Database error: {e}")


def load_config() -> tuple[Path, Path]:
    """Load database path from config.yaml.

    Returns:
        tuple[Path, Path]: (invokeai_data_path, database_path)
    """
    config_path = Path("config.yaml")
    if not config_path.exists():
        raise FileNotFoundError("config.yaml not found")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    invokeai_data_path = config.get('invokeai_data_path')
    if not invokeai_data_path:
        raise ValueError("invokeai_data_path not found in config.yaml")

    data_path = Path(invokeai_data_path)
    db_path = data_path / "databases" / "invokeai.db"

    return data_path, db_path


class InvokeAIViewer(App):
    """A Textual app to view and filter InvokeAI models."""

    CSS = """
    Screen {
        background: #1a1a1a;
    }

    #filters {
        height: auto;
        background: #2a2a2a;
        border: solid #444;
        color: white;
    }

    .filter-row {
        height: auto;
        width: 100%;
        padding: 0 1;
    }

    .filter-label {
        width: 9;
        content-align: right middle;
        color: #aaa;
        text-style: bold;
    }

    Input {
        width: 1fr;
        margin: 0 1 0 0;
        background: #333333;
        color: #ffffff !important;
        height: 3;
        padding: 0 1;
    }

    #input_name, #input_type, #input_subtype, #input_triggers {
        background: #333333 !important;
        color: #ffffff !important;
        height: 3;
    }

    Input > .input--placeholder {
        color: gray !important;
    }

    Input:focus {
        border: tall #ff8800;
        color: white !important;
    }

    DataTable {
        height: 1fr;
        background: #1a1a1a;
    }

    DataTable > .datatable--header {
        background: #2a2a2a;
        color: white;
    }

    DataTable > .datatable--cursor {
        background: #ff8800;
        color: black;
    }

    #status {
        height: 3;
        padding: 1;
        background: #2a2a2a;
        color: white;
    }

    Static {
        color: white;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True, show=False),
        Binding("escape", "quit", "Quit", priority=True, show=False),
        Binding("f", "focus_filter", "Focus Filter", priority=True, show=False),
        Binding("r", "reset_filters", "Reset", priority=True),
        Binding("s", "generate_symlinks", "Symlinks", priority=True),
    ]

    TITLE = "InvokeAI Models Viewer"

    # Reactive filters
    filter_name = reactive("")
    filter_type = reactive("")
    filter_subtype = reactive("")

    def __init__(self):
        super().__init__()
        self.data_path, self.db_path = load_config()
        self.db = ModelDatabase(self.db_path)
        self.all_models = []
        self.filtered_models = []
        self.sort_column = "name"  # Default sort by name
        self.sort_reverse = False

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()

        with Container(id="filters"):
            with Horizontal(classes="filter-row"):
                yield Static("Model:", classes="filter-label")
                yield Input(placeholder="filter...", id="input_name")
                yield Static("Type:", classes="filter-label")
                yield Input(placeholder="filter...", id="input_type")
                yield Static("Base Model:", classes="filter-label")
                yield Input(placeholder="filter...", id="input_subtype")

        yield DataTable(id="models_table")

        with Container(id="status"):
            yield Static("Loading models...", id="status_text")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app after mounting."""
        # Setup table with fixed column widths
        table = self.query_one("#models_table", DataTable)
        table.add_column("Model ▼", width=120)
        table.add_column("Type", width=24)
        table.add_column("Base Model", width=16)
        table.cursor_type = "row"

        # Load models
        try:
            self.all_models = self.db.load_models()
            self.filtered_models = self.all_models.copy()
            self.update_table()
            self.update_status()
        except Exception as e:
            self.update_status_text(f"Error loading models: {e}", error=True)

    def on_data_table_header_selected(self, event) -> None:
        """Handle column header clicks for sorting."""
        table = self.query_one("#models_table", DataTable)

        # Map column index to field name
        column_map = {0: "name", 1: "type", 2: "subtype"}
        selected_column = column_map.get(event.column_index)

        if selected_column is None:
            return

        # Toggle sort direction if clicking same column
        if self.sort_column == selected_column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = selected_column
            self.sort_reverse = False

        # Update column headers with sort indicator
        headers = ["Model", "Type", "Base Model"]
        sort_indicator = " ▼" if not self.sort_reverse else " ▲"
        headers[event.column_index] = headers[event.column_index] + sort_indicator

        # Clear and re-add columns with consistent widths
        table.clear(columns=True)
        table.add_column(headers[0], width=120)  # Model
        table.add_column(headers[1], width=24)   # Type
        table.add_column(headers[2], width=16)   # Base Model

        # Re-sort and update table
        self.apply_filters()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes for live filtering."""
        input_id = event.input.id

        if input_id == "input_name":
            self.filter_name = event.value.lower()
        elif input_id == "input_type":
            self.filter_type = event.value.lower()
        elif input_id == "input_subtype":
            self.filter_subtype = event.value.lower()

        self.apply_filters()

    def apply_filters(self) -> None:
        """Apply all active filters to the model list."""
        filtered = self.all_models.copy()

        if self.filter_name:
            filtered = [m for m in filtered if self.filter_name in m["name"].lower()]

        if self.filter_type:
            filtered = [m for m in filtered if self.filter_type in m["type"].lower()]

        if self.filter_subtype:
            filtered = [m for m in filtered if self.filter_subtype in m["subtype"].lower()]

        # Sort the filtered results
        filtered.sort(key=lambda x: x[self.sort_column].lower(), reverse=self.sort_reverse)

        self.filtered_models = filtered
        self.update_table()
        self.update_status()

    def update_table(self) -> None:
        """Update the DataTable with filtered models."""
        table = self.query_one("#models_table", DataTable)
        table.clear()

        for model in self.filtered_models:
            table.add_row(
                model["name"],
                model["type"],
                model["subtype"]
            )

    def update_status(self) -> None:
        """Update the status bar with current filter stats."""
        total = len(self.all_models)
        filtered = len(self.filtered_models)

        if filtered == total:
            msg = f"Showing all {total} models | Database: {self.db_path}"
        else:
            msg = f"Showing {filtered} of {total} models | Database: {self.db_path}"

        self.update_status_text(msg)

    def update_status_text(self, text: str, error: bool = False) -> None:
        """Update the status text widget."""
        status = self.query_one("#status_text", Static)
        status.update(text)
        if error:
            status.styles.color = "red"
        else:
            status.styles.color = "white"

    def action_focus_filter(self) -> None:
        """Focus the first filter field (hotkey: F)."""
        self.query_one("#input_name", Input).focus()

    def action_reset_filters(self) -> None:
        """Reset all filters (hotkey: R)."""
        self.query_one("#input_name", Input).value = ""
        self.query_one("#input_type", Input).value = ""
        self.query_one("#input_subtype", Input).value = ""

        self.filter_name = ""
        self.filter_type = ""
        self.filter_subtype = ""

        self.apply_filters()
        self.update_status_text("Filters reset")

    def action_generate_symlinks(self) -> None:
        """Generate symlink commands and copy to clipboard (hotkey: S)."""
        if not self.filtered_models:
            self.update_status_text("No models to generate symlinks for", error=True)
            return

        symlinks = []
        for model in self.filtered_models:
            model_path = model["path"]
            if model_path and model_path.strip():
                # Construct full path: data_path / models / path
                # Structure: /mnt/llm/hub/invokeai_data/models/{UUID}/{filename}
                full_path = self.data_path / "models" / model_path
                symlinks.append(f'ln -s "{full_path}" .')

        if not symlinks:
            self.update_status_text("No valid model paths found", error=True)
            return

        symlink_text = "\n".join(symlinks)

        try:
            pyperclip.copy(symlink_text)
            count = len(symlinks)
            self.update_status_text(f"✓ Copied {count} symlink command{'s' if count > 1 else ''} to clipboard!")
        except Exception as e:
            self.update_status_text(f"Failed to copy to clipboard: {e}", error=True)


def main():
    """Run the InvokeAI Viewer TUI."""
    app = InvokeAIViewer()
    app.run()


if __name__ == "__main__":
    main()
