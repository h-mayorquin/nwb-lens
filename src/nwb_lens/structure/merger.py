"""Module for merging NWB structure with inspection results."""

import copy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ..inspector.manager import InspectorManager


class NWBDataMerger:
    """
    Handles merging of NWB structure data with inspection results.
    
    This class is responsible for combining the base NWB structure
    with validation results from nwbinspector, creating a unified
    data structure for display and export.
    """
    
    def __init__(self):
        """Initialize the merger."""
        self.structure_data = None
        self.inspection_data = None
        self.merged_data = None
    
    def set_structure(self, structure_data: Dict[str, Any]) -> None:
        """Set the NWB structure data."""
        self.structure_data = structure_data
        self.merged_data = None  # Reset merged data
    
    def set_inspection(self, inspection_data: Dict[str, Any]) -> None:
        """Set the inspection results data."""
        self.inspection_data = inspection_data
        self.merged_data = None  # Reset merged data
    
    def load_inspection_from_file(self, inspector_json_path: Path) -> None:
        """
        Load inspection results from a JSON file.
        
        Args:
            inspector_json_path: Path to nwbinspector JSON output file
        """
        manager = InspectorManager()
        self.inspection_data = manager.load_inspection_json(inspector_json_path)
        self.merged_data = None  # Reset merged data
    
    def get_merged_data(self) -> Dict[str, Any]:
        """
        Get the merged structure and inspection data.
        
        Returns the merged data if available, otherwise returns
        the structure data alone if no inspection data is set.
        """
        if self.merged_data is not None:
            return self.merged_data
        
        if self.structure_data is None:
            raise RuntimeError("No structure data set. Call set_structure() first.")
        
        if self.inspection_data is None:
            # No inspection data, return structure as-is
            return self.structure_data
        
        # Merge the data
        self.merged_data = self._merge_structure_and_inspection(
            self.structure_data, 
            self.inspection_data
        )
        return self.merged_data
    
    def _merge_structure_and_inspection(
        self, 
        structure_json: Dict[str, Any], 
        inspection_json: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge NWB structure JSON with inspection results JSON.
        
        Args:
            structure_json: NWB structure from NWBJSONConverter
            inspection_json: Inspection results from InspectorManager
            
        Returns:
            Merged JSON with inspection data added to structure nodes
        """
        # Create a deep copy to avoid modifying original
        merged = copy.deepcopy(structure_json)
        
        # Get inspection results
        inspection_results = inspection_json.get("inspection_results", {})
        inspection_info = inspection_json.get("inspection_info", {})
        
        # Add inspection metadata to file info
        if "file_info" in merged:
            merged["file_info"]["inspection"] = inspection_info
            merged["file_info"]["inspection_summary"] = inspection_json.get("summary", {})
        
        # Add inspection data to structure
        if "structure" in merged:
            root_path = merged["structure"].get("path", "/")
            self._add_inspection_to_node(merged["structure"], root_path, inspection_results)
        
        # Add merge metadata
        merged["merge_info"] = {
            "timestamp": datetime.now().isoformat(),
            "inspection_available": inspection_info.get("available", False),
            "total_messages": inspection_json.get("summary", {}).get("total", 0)
        }
        
        return merged
    
    def _add_inspection_to_node(
        self, 
        node: Dict[str, Any], 
        path: str, 
        inspection_results: Dict[str, Any]
    ) -> None:
        """
        Recursively add inspection data to structure nodes.
        
        Args:
            node: Structure node to add inspection data to
            path: Path of the current node
            inspection_results: Dictionary of inspection results by path
        """
        # First, add virtual nodes for missing elements
        self._add_virtual_nodes_for_missing_elements(node, path, inspection_results)
        
        # Try both the original path and with /general prefix
        messages = []
        
        # Check for exact match
        if path in inspection_results:
            messages.extend(inspection_results[path])
        
        # Check with /general prefix
        general_path = f"/general{path}" if path != "/" else "/general"
        if general_path in inspection_results:
            messages.extend(inspection_results[general_path])
        
        # Also check if this path maps to an inspector path without /general
        for insp_path, insp_messages in inspection_results.items():
            if self._normalize_path(insp_path, path):
                # Avoid duplicates
                for msg in insp_messages:
                    if msg not in messages:
                        messages.append(msg)
        
        # Calculate summary
        summary = {}
        for msg in messages:
            importance = msg["importance"]
            summary[importance] = summary.get(importance, 0) + 1
        
        # Add inspection info to node
        if messages:  # Only add if there are messages
            if "inspection" not in node:
                node["inspection"] = {
                    "messages": messages,
                    "summary": summary,
                    "has_issues": True
                }
            else:
                # Merge with existing inspection data (for virtual nodes)
                node["inspection"]["messages"].extend(messages)
                for importance, count in summary.items():
                    existing = node["inspection"]["summary"].get(importance, 0)
                    node["inspection"]["summary"][importance] = existing + count
                node["inspection"]["has_issues"] = len(node["inspection"]["messages"]) > 0
        
        # Recursively process children
        if "children" in node:
            for child in node["children"]:
                child_path = child.get("path", path)
                self._add_inspection_to_node(child, child_path, inspection_results)
    
    def _add_virtual_nodes_for_missing_elements(
        self, 
        node: Dict[str, Any], 
        path: str,
        inspection_results: Dict[str, Any]
    ) -> None:
        """Add virtual nodes for missing elements flagged by inspector."""
        messages = inspection_results.get(path, [])
        
        # Check for messages about missing elements
        for msg in messages:
            message_text = msg.get("message", "")
            message_lower = message_text.lower()
            
            # Handle missing Subject
            if "subject is missing" in message_lower and path == "/":
                # Check if subject already exists in children
                has_subject = False
                if "children" in node:
                    for child in node["children"]:
                        if child.get("name") == "subject" or child.get("type") == "Subject":
                            has_subject = True
                            break
                
                if not has_subject:
                    # Create virtual subject node
                    virtual_subject = {
                        "name": "subject",
                        "type": "Subject",
                        "class": "pynwb.file.Subject",
                        "path": "/general/subject",
                        "virtual": True,  # Mark as virtual/missing
                        "inspection": {
                            "messages": [{
                                "message": message_text,
                                "importance": msg.get("importance", "BEST_PRACTICE_SUGGESTION"),
                                "importance_level": msg.get("importance_level", 0),
                                "severity": msg.get("severity", "LOW"),
                                "check_function": msg.get("check_function", "check_subject_exists")
                            }],
                            "summary": {msg.get("importance", "BEST_PRACTICE_SUGGESTION"): 1},
                            "has_issues": True
                        }
                    }
                    
                    # Add to general node
                    self._add_to_general_node(node, virtual_subject)
    
    def _add_to_general_node(self, parent_node: Dict[str, Any], child_to_add: Dict[str, Any]) -> None:
        """Helper to add a child to the general node, creating it if needed."""
        if "children" not in parent_node:
            parent_node["children"] = []
        
        # Find or create general node
        general_node = None
        for child in parent_node["children"]:
            if child.get("name") == "general":
                general_node = child
                break
        
        if general_node is None:
            general_node = {
                "name": "general",
                "type": "Collection",
                "class": "dict",
                "path": "/general",
                "children": []
            }
            parent_node["children"].append(general_node)
        
        if "children" not in general_node:
            general_node["children"] = []
        
        general_node["children"].append(child_to_add)
    
    def _normalize_path(self, inspector_path: str, structure_path: str) -> bool:
        """Check if inspector path matches structure path, handling /general prefix."""
        # Remove /general prefix from inspector paths for comparison
        norm_inspector = inspector_path
        if inspector_path.startswith("/general/"):
            norm_inspector = inspector_path[8:]  # Remove "/general"
        elif inspector_path == "/general":
            norm_inspector = "/"
        
        # Also handle None paths from inspector
        if inspector_path is None:
            return False
            
        return norm_inspector == structure_path or inspector_path == structure_path
    
    def has_inspection_data(self) -> bool:
        """Check if inspection data is available."""
        if self.merged_data:
            return self.merged_data.get("merge_info", {}).get("inspection_available", False)
        return self.inspection_data is not None
    
    def get_inspection_summary(self) -> Optional[Dict[str, Any]]:
        """Get the inspection summary if available."""
        if self.inspection_data:
            return self.inspection_data.get("summary")
        if self.merged_data:
            return self.merged_data.get("file_info", {}).get("inspection_summary")
        return None