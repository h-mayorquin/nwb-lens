"""Tree widget for displaying NWB structure."""

from typing import Any, Dict, List

from textual.widgets import Tree
from textual.message import Message
from textual import log

from ..structure.models import NWBObjectInfo, InspectorMessage


class NWBTree(Tree):
    """Expandable tree widget for NWB structure."""
    
    class ObjectSelected(Message):
        """Message sent when an object is selected in the tree."""
        
        def __init__(self, object_info: NWBObjectInfo) -> None:
            super().__init__()
            self.object_info = object_info
    
    def __init__(self, **kwargs):
        super().__init__("NWBFile", **kwargs)
        self.root.expand()
        self.structure_map = {}  # Maps tree nodes to NWBObjectInfo objects
        self.problems_map = {}   # Maps paths to problem indicators
    
    def populate_from_structure(self, structure: NWBObjectInfo) -> None:
        """Populate tree from NWB structure."""
        # Clear existing content
        self.root.remove_children()
        self.structure_map.clear()
        
        # Set root information - always use "NWBFile" for root
        self.root.set_label("NWBFile")
        self.structure_map[self.root] = structure
        
        # Add children recursively
        self._add_children_to_node(self.root, structure.children)
    
    def populate_from_json(self, json_structure: dict[str, Any]) -> None:
        """Populate tree from JSON structure."""
        # Convert JSON to NWBObjectInfo structure
        structure = self._json_to_object_info(json_structure)
        
        # Use existing populate method
        self.populate_from_structure(structure)
    
    def _json_to_object_info(self, json_obj: dict[str, Any], parent: NWBObjectInfo = None) -> NWBObjectInfo:
        """Convert JSON object to NWBObjectInfo recursively."""
        
        # Create unified info structure combining fields, attributes, and data_info
        unified_info = {}
        
        # Add fields
        if "fields" in json_obj:
            unified_info.update(json_obj["fields"])
        
        # Add attributes
        if "attributes" in json_obj:
            unified_info.update(json_obj["attributes"])
        
        # Add data info with descriptive names
        if "data_info" in json_obj:
            data_info = json_obj["data_info"]
            if "shape" in data_info:
                unified_info["shape"] = data_info["shape"]
            if "dtype" in data_info:
                unified_info["data_type"] = data_info["dtype"]
            if "chunks" in data_info:
                unified_info["chunks"] = data_info["chunks"]
            if "hdf5_path" in data_info:
                unified_info["hdf5_path"] = data_info["hdf5_path"]
        
        # Create the object with unified info
        obj_info = NWBObjectInfo(
            name=json_obj.get('name', ''),
            type=json_obj.get('type', ''),
            class_name=json_obj.get('class', ''),
            path=json_obj.get('path', ''),
            fields=json_obj.get('fields', {}),
            attributes=json_obj.get('attributes', {}),
            info=unified_info,  # Add unified info for display
            children=[],  # Will populate below
            parent=parent
        )
        
        # Mark if this is a virtual/missing node
        if json_obj.get('virtual', False):
            obj_info.attributes['is_virtual'] = True
            obj_info.attributes['virtual_reason'] = 'missing'
        
        # Store inspection data if present
        if 'inspection' in json_obj:
            inspection = json_obj['inspection']
            obj_info.attributes['has_inspection_issues'] = inspection.get('has_issues', False)
            obj_info.attributes['inspection_message_count'] = len(inspection.get('messages', []))
            
            # Add inspection info to unified info as well
            unified_info['inspection_messages'] = len(inspection.get('messages', []))
            unified_info['inspection_has_issues'] = inspection.get('has_issues', False)
            unified_info['inspection_summary'] = inspection.get('summary', {})
            
            # Parse inspector messages
            for msg_data in inspection.get('messages', []):
                msg = InspectorMessage(
                    message=msg_data.get('message', ''),
                    importance=msg_data.get('importance', 'UNKNOWN'),
                    importance_level=msg_data.get('importance_level', 0),
                    severity=msg_data.get('severity', 'LOW'),
                    severity_level=msg_data.get('severity_level', 0),
                    check_function=msg_data.get('check_function', ''),
                    location=json_obj.get('path', '')
                )
                obj_info.inspector_messages.append(msg)
        
        # Update the unified info in obj_info after all modifications
        obj_info.info = unified_info
        
        # Convert children recursively
        if 'children' in json_obj:
            for child_json in json_obj['children']:
                child_obj = self._json_to_object_info(child_json, obj_info)
                obj_info.children.append(child_obj)
        
        return obj_info
    
    def _add_children_to_node(self, parent_node, children: list[NWBObjectInfo]) -> None:
        """Recursively add children to a tree node."""
        for child in children:
            display_name = child.get_display_name()
            
            # Check if this is a virtual/missing node
            if child.attributes.get('is_virtual', False):
                # Add visual indicator for missing elements
                display_name = f"❌ {display_name} (missing)"
            elif child.has_inspector_issues():
                # Add inspector icon summary
                icon_summary = child.get_inspector_icon()
                if icon_summary:
                    display_name = f"{icon_summary} {display_name}"
            
            child_node = parent_node.add(display_name)
            self.structure_map[child_node] = child
            
            # Add children recursively if they exist
            if child.has_children():
                self._add_children_to_node(child_node, child.children)
    
    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle node selection."""
        node = event.node
        
        log(f"Tree node selected: {node.label}")
        
        # Get the NWBObjectInfo for this node
        if node in self.structure_map:
            object_info = self.structure_map[node]
            log(f"Found object info for node: {object_info.name}")
            
            # Set the reactive attribute on the app
            self.app.selected_object = object_info
            log(f"Set app.selected_object to: {object_info.name}")
        else:
            log(f"No object info found for node: {node.label}")
            log(f"Available nodes: {list(self.structure_map.keys())}")
    
    def update_with_problems(self, problems_by_path: dict[str, list]) -> None:
        """Update tree nodes with problem indicators."""
        self.problems_map = problems_by_path
        
        # Update all nodes to show problem indicators
        for node, obj_info in self.structure_map.items():
            # Skip virtual nodes - they already have their indicator
            if obj_info.attributes.get('is_virtual', False):
                continue
                
            if obj_info.path in problems_by_path:
                # Add problem indicator to node label
                problems = problems_by_path[obj_info.path]
                worst_severity = self._get_worst_severity(problems)
                icon = self._get_severity_icon(worst_severity)
                
                # Update node label with icon
                original_label = obj_info.get_display_name()
                node.set_label(f"{icon} {original_label}")
    
    def _get_worst_severity(self, problems: list[dict]) -> str:
        """Get the worst severity from a list of problems."""
        severity_order = ['ERROR', 'PYNWB_VALIDATION', 'CRITICAL', 'BEST_PRACTICE_VIOLATION', 'BEST_PRACTICE_SUGGESTION']
        for severity in severity_order:
            if any(p['severity'] == severity for p in problems):
                return severity
        return 'BEST_PRACTICE_SUGGESTION'
    
    def _get_severity_icon(self, severity: str) -> str:
        """Get visual indicator for problem severity."""
        icons = {
            'CRITICAL': '❌',
            'ERROR': '❌',   
            'PYNWB_VALIDATION': '❌',
            'WARNING': '⚠️',
            'BEST_PRACTICE_VIOLATION': '⚠️',
            'INFO': '💡',
            'SUGGESTION': '💡',
            'BEST_PRACTICE_SUGGESTION': '💡',
        }
        return icons.get(severity, '❓')
    