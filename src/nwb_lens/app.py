"""Main Textual application for NWB Lens."""

import json
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header
from textual.reactive import reactive
from textual import log

from nwb_lens.structure.json_converter import NWBJSONConverter
from nwb_lens.inspector.manager import InspectorManager
from nwb_lens.ui.tree import NWBTree
from nwb_lens.ui.panels import AttributePanel


class NWBLensApp(App):
    """Main TUI application for exploring NWB files."""
    
    # Reactive attribute to share selected object between widgets
    selected_object = reactive(None)
    
    # Load CSS from external file
    CSS_PATH = Path(__file__).parent / "ui" / "basic.tcss"
    
    BINDINGS = [
        ("i", "run_inspector", "Run Inspector"),
        ("o", "export_output", "Export JSON"),
        ("q", "quit", "Quit"),
        ("h", "show_help", "Help"),
    ]
    
    def __init__(self, json_file_path: Path, run_inspector: bool = False):
        super().__init__()
        self.json_file_path = json_file_path
        self.run_inspector = run_inspector
        self.inspector = InspectorManager()
        self.json_data = None
        self.original_nwb_path = None  # Will be set from JSON data
        self.inspector_results = None
    
    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header()
        yield Horizontal(
            NWBTree(id="tree"),
            AttributePanel(id="details")
        )
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the application after mounting."""
        self.theme = "solarized-light"

        # Load JSON structure
        try:
            with open(self.json_file_path, 'r') as f:
                self.json_data = json.load(f)
            
            # Extract original file info from JSON
            file_info = self.json_data.get('file_info', {})
            self.original_nwb_path = Path(file_info.get('path', 'unknown.nwb'))
            
            # Set title using the file name from JSON
            self.title = f"NWB Lens: {file_info.get('name', 'unknown.nwb')}"
            
            # Populate the tree with JSON data
            tree = self.query_one("#tree", NWBTree)
            tree.populate_from_json(self.json_data['structure'])
            
            log(f"App initialized successfully")
            log(f"Structure loaded from JSON")
            
        except Exception as e:
            import traceback
            error_msg = f"Failed to load JSON structure: {str(e)}"
            self.notify(error_msg, severity="error")
            
            # Also log to console for debugging
            print(f"\n{'='*60}")
            print(f"ERROR in NWB Lens: {error_msg}")
            print(f"{'='*60}")
            traceback.print_exc()
            print(f"{'='*60}\n")
        
        if self.run_inspector:
            self.action_run_inspector()
    
    def action_run_inspector(self) -> None:
        """Run nwbinspector on the current file."""
        if not self.inspector.is_available():
            self.notify("nwbinspector not available. Install with: uv add --optional inspector", severity="warning")
            return
        
        try:
            self.notify("Running nwbinspector...", timeout=1)
            self.inspector_results = self.inspector.run_inspector(self.original_nwb_path)
            
            # Update tree with problem indicators
            tree = self.query_one("#tree", NWBTree)
            tree.update_with_problems(self.inspector.problems_by_path)
            
            self.notify(f"Inspector found {len(self.inspector_results)} issues")
            
        except Exception as e:
            self.notify(f"Inspector failed: {e}", severity="error")
    
    def action_export_output(self) -> None:
        """Export current structure to JSON."""
        from pathlib import Path
        import json
        
        # Generate output filename from the original file path
        output_path = Path(f"{self.original_nwb_path.stem}_structure.json")
        
        try:
            # We already have the JSON data loaded
            with open(output_path, 'w') as f:
                json.dump(self.json_data, f, indent=2)
            
            self.notify(f"Exported structure to {output_path}", severity="information")
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")
    
    def action_show_help(self) -> None:
        """Show help screen."""
        # TODO: Implement help screen
        self.notify("Help screen not implemented yet")
        
        
if __name__ == "__main__":
    json_file_path = Path("/home/heberto/development/nwb-lens/example.json")
    app = NWBLensApp(json_file_path=json_file_path)
    app.run()