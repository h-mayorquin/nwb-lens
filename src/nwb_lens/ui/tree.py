"""Tree widget for displaying NWB structure."""

from typing import Any

from textual.widgets import Tree
from textual.message import Message
from textual import log

from ..structure.models import NWBObjectInfo


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
        # Create the object without children first
        obj_info = NWBObjectInfo(
            name=json_obj.get('name', ''),
            type=json_obj.get('type', ''),
            class_name=json_obj.get('class', ''),
            path=json_obj.get('path', ''),
            fields=json_obj.get('fields', {}),
            attributes=json_obj.get('attributes', {}),
            children=[],  # Will populate below
            parent=parent
        )
        
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
        severity_order = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'SUGGESTION']
        for severity in severity_order:
            if any(p['severity'] == severity for p in problems):
                return severity
        return 'INFO'
    
    def _get_severity_icon(self, severity: str) -> str:
        """Get visual indicator for problem severity."""
        icons = {
            'CRITICAL': 'X',
            'ERROR': 'X',   
            'WARNING': '!',
            'INFO': 'i',
            'SUGGESTION': '?',
        }
        return icons.get(severity, '?')
    