"""NWBInspector integration manager for extracting validation results to JSON."""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    from nwbinspector import (
        inspect_nwbfile_object, 
        configure_checks, 
        available_checks,
        Importance,
        Severity
    )
    NWBINSPECTOR_AVAILABLE = True
except ImportError:
    NWBINSPECTOR_AVAILABLE = False
    # Define minimal types for when nwbinspector is not available
    class Importance:
        BEST_PRACTICE_SUGGESTION = 0
        BEST_PRACTICE_VIOLATION = 1  
        CRITICAL = 2
        PYNWB_VALIDATION = 3
        ERROR = 4
    
    class Severity:
        LOW = 0
        MEDIUM = 1
        HIGH = 2


class InspectorManager:
    """
    Manager for integrating nwbinspector functionality with NWB Lens.
    
    Extracts validation results to JSON format that can be merged
    with the NWB structure JSON for unified display.
    """
    
    def __init__(self):
        """Initialize the inspector manager."""
        self.messages = []
        self.location_map = {}
        self.checks_configured = False
        self.last_inspection_time = None
        
        if not NWBINSPECTOR_AVAILABLE:
            print("Warning: nwbinspector not available. Inspector functionality disabled.")
    
    def is_available(self) -> bool:
        """Check if nwbinspector is available."""
        return NWBINSPECTOR_AVAILABLE
    
    def configure_for_tui(self, importance_threshold: int = Importance.BEST_PRACTICE_SUGGESTION) -> None:
        """
        Configure checks optimized for TUI usage.
        
        Args:
            importance_threshold: Minimum importance level to include
        """
        if not NWBINSPECTOR_AVAILABLE:
            return
            
        try:
            # For TUI usage, we might want to skip the most time-consuming checks
            # and focus on structural/metadata issues that are quick to validate
            self.checks = configure_checks(
                importance_threshold=importance_threshold
            )
            self.checks_configured = True
        except Exception as e:
            print(f"Warning: Could not configure nwbinspector checks: {e}")
            self.checks_configured = False
    
    def extract_inspection_to_json(self, nwbfile) -> Dict[str, Any]:
        """
        Extract nwbinspector results to JSON format.
        
        Args:
            nwbfile: PyNWB NWBFile object
            
        Returns:
            Dictionary with inspection results organized by location
        """
        if not NWBINSPECTOR_AVAILABLE:
            return {
                "inspection_results": {},
                "summary": {"total": 0, "by_importance": {}},
                "inspection_info": {
                    "available": False,
                    "reason": "nwbinspector not installed"
                }
            }
        
        if not self.checks_configured:
            self.configure_for_tui()
        
        try:
            # Run inspection
            messages = list(inspect_nwbfile_object(
                nwbfile_object=nwbfile,
                checks=self.checks if self.checks_configured else None
            ))
            
            # Organize by location
            location_map = {}
            importance_counts = {}
            
            for msg in messages:
                # Get location - use root if none specified
                location = msg.location if msg.location else "/"
                
                # Initialize location if not seen before
                if location not in location_map:
                    location_map[location] = []
                
                # Convert message to JSON-serializable format
                msg_dict = {
                    "message": msg.message,
                    "importance": msg.importance.name if hasattr(msg.importance, 'name') else str(msg.importance),
                    "importance_level": msg.importance.value if hasattr(msg.importance, 'value') else int(msg.importance),
                    "severity": msg.severity.name if hasattr(msg.severity, 'name') else str(msg.severity),
                    "severity_level": msg.severity.value if hasattr(msg.severity, 'value') else int(msg.severity),
                    "check_function": msg.check_function_name,
                    "object_type": msg.object_type,
                    "object_name": msg.object_name,
                    "file_path": msg.file_path
                }
                
                location_map[location].append(msg_dict)
                
                # Count by importance
                importance_name = msg_dict["importance"]
                importance_counts[importance_name] = importance_counts.get(importance_name, 0) + 1
            
            # Store for later access
            self.messages = messages
            self.location_map = location_map
            self.last_inspection_time = datetime.now().isoformat()
            
            return {
                "inspection_results": location_map,
                "summary": {
                    "total": len(messages),
                    "by_importance": importance_counts,
                    "locations": len(location_map)
                },
                "inspection_info": {
                    "available": True,
                    "timestamp": self.last_inspection_time,
                    "checks_configured": self.checks_configured,
                    "total_checks": len(available_checks) if NWBINSPECTOR_AVAILABLE else 0
                }
            }
            
        except Exception as e:
            return {
                "inspection_results": {},
                "summary": {"total": 0, "by_importance": {}},
                "inspection_info": {
                    "available": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            }
    
    async def extract_inspection_async(self, nwbfile) -> Dict[str, Any]:
        """
        Extract inspection results asynchronously to avoid blocking the TUI.
        
        Args:
            nwbfile: PyNWB NWBFile object
            
        Returns:
            Dictionary with inspection results
        """
        if not NWBINSPECTOR_AVAILABLE:
            return self.extract_inspection_to_json(nwbfile)
        
        loop = asyncio.get_event_loop()
        
        # Run inspection in thread pool to avoid blocking
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor,
                self.extract_inspection_to_json,
                nwbfile
            )
        
        return result
    
    def get_messages_for_location(self, location: str) -> List[Dict[str, Any]]:
        """
        Get all inspection messages for a specific location.
        
        Args:
            location: Path location in the NWB file
            
        Returns:
            List of message dictionaries for the location
        """
        return self.location_map.get(location, [])
    
    def get_summary_for_location(self, location: str) -> Dict[str, int]:
        """
        Get summary counts of messages by importance for a location.
        
        Args:
            location: Path location in the NWB file
            
        Returns:
            Dictionary with counts by importance level
        """
        messages = self.get_messages_for_location(location)
        summary = {}
        
        for msg in messages:
            importance = msg["importance"]
            summary[importance] = summary.get(importance, 0) + 1
        
        return summary
    
    def format_summary_for_display(self, location: str) -> str:
        """
        Format inspection summary for display in the tree.
        
        Args:
            location: Path location in the NWB file
            
        Returns:
            Formatted string like "❌2 ⚠️1 💡3"
        """
        summary = self.get_summary_for_location(location)
        if not summary:
            return "✅"
        
        # Map importance to symbols
        symbols = {
            "ERROR": "❌",
            "PYNWB_VALIDATION": "❌", 
            "CRITICAL": "❌",
            "BEST_PRACTICE_VIOLATION": "⚠️",
            "BEST_PRACTICE_SUGGESTION": "💡"
        }
        
        # Priority order for display
        priority_order = ["ERROR", "PYNWB_VALIDATION", "CRITICAL", "BEST_PRACTICE_VIOLATION", "BEST_PRACTICE_SUGGESTION"]
        
        parts = []
        for importance in priority_order:
            if importance in summary:
                count = summary[importance]
                symbol = symbols.get(importance, "?")
                parts.append(f"{symbol}{count}")
        
        return " ".join(parts) if parts else "✅"
    
    def save_inspection_json(self, inspection_data: Dict[str, Any], output_path: Path) -> None:
        """
        Save inspection results to JSON file.
        
        Args:
            inspection_data: Inspection results dictionary
            output_path: Path to save JSON file
        """
        with open(output_path, 'w') as f:
            json.dump(inspection_data, f, indent=2)
    
    def load_inspection_json(self, json_path: Path) -> Dict[str, Any]:
        """
        Load previously saved inspection results.
        
        Args:
            json_path: Path to JSON file
            
        Returns:
            Inspection results dictionary
        """
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Check if this is raw nwbinspector output
        if "messages" in data and "header" in data:
            # Convert from nwbinspector format to our format
            return self.parse_nwbinspector_json(data)
        
        return data
    
    def parse_nwbinspector_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw nwbinspector JSON output into our format.
        
        Args:
            data: Raw nwbinspector JSON data
            
        Returns:
            Inspection results in our format
        """
        location_map = {}
        importance_counts = {}
        
        for msg in data.get("messages", []):
            # Get location - use root if none specified
            location = msg.get("location")
            if location is None:
                # Try to infer location for processing modules and other objects
                obj_type = msg.get("object_type", "")
                obj_name = msg.get("object_name", "")
                
                if obj_type == "ProcessingModule" and obj_name:
                    # ProcessingModules are typically under /processing/
                    location = f"/processing/{obj_name}"
                elif obj_type and obj_name:
                    # Generic fallback
                    location = f"/{obj_type}/{obj_name}"
                else:
                    location = "/"
            
            # Initialize location if not seen before
            if location not in location_map:
                location_map[location] = []
            
            # Convert message to our format
            msg_dict = {
                "message": msg.get("message", ""),
                "importance": msg.get("importance", "UNKNOWN"),
                "importance_level": self._get_importance_level(msg.get("importance")),
                "severity": msg.get("severity", "LOW"),
                "severity_level": self._get_severity_level(msg.get("severity")),
                "check_function": msg.get("check_function_name", ""),
                "object_type": msg.get("object_type"),
                "object_name": msg.get("object_name"),
                "file_path": msg.get("file_path"),
                "location": location
            }
            
            location_map[location].append(msg_dict)
            
            # Count by importance
            importance_name = msg_dict["importance"]
            importance_counts[importance_name] = importance_counts.get(importance_name, 0) + 1
        
        # Store for later access
        self.location_map = location_map
        self.last_inspection_time = data.get("header", {}).get("Timestamp", datetime.now().isoformat())
        
        return {
            "inspection_results": location_map,
            "summary": {
                "total": len(data.get("messages", [])),
                "by_importance": importance_counts,
                "locations": len(location_map)
            },
            "inspection_info": {
                "available": True,
                "timestamp": self.last_inspection_time,
                "version": data.get("header", {}).get("NWBInspector_version", "unknown"),
                "total_messages": len(data.get("messages", []))
            }
        }
    
    def _get_importance_level(self, importance: str) -> int:
        """Get numeric importance level from string."""
        levels = {
            "BEST_PRACTICE_SUGGESTION": 0,
            "BEST_PRACTICE_VIOLATION": 1,
            "CRITICAL": 2,
            "PYNWB_VALIDATION": 3,
            "ERROR": 4
        }
        return levels.get(importance, 0)
    
    def _get_severity_level(self, severity: str) -> int:
        """Get numeric severity level from string."""
        levels = {
            "LOW": 0,
            "MEDIUM": 1,
            "HIGH": 2
        }
        return levels.get(severity, 0)
    
    # Legacy compatibility methods
    def get_problems_for_path(self, path: str) -> List[Dict]:
        """Get problems for a specific object path (legacy compatibility)."""
        messages = self.get_messages_for_location(path)
        return [
            {
                'path': path,
                'severity': msg.get('importance', 'UNKNOWN'),
                'message': msg.get('message', ''),
                'check_name': msg.get('check_function', ''),
            }
            for msg in messages
        ]
    
    def get_severity_icon(self, severity: str) -> str:
        """Get visual indicator for problem severity (legacy compatibility)."""
        severity_icons = {
            'CRITICAL': '❌',
            'ERROR': '❌', 
            'WARNING': '⚠️',
            'BEST_PRACTICE_VIOLATION': '⚠️',
            'INFO': '💡',
            'SUGGESTION': '💡',
            'BEST_PRACTICE_SUGGESTION': '💡',
        }
        return severity_icons.get(severity.upper(), '❓')
    
    def has_problems_for_path(self, path: str) -> bool:
        """Check if there are problems for a specific path (legacy compatibility)."""
        return len(self.get_messages_for_location(path)) > 0
    
    def get_worst_severity_for_path(self, path: str) -> Optional[str]:
        """Get the worst severity level for a path (legacy compatibility)."""
        messages = self.get_messages_for_location(path)
        if not messages:
            return None
        
        severity_order = ['ERROR', 'PYNWB_VALIDATION', 'CRITICAL', 'BEST_PRACTICE_VIOLATION', 'BEST_PRACTICE_SUGGESTION']
        
        for severity in severity_order:
            if any(msg['importance'] == severity for msg in messages):
                return severity
        
        return None


