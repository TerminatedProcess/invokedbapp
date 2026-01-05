# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Terminal UI application (Textual framework) for browsing and filtering InvokeAI model metadata from a SQLite database. Provides real-time filtering, column sorting, and clipboard integration for batch model operations.

## Architecture

**Single-file application:**
- `invokedbapp.py` - Textual TUI app with all UI and database logic

**Core classes:**
1. **ModelDatabase** - SQLite query layer, extracts JSON model metadata
2. **InvokeAIViewer** - Main Textual App with reactive filtering

**Data flow:**
- Config (`config.yaml`) → Database path → SQLite query → JSON extraction → Reactive filters → DataTable display

**Database schema:**
- Table: `models`
- JSON fields in `config` column: `name`, `type`, `base` (displayed as "subtype"), `trigger_phrases`, `path`

## Development Commands

**Environment setup:**
```bash
mkenv          # Create venv (uv, Python 3.12.10)
install        # Install dependencies
rmenv          # Clean environment and exit
```

**Run the app:**
```bash
run            # Alias for: python invokedbapp.py
```

**Dependencies:**
- `textual` - Terminal UI framework
- `pyyaml` - Config parsing
- `pyperclip` - Clipboard integration

## Configuration

`config.yaml` specifies InvokeAI installation location:
```yaml
invokeai_data_path: /mnt/llm/hub/invokeai_data
```

Database path is constructed in `load_config()`: `{invokeai_data_path}/databases/invokeai.db`

## Key Features & Keybindings

- **Live filtering**: Four simultaneous text filters (Model, Type, Subtype, Triggers)
- **Column sorting**: Click headers to sort, toggle ascending/descending
- **Symlink generation**: Press `s` to copy `ln -s` commands for filtered models to clipboard
- **Reset filters**: Press `r` to clear all filters
- **Quit**: Press `q` or `Esc`

## UI Architecture

**Reactive properties** (`textual.reactive`):
- `filter_name`, `filter_type`, `filter_subtype`, `filter_triggers`
- Changes trigger `apply_filters()` → `update_table()` → `update_status()`

**Component hierarchy:**
- Header → Filter inputs (4 horizontal) → DataTable → Status bar → Footer

**Styling:**
- CSS-in-Python via `CSS` class attribute
- Custom colors: Dark theme with orange accents (`#ff8800`)
- Column widths: Fixed percentages (40/12/12/36)

## Database Query Pattern

SQLite JSON extraction for nested config fields:
```sql
json_extract(config, '$.name') AS model_name
json_extract(config, '$.trigger_phrases') AS trigger_phrases
```

Trigger phrases are parsed from JSON arrays and joined as comma-separated strings.

## Implementation Notes

- **Sorting**: Maintains sort state across filtering operations via `sort_column` and `sort_reverse` attributes
- **Case-insensitive**: All filters use `.lower()` for string comparison
- **Column re-rendering**: Sorting updates column headers with visual indicators (▼/▲)
- **Clipboard robustness**: Catches `pyperclip.copy()` exceptions and displays errors in status bar
