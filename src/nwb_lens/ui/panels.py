"""Panel components for displaying object details."""

from textual.containers import Vertical, ScrollableContainer
from textual.widgets import Static
from textual.widget import Widget
from textual import log

from ..structure.models import NWBObjectInfo


class AttributePanel(Widget):
    """Right panel showing object details and attributes."""
    
    def compose(self):
        """Create the panel layout."""
        yield Vertical(
            Static("Select an object to view details", id="object-info", markup=True),
            ScrollableContainer(
                Static("", id="object-details", markup=True),
                id="details-scroll"
            ),
            Static("", id="inspector-results", markup=True),
        )
    
    def on_mount(self) -> None:
        """Watch for changes in the app's selected_object."""
        self.watch(self.app, "selected_object", self.update_selection)
        log("AttributePanel mounted and watching selected_object")
    
    def update_selection(self, selected_object: NWBObjectInfo) -> None:
        """Called when app.selected_object changes."""
        if selected_object is None:
            return
            
        log("=" * 60)
        log("AttributePanel: selected_object changed via REACTIVE!")
        log(f"Object name: {selected_object.name}")
        log(f"Object type: {selected_object.type}")
        log(f"Object path: {selected_object.path}")
        log("=" * 60)
        
        # Update object info section
        info_text = f"""[bold]Selected:[/bold] {selected_object.path}
[bold]Type:[/bold] {selected_object.type}
[bold]Class:[/bold] {selected_object.class_name}"""
        
        self.query_one("#object-info", Static).update(info_text)
        
        # Build detailed information display
        details_sections = []
        
        # Data information (shape, dtype, chunks)
        data_info = self._extract_data_info(selected_object)
        if data_info:
            details_sections.append(data_info)
        
        # Fields section
        if selected_object.fields:
            fields_text = "[bold]Fields:[/bold]\n"
            for field_name, field_type in selected_object.fields.items():
                fields_text += f"  • {field_name}: [dim]{field_type}[/dim]\n"
            details_sections.append(fields_text.rstrip())
        
        # Attributes/Metadata section
        metadata_text = self._format_metadata(selected_object)
        if metadata_text:
            details_sections.append(metadata_text)
        
        # Join all sections
        details_text = "\n\n".join(details_sections) if details_sections else "[dim]No additional details[/dim]"
        self.query_one("#object-details", Static).update(details_text)
    
    def update_inspector_results(self, results: list) -> None:
        """Update the inspector results section."""
        if not results:
            self.query_one("#inspector-results", Static).update("")
            return
        
        results_text = "Inspector Results:\n"
        for result in results:
            severity = result.get('severity', 'INFO')
            message = result.get('message', '')
            results_text += f"  [{severity}] {message}\n"
        
        self.query_one("#inspector-results", Static).update(results_text)
    
    def _extract_data_info(self, info: NWBObjectInfo) -> str:
        """Extract and format data information (shape, dtype, chunks)."""
        data_sections = []
        
        # Check for data shape info
        if 'data_shape' in info.attributes:
            shape = info.attributes['data_shape']
            dtype = info.attributes.get('data_dtype', 'unknown')
            chunks = info.attributes.get('data_chunks')
            
            data_text = f"[bold]Data:[/bold]\n"
            data_text += f"  • Shape: {shape}\n"
            data_text += f"  • Dtype: [cyan]{dtype}[/cyan]\n"
            if chunks:
                data_text += f"  • Chunks: {chunks}\n"
            
            # Add HDF5 path if available
            hdf5_path = info.attributes.get('data_hdf5_path')
            if hdf5_path:
                data_text += f"  • HDF5 path: [dim]{hdf5_path}[/dim]\n"
            
            data_sections.append(data_text.rstrip())
        
        # Check for timestamps info
        if 'timestamps_shape' in info.attributes:
            ts_text = f"[bold]Timestamps:[/bold]\n"
            ts_text += f"  • Shape: {info.attributes['timestamps_shape']}\n"
            data_sections.append(ts_text.rstrip())
        
        return "\n\n".join(data_sections) if data_sections else ""
    
    def _format_metadata(self, info: NWBObjectInfo) -> str:
        """Format metadata/attributes for display."""
        # Skip data-related attributes as they're shown separately
        skip_attrs = {'data_shape', 'data_dtype', 'data_chunks', 'data_hdf5_path', 
                     'timestamps_shape', 'has_timestamps'}
        
        # Common important attributes to show first
        priority_attrs = ['description', 'comments', 'unit', 'units', 'rate', 
                         'sampling_rate', 'resolution', 'conversion', 'offset']
        
        metadata_items = []
        
        # Show priority attributes first
        for attr in priority_attrs:
            if attr in info.attributes and attr not in skip_attrs:
                value = info.attributes[attr]
                if value and str(value).strip():
                    metadata_items.append((attr, value))
        
        # Show remaining attributes
        for key, value in info.attributes.items():
            if key not in skip_attrs and key not in priority_attrs:
                if value and str(value).strip():
                    metadata_items.append((key, value))
        
        if not metadata_items:
            return ""
        
        metadata_text = "[bold]Metadata:[/bold]\n"
        for key, value in metadata_items:
            # Format key nicely
            display_key = key.replace('_', ' ').title()
            
            # Format value based on type
            if isinstance(value, (int, float)):
                if key in ['rate', 'sampling_rate'] and value > 0:
                    metadata_text += f"  • {display_key}: [green]{value:g} Hz[/green]\n"
                elif key == 'conversion':
                    metadata_text += f"  • {display_key}: [yellow]{value:g}[/yellow]\n"
                else:
                    metadata_text += f"  • {display_key}: {value}\n"
            else:
                # Truncate long strings
                str_value = str(value)
                if len(str_value) > 100:
                    str_value = str_value[:97] + "..."
                metadata_text += f"  • {display_key}: {str_value}\n"
        
        return metadata_text.rstrip()