"""Panel components for displaying object details."""

from textual.containers import Vertical, ScrollableContainer
from textual.widgets import Static
from textual.widget import Widget
from textual import log

from ..structure.models import NWBObjectInfo, InspectorMessage


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
            ScrollableContainer(
                Static("", id="inspector-results", markup=True),
                id="inspector-scroll"
            ),
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
        
        # Update object info section (removed class as requested)
        info_text = f"""[bold]Selected:[/bold] {selected_object.path}
[bold]Type:[/bold] {selected_object.type}"""
        
        self.query_one("#object-info", Static).update(info_text)
        
        # Build detailed information display using unified info
        details_sections = []
        
        # Format unified info
        info_text = self._format_unified_info(selected_object)
        if info_text:
            details_sections.append(info_text)
        
        # Join all sections
        details_text = "\n\n".join(details_sections) if details_sections else "[dim]No additional details[/dim]"
        self.query_one("#object-details", Static).update(details_text)
        
        # Update inspector results if available
        self._update_inspector_results(selected_object)
    
    def _update_inspector_results(self, selected_object: NWBObjectInfo) -> None:
        """Update the inspector results section for the selected object."""
        if not selected_object.inspector_messages:
            self.query_one("#inspector-results", Static).update("")
            return
        
        # Group messages by importance
        messages_by_importance = {}
        for msg in selected_object.inspector_messages:
            if msg.importance not in messages_by_importance:
                messages_by_importance[msg.importance] = []
            messages_by_importance[msg.importance].append(msg)
        
        # Build display text
        results_sections = []
        results_sections.append("[bold]Inspector Results:[/bold]")
        
        # Show in priority order
        priority_order = ["ERROR", "PYNWB_VALIDATION", "CRITICAL", 
                         "BEST_PRACTICE_VIOLATION", "BEST_PRACTICE_SUGGESTION"]
        
        for importance in priority_order:
            if importance in messages_by_importance:
                messages = messages_by_importance[importance]
                text_indicator = messages[0].get_text_indicator()
                
                # Format importance name nicely
                display_importance = importance.replace('_', ' ').title()
                
                # Color based on severity - different shades of red with more intense for worse problems
                if importance in ["ERROR", "PYNWB_VALIDATION", "CRITICAL"]:
                    color = "red1"  # Most intense red for critical errors
                elif importance == "BEST_PRACTICE_VIOLATION":
                    color = "red3"  # Medium red for violations
                else:
                    color = "orange_red1"  # Lighter red-orange for suggestions
                
                results_sections.append(f"\n[{color}]{text_indicator}: {display_importance}:[/{color}]")
                for msg in messages:
                    # Truncate long messages
                    message_text = msg.message
                    if len(message_text) > 120:
                        message_text = message_text[:117] + "..."
                    results_sections.append(f"  • {message_text}")
                    if msg.check_function:
                        results_sections.append(f"    [dim]Check: {msg.check_function}[/dim]")
        
        results_text = "\n".join(results_sections)
        self.query_one("#inspector-results", Static).update(results_text)
    
    def update_inspector_results(self, results: list) -> None:
        """Update the inspector results section (legacy method)."""
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
    
    def _format_unified_info(self, obj_info: NWBObjectInfo) -> str:
        """Format unified info combining fields, attributes, and data info."""
        if not obj_info.info:
            return ""
        
        # Organize info into categories
        data_items = []
        metadata_items = []
        inspection_items = []
        
        # Priority order for display
        data_keys = ['shape', 'data_type', 'chunks', 'compression', 'compression_opts', 
                    'original_size', 'compressed_size', 'compression_ratio', 'hdf5_path']
        metadata_keys = ['description', 'comments', 'unit', 'units', 'rate', 
                        'sampling_rate', 'resolution', 'conversion', 'offset', 
                        'starting_time', 'timestamps_shape']
        inspection_keys = ['inspection_messages', 'inspection_has_issues']
        
        # Process data-related info
        for key in data_keys:
            if key in obj_info.info:
                value = obj_info.info[key]
                display_key = key.replace('_', ' ').title()
                if key == 'data_type':
                    display_key = 'Data Type'
                elif key == 'hdf5_path':
                    display_key = 'HDF5 Path'
                    value = f"[dim]{value}[/dim]"
                elif key == 'compression_opts':
                    display_key = 'Compression Options'
                elif key == 'compression_ratio':
                    display_key = 'Compression Ratio'
                    value = f"{value}:1" if isinstance(value, (int, float)) else value
                elif key == 'original_size':
                    display_key = 'Original Size'
                elif key == 'compressed_size':
                    display_key = 'Compressed Size'
                elif key == 'shape' and isinstance(value, list):
                    value = f"{value}"
                data_items.append(f"  • {display_key}: {value}")
        
        # Process metadata
        for key in metadata_keys:
            if key in obj_info.info:
                value = obj_info.info[key]
                display_key = key.replace('_', ' ').title()
                if key == 'timestamps_shape':
                    display_key = 'Timestamps Shape'
                metadata_items.append(f"  • {display_key}: {value}")
        
        # Process remaining items not in priority lists (sorted alphabetically)
        processed_keys = set(data_keys + metadata_keys + inspection_keys)
        remaining_items = []
        for key, value in obj_info.info.items():
            if key not in processed_keys:
                display_key = key.replace('_', ' ').title()
                remaining_items.append((display_key, value))
        
        # Sort alphabetically by display key
        remaining_items.sort(key=lambda x: x[0])
        for display_key, value in remaining_items:
            metadata_items.append(f"  • {display_key}: {value}")
        
        # Build sections
        sections = []
        
        if data_items:
            sections.append("[bold]Data:[/bold]\n" + "\n".join(data_items))
        
        if metadata_items:
            sections.append("[bold]Info:[/bold]\n" + "\n".join(metadata_items))
        
        return "\n\n".join(sections)
    
    def _format_metadata(self, info: NWBObjectInfo) -> str:
        """Format metadata/attributes for display."""
        # Skip data-related attributes as they're shown separately
        skip_attrs = {'data_shape', 'data_dtype', 'data_chunks', 'data_hdf5_path', 
                     'timestamps_shape', 'has_timestamps', 'has_inspection_issues', 
                     'inspection_message_count', 'is_virtual', 'virtual_reason'}
        
        # Common important attributes to show first
        priority_attrs = ['description', 'comments', 'unit', 'units', 'rate', 
                         'sampling_rate', 'resolution', 'conversion', 'offset']
        
        metadata_items = []
        missing_fields = []
        
        # Check for missing fields based on inspector messages
        for msg in info.inspector_messages:
            msg_lower = msg.message.lower()
            if "description is missing" in msg_lower:
                missing_fields.append('description')
            elif "description" in msg_lower and "placeholder" in msg_lower:
                # Description exists but is a placeholder
                if 'description' not in info.attributes or not info.attributes.get('description'):
                    missing_fields.append('description')
        
        # Show priority attributes first (including missing ones)
        for attr in priority_attrs:
            if attr in missing_fields and attr not in info.attributes:
                # Highlight missing required field
                display_key = attr.replace('_', ' ').title()
                metadata_items.append((attr, None, True))  # True = missing
            elif attr in info.attributes and attr not in skip_attrs:
                value = info.attributes[attr]
                # Check if it's a placeholder
                is_placeholder = False
                if attr == 'description' and value:
                    value_lower = str(value).lower()
                    if 'no description' in value_lower or value_lower == 'description':
                        is_placeholder = True
                
                if value and str(value).strip():
                    metadata_items.append((attr, value, is_placeholder))
        
        # Show remaining attributes
        for key, value in info.attributes.items():
            if key not in skip_attrs and key not in priority_attrs:
                if value and str(value).strip():
                    metadata_items.append((key, value, False))
        
        # Add missing description if detected and not in attributes
        if 'description' in missing_fields and not any(item[0] == 'description' for item in metadata_items):
            metadata_items.insert(0, ('description', None, True))
        
        if not metadata_items and not missing_fields:
            return ""
        
        metadata_text = "[bold]Metadata:[/bold]\n"
        for item in metadata_items:
            if len(item) == 3:
                key, value, is_special = item
            else:
                key, value = item
                is_special = False
            
            # Format key nicely
            display_key = key.replace('_', ' ').title()
            
            # Handle missing fields
            if value is None:
                metadata_text += f"  • {display_key}: [red bold]⚠️ MISSING[/red bold]\n"
            elif is_special:
                # Placeholder value
                metadata_text += f"  • {display_key}: [yellow]{value} ⚠️[/yellow]\n"
            elif isinstance(value, (int, float)):
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