"""NWB structure extraction using JSON representation."""

from pathlib import Path
from typing import Any, Optional

from .models import NWBObjectInfo
from .json_converter import NWBJSONConverter


class NWBStructureExtractor:
    """Extract structure from NWB files as JSON for efficient navigation."""
    
    def __init__(self):
        """Initialize the extractor with JSON converter."""
        self.file_path = None
        self.json_converter = NWBJSONConverter()
        self.json_structure = None
    
    def load_file(self, file_path: Path) -> None:
        """
        Load NWB file by extracting to JSON representation.
        
        This extracts the structure once and closes the file handle,
        keeping only the JSON representation in memory.
        """
        self.file_path = file_path
        
        try:
            self.json_structure = self.json_converter.extract_to_json(file_path)
        except Exception as e:
            raise RuntimeError(f"Failed to extract NWB file to JSON: {e}")
    
    def extract_file_structure(self, structure_data: Optional[dict[str, Any]] = None) -> NWBObjectInfo:
        """
        Extract the complete file structure from JSON.
        
        Args:
            structure_data: Optional structure data to use instead of loaded data
        """
        if structure_data is None:
            if self.json_structure is None:
                raise RuntimeError("No file loaded. Call load_file() first.")
            structure_data = self.json_structure
        
        return self._build_from_json(structure_data["structure"])
    
    def _build_from_json(self, json_obj: dict[str, Any], parent: Optional[NWBObjectInfo] = None) -> NWBObjectInfo:
        """Build NWBObjectInfo structure from JSON representation."""
        
        # Extract basic info
        obj_info = NWBObjectInfo(
            name=json_obj.get("name", "unknown"),
            type=json_obj.get("type", "unknown"),
            class_name=json_obj.get("class", "unknown").split(".")[-1],  # Get class name only
            path=json_obj.get("path", "/"),
            fields=json_obj.get("fields", {}),
            attributes=json_obj.get("attributes", {}),
            children=[],
            parent=parent
        )
        
        # Add data info to attributes if present
        if "data_info" in json_obj:
            obj_info.attributes.update({
                f"data_{k}": v for k, v in json_obj["data_info"].items()
            })
        
        # Add inspection info to attributes if present
        if "inspection" in json_obj:
            inspection_data = json_obj["inspection"]
            obj_info.attributes.update({
                "inspection_messages": len(inspection_data.get("messages", [])),
                "inspection_has_issues": inspection_data.get("has_issues", False),
                "inspection_summary": inspection_data.get("summary", {})
            })
        
        # Recursively build children
        if "children" in json_obj:
            for child_json in json_obj["children"]:
                child = self._build_from_json(child_json, parent=obj_info)
                obj_info.children.append(child)
        
        return obj_info
    
    def get_file_info(self) -> Optional[dict[str, Any]]:
        """Get file metadata from JSON structure."""
        if self.json_structure:
            return self.json_structure.get("file_info")
        return None
    
    def get_json_structure(self) -> Optional[dict[str, Any]]:
        """Get the raw JSON structure for export or debugging."""
        return self.json_structure
    
    def export_json(self, output_path: Path) -> None:
        """Export the structure data to JSON file."""
        if not self.json_structure:
            raise RuntimeError("No data loaded to export")
        
        with open(output_path, 'w') as f:
            import json
            json.dump(self.json_structure, f, indent=2)
    
    # Future extension point: Could add methods like:
    # def reload_file(self) -> None: ...
    # def get_object_by_path(self, path: str) -> NWBObjectInfo: ...