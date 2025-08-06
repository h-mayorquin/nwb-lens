"""CLI interface for NWB Lens."""

import asyncio
import tempfile
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .app import NWBLensApp
from .structure.extractor import NWBStructureExtractor
from .structure.merger import NWBDataMerger
from .inspector.runner import InspectorRunner

console = Console()
app = typer.Typer(
    name="nwb-lens",
    help="Interactive terminal-based NWB file explorer for debugging and exploration",
    no_args_is_help=True,
)


@app.command()
def main(
    file_path: Path = typer.Argument(..., help="Path to the NWB file to explore"),
    inspect: bool = typer.Option(
        False, "--inspect", "-i", help="Run nwbinspector validation and include results in output or TUI"
    ),
    inspector_json: Optional[Path] = typer.Option(
        None, "--inspector-json", help="Path to existing nwbinspector JSON output to merge with structure"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Export structure to JSON file (non-interactive mode). When used with --inspect, validation results are included in the output"
    ),
) -> None:
    """
    Explore NWB file structure with interactive TUI or export to JSON.
    
    When using --output with --inspect, the exported JSON will include:
    - Complete NWB file structure
    - nwbinspector validation messages for each object
    - Summary of issues by importance level
    
    Examples:
        nwb-lens file.nwb                                  # Interactive TUI mode
        nwb-lens file.nwb --inspect                        # TUI with validation
        nwb-lens file.nwb --output structure.json          # Export structure only
        nwb-lens file.nwb --inspect --output validated.json # Export with validation
    """
    
    if not file_path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(1)
    
    if not file_path.suffix.lower() == ".nwb":
        console.print(f"[yellow]Warning: File does not have .nwb extension: {file_path}[/yellow]")
    
    async def process_file():
        """Process the NWB file with optional inspection."""
        # Initialize components
        extractor = NWBStructureExtractor()
        merger = NWBDataMerger()
        inspector = InspectorRunner() if (inspect or inspector_json) else None
        
        # Extract structure
        console.print(f"[blue]Extracting structure from {file_path.name}...[/blue]")
        extractor.load_file(file_path)
        merger.set_structure(extractor.get_json_structure())
        
        # Run inspection if requested
        if inspect:
            if not inspector or not inspector.is_available():
                console.print(f"[yellow]Warning: nwbinspector not available, skipping validation[/yellow]")
            else:
                console.print(f"[blue]Running nwbinspector validation...[/blue]")
                inspection_results = await inspector.run_inspection(file_path)
                merger.set_inspection(inspection_results)
        
        # Load and merge external inspector JSON if provided
        if inspector_json:
            if not inspector_json.exists():
                console.print(f"[red]Error: Inspector JSON file not found: {inspector_json}[/red]")
                raise typer.Exit(1)
            
            console.print(f"[blue]Loading inspector results from {inspector_json.name}...[/blue]")
            merger.load_inspection_from_file(inspector_json)
            
        return extractor, merger
    
    try:
        # Run the async processing
        extractor, merger = asyncio.run(process_file())
        
        if output:
            # Non-interactive mode: export to specified output file
            json_data = merger.get_merged_data()
            
            with open(output, 'w') as f:
                import json
                json.dump(json_data, f, indent=2)
            
            def count_objects(obj):
                count = 1
                if 'children' in obj:
                    for child in obj['children']:
                        count += count_objects(child)
                return count
            
            object_count = count_objects(json_data['structure'])
            file_size_mb = output.stat().st_size / 1024 / 1024
            
            console.print(f"[green]✓ Export completed successfully![/green]")
            console.print(f"  • Total objects: {object_count}")
            console.print(f"  • JSON size: {file_size_mb:.2f} MB")
            
            # Show inspection summary if available
            if merger.has_inspection_data():
                merge_info = json_data.get("merge_info", {})
                total_messages = merge_info.get("total_messages", 0)
                console.print(f"  • Inspection messages: {total_messages}")
                
        else:
            # Interactive mode: save to temporary file and launch app
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
                import json
                json_data = merger.get_merged_data()
                json.dump(json_data, tmp_file, indent=2)
                tmp_json_path = Path(tmp_file.name)
            
            try:
                # Launch the app with the JSON file
                nwb_app = NWBLensApp(
                    json_file_path=tmp_json_path,
                    run_inspector=inspect
                )
                nwb_app.run()
            finally:
                # Clean up temporary file
                if tmp_json_path.exists():
                    tmp_json_path.unlink()
                    
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()