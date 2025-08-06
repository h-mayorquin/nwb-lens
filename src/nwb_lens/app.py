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
            
            # Check if inspection data is already in the JSON
            if "merge_info" in self.json_data and self.json_data["merge_info"].get("inspection_available", False):
                # Extract and apply inspection results from JSON
                self._extract_inspection_from_json()
                tree.update_with_problems(self.inspector.problems_by_path)
                
                total_messages = self.json_data["merge_info"].get("total_messages", 0)
                if total_messages > 0:
                    self.notify(f"Loaded {total_messages} inspection messages", severity="information")
            
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
        
        # Note: run_inspector flag is now handled differently
        # Inspection should be done during file loading with --inspect flag
    
    def action_run_inspector(self) -> None:
        """Display inspector results if available in the JSON data."""
        # Check if inspection data is already in the loaded JSON
        if self.json_data and "merge_info" in self.json_data:
            merge_info = self.json_data.get("merge_info", {})
            if merge_info.get("inspection_available", False):
                total_messages = merge_info.get("total_messages", 0)
                
                # Extract inspection results from the JSON structure
                self._extract_inspection_from_json()
                
                # Update tree with problem indicators
                tree = self.query_one("#tree", NWBTree)
                tree.update_with_problems(self.inspector.problems_by_path)
                
                self.notify(f"Inspector found {total_messages} issues", severity="information")
                return
        
        # If no inspection data in JSON, check if inspector is available for live run
        if not self.inspector.is_available():
            self.notify("nwbinspector not available. Re-run with --inspect flag or install with: uv add nwbinspector", severity="warning")
            return
        
        # For now, inform user to re-run with inspection
        self.notify("No inspection data found. Re-run nwb-lens with --inspect flag", severity="warning")
    
    def _extract_inspection_from_json(self) -> None:
        """Extract inspection results from the loaded JSON structure."""
        self.inspector.problems_by_path = {}
        
        def extract_from_node(node, path=""):
            """Recursively extract inspection data from JSON nodes."""
            if "inspection" in node:
                inspection = node["inspection"]
                if inspection.get("has_issues", False):
                    messages = inspection.get("messages", [])
                    # Convert to the format expected by the tree
                    problems = []
                    for msg in messages:
                        problems.append({
                            'path': path,
                            'severity': msg.get('importance', 'UNKNOWN'),
                            'message': msg.get('message', ''),
                            'check_name': msg.get('check_function', ''),
                        })
                    if problems:
                        self.inspector.problems_by_path[path] = problems
            
            # Process children
            if "children" in node:
                for child in node["children"]:
                    child_path = child.get("path", path)
                    extract_from_node(child, child_path)
        
        # Start extraction from the root structure
        if "structure" in self.json_data:
            extract_from_node(self.json_data["structure"])
    
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