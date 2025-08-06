"""Data models for NWB structure representation."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class InspectorImportance(Enum):
    """Inspector message importance levels."""
    BEST_PRACTICE_SUGGESTION = 0
    BEST_PRACTICE_VIOLATION = 1
    CRITICAL = 2
    PYNWB_VALIDATION = 3
    ERROR = 4


class InspectorSeverity(Enum):
    """Inspector message severity levels."""
    LOW = 0
    MEDIUM = 1
    HIGH = 2


@dataclass
class InspectorMessage:
    """Data model for a single inspector validation message."""
    message: str
    importance: str
    importance_level: int
    severity: str
    severity_level: int
    check_function: str
    object_type: Optional[str] = None
    object_name: Optional[str] = None
    file_path: Optional[str] = None
    location: Optional[str] = None
    
    def get_icon(self) -> str:
        """Get the icon for this message based on importance."""
        if self.importance in ["ERROR", "PYNWB_VALIDATION", "CRITICAL"]:
            return "❌"
        elif self.importance == "BEST_PRACTICE_VIOLATION":
            return "⚠️"
        elif self.importance == "BEST_PRACTICE_SUGGESTION":
            return "💡"
        else:
            return "❓"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InspectorMessage':
        """Create from dictionary representation."""
        return cls(
            message=data.get("message", ""),
            importance=data.get("importance", "UNKNOWN"),
            importance_level=data.get("importance_level", 0),
            severity=data.get("severity", "LOW"),
            severity_level=data.get("severity_level", 0),
            check_function=data.get("check_function", ""),
            object_type=data.get("object_type"),
            object_name=data.get("object_name"),
            file_path=data.get("file_path"),
            location=data.get("location")
        )


@dataclass
class InspectorResults:
    """Container for all inspector results."""
    messages: List[InspectorMessage] = field(default_factory=list)
    location_map: Dict[str, List[InspectorMessage]] = field(default_factory=dict)
    summary: Dict[str, int] = field(default_factory=dict)
    
    def add_message(self, message: InspectorMessage) -> None:
        """Add a message to the results."""
        self.messages.append(message)
        
        # Add to location map
        location = message.location or "/"
        if location not in self.location_map:
            self.location_map[location] = []
        self.location_map[location].append(message)
        
        # Update summary
        self.summary[message.importance] = self.summary.get(message.importance, 0) + 1
    
    def get_messages_for_location(self, location: str) -> List[InspectorMessage]:
        """Get messages for a specific location."""
        return self.location_map.get(location, [])
    
    def get_summary_for_location(self, location: str) -> Dict[str, int]:
        """Get summary counts for a specific location."""
        messages = self.get_messages_for_location(location)
        summary = {}
        for msg in messages:
            summary[msg.importance] = summary.get(msg.importance, 0) + 1
        return summary
    
    def get_icon_summary_for_location(self, location: str) -> str:
        """Get a formatted icon summary for display."""
        summary = self.get_summary_for_location(location)
        if not summary:
            return "✅"
        
        priority_order = ["ERROR", "PYNWB_VALIDATION", "CRITICAL", 
                         "BEST_PRACTICE_VIOLATION", "BEST_PRACTICE_SUGGESTION"]
        
        parts = []
        for importance in priority_order:
            if importance in summary:
                count = summary[importance]
                # Get icon based on importance
                if importance in ["ERROR", "PYNWB_VALIDATION", "CRITICAL"]:
                    icon = "❌"
                elif importance == "BEST_PRACTICE_VIOLATION":
                    icon = "⚠️"
                elif importance == "BEST_PRACTICE_SUGGESTION":
                    icon = "💡"
                else:
                    icon = "❓"
                parts.append(f"{icon}{count}")
        
        return " ".join(parts) if parts else "✅"
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'InspectorResults':
        """Create from JSON data (from nwbinspector output)."""
        results = cls()
        
        # Parse messages from the data
        if isinstance(data, list):
            # Direct list of messages
            for msg_data in data:
                message = InspectorMessage.from_dict(msg_data)
                results.add_message(message)
        elif isinstance(data, dict):
            # Could be the full inspector output
            if "inspection_results" in data:
                # Our format
                for location, messages in data["inspection_results"].items():
                    for msg_data in messages:
                        message = InspectorMessage.from_dict(msg_data)
                        message.location = location
                        results.add_message(message)
            else:
                # Direct nwbinspector JSON output format
                for msg_data in data.get("messages", []):
                    message = InspectorMessage.from_dict(msg_data)
                    results.add_message(message)
        
        return results


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
    inspector_messages: List[InspectorMessage] = field(default_factory=list)
    
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
    
    def get_inspector_icon(self) -> str:
        """Get inspector icon summary for this object."""
        if not self.inspector_messages:
            return ""
        
        summary = {}
        for msg in self.inspector_messages:
            summary[msg.importance] = summary.get(msg.importance, 0) + 1
        
        priority_order = ["ERROR", "PYNWB_VALIDATION", "CRITICAL", 
                         "BEST_PRACTICE_VIOLATION", "BEST_PRACTICE_SUGGESTION"]
        
        parts = []
        for importance in priority_order:
            if importance in summary:
                count = summary[importance]
                if importance in ["ERROR", "PYNWB_VALIDATION", "CRITICAL"]:
                    icon = "❌"
                elif importance == "BEST_PRACTICE_VIOLATION":
                    icon = "⚠️"
                elif importance == "BEST_PRACTICE_SUGGESTION":
                    icon = "💡"
                else:
                    icon = "❓"
                parts.append(f"{icon}{count}")
        
        return " ".join(parts) if parts else ""
    
    def has_inspector_issues(self) -> bool:
        """Check if this object has any inspector issues."""
        return len(self.inspector_messages) > 0
    
    def get_worst_severity(self) -> Optional[str]:
        """Get the worst severity level from inspector messages."""
        if not self.inspector_messages:
            return None
        
        severity_order = ['ERROR', 'PYNWB_VALIDATION', 'CRITICAL', 
                         'BEST_PRACTICE_VIOLATION', 'BEST_PRACTICE_SUGGESTION']
        
        for severity in severity_order:
            if any(msg.importance == severity for msg in self.inspector_messages):
                return severity
        
        return None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation for JSON export."""
        result = {
            "name": self.name,
            "type": self.type,
            "class": self.class_name,
            "path": self.path,
            "fields": self.fields,
            "attributes": self.attributes,
            "children": [child.to_dict() for child in self.children]
        }
        
        # Add inspector data if present
        if self.inspector_messages:
            result["inspection"] = {
                "messages": [
                    {
                        "message": msg.message,
                        "importance": msg.importance,
                        "importance_level": msg.importance_level,
                        "severity": msg.severity,
                        "check_function": msg.check_function
                    }
                    for msg in self.inspector_messages
                ],
                "has_issues": True,
                "summary": self.get_inspector_icon()
            }
        
        return result