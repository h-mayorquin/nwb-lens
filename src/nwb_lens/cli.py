"""CLI interface for NWB Lens."""

import tempfile
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .app import NWBLensApp
from .structure.json_converter import NWBJSONConverter

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
        False, "--inspect", "-i", help="Run nwbinspector at startup"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Export structure to JSON file (non-interactive mode)"
    ),
) -> None:
    """Explore NWB file structure with interactive TUI or export to JSON."""
    
    if not file_path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(1)
    
    if not file_path.suffix.lower() == ".nwb":
        console.print(f"[yellow]Warning: File does not have .nwb extension: {file_path}[/yellow]")
    
    # Always convert to JSON first
    try:
        converter = NWBJSONConverter()
        console.print(f"[blue]Converting {file_path.name} to JSON structure...[/blue]")
        json_data = converter.extract_to_json(file_path)
        
        if output:
            # Non-interactive mode: save to specified output file
            converter.save_json(json_data, output)
            
            # Count objects for stats
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
        else:
            # Interactive mode: save to temporary file and launch app
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
                import json
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