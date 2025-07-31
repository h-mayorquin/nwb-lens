"""nwbinspector integration manager."""

from pathlib import Path
from typing import Dict, List, Optional

try:
    import nwbinspector
    INSPECTOR_AVAILABLE = True
except ImportError:
    INSPECTOR_AVAILABLE = False


class InspectorManager:
    """Manage nwbinspector integration."""
    
    def __init__(self):
        self.results = None
        self.problems_by_path = {}
    
    def is_available(self) -> bool:
        """Check if nwbinspector is available."""
        return INSPECTOR_AVAILABLE
    
    def run_inspector(self, filepath: Path) -> List[Dict]:
        """Run nwbinspector and return results."""
        if not self.is_available():
            raise RuntimeError(
                "nwbinspector not available. Install with: uv add --optional inspector"
            )
        
        try:
            # Run nwbinspector
            results = list(nwbinspector.inspect_nwbfile(nwbfile_path=str(filepath)))
            
            # Convert to our format
            formatted_results = []
            for result in results:
                formatted_result = {
                    'path': getattr(result, 'object_name', ''),
                    'severity': result.severity.name,
                    'message': result.message,
                    'check_name': result.check_function_name,
                }
                formatted_results.append(formatted_result)
            
            self.results = formatted_results
            self.problems_by_path = self._map_problems_to_paths(formatted_results)
            return formatted_results
            
        except Exception as e:
            raise RuntimeError(f"nwbinspector failed: {e}")
    
    def _map_problems_to_paths(self, problems: List[Dict]) -> Dict[str, List[Dict]]:
        """Map inspector problems to object paths."""
        problems_map = {}
        
        for problem in problems:
            path = problem['path']
            if path not in problems_map:
                problems_map[path] = []
            problems_map[path].append(problem)
        
        return problems_map
    
    def get_problems_for_path(self, path: str) -> List[Dict]:
        """Get problems for a specific object path."""
        return self.problems_by_path.get(path, [])
    
    def get_severity_icon(self, severity: str) -> str:
        """Get visual indicator for problem severity."""
        severity_icons = {
            'CRITICAL': '❌',
            'ERROR': '❌', 
            'WARNING': '⚠️',
            'INFO': '💡',
            'SUGGESTION': '💡',
        }
        return severity_icons.get(severity.upper(), '❓')
    
    def has_problems_for_path(self, path: str) -> bool:
        """Check if there are problems for a specific path."""
        return path in self.problems_by_path
    
    def get_worst_severity_for_path(self, path: str) -> Optional[str]:
        """Get the worst severity level for a path."""
        if not self.has_problems_for_path(path):
            return None
        
        problems = self.problems_by_path[path]
        severity_order = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'SUGGESTION']
        
        for severity in severity_order:
            if any(p['severity'] == severity for p in problems):
                return severity
        
        return None