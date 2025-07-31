"""Data models for NWB structure representation."""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class NWBObjectInfo:
    """Data class for NWB object information."""
    
    name: str
    type: str
    class_name: str
    path: str
    fields: dict[str, Any]
    attributes: dict[str, Any]
    children: list['NWBObjectInfo']
    parent: Optional['NWBObjectInfo'] = None
    
    def __post_init__(self):
        """Set parent references for children."""
        for child in self.children:
            child.parent = self
    
    def get_display_name(self) -> str:
        """Get the display name for this object."""
        if self.type and self.type != self.name:
            return f"{self.name} ({self.type})"
        return self.name
    
    def get_full_path(self) -> str:
        """Get the full path to this object."""
        return self.path
    
    def has_children(self) -> bool:
        """Check if this object has children."""
        return len(self.children) > 0
    
    def find_child(self, name: str) -> Optional['NWBObjectInfo']:
        """Find a child by name."""
        for child in self.children:
            if child.name == name:
                return child
        return None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation for JSON export."""
        return {
            "name": self.name,
            "type": self.type,
            "class": self.class_name,
            "path": self.path,
            "fields": self.fields,
            "attributes": self.attributes,
            "children": [child.to_dict() for child in self.children]
        }