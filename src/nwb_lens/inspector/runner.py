"""Inspector runner for async nwbinspector execution."""

import asyncio
from pathlib import Path
from typing import Any, Dict

from .manager import InspectorManager


class InspectorRunner:
    """
    Handles running nwbinspector asynchronously.
    
    This class is responsible for executing nwbinspector validation
    on NWB files and returning structured results.
    """
    
    def __init__(self):
        """Initialize the inspector runner."""
        self.manager = InspectorManager()
    
    def is_available(self) -> bool:
        """Check if nwbinspector is available."""
        return self.manager.is_available()
    
    async def run_inspection(self, file_path: Path) -> Dict[str, Any]:
        """
        Run nwbinspector on an NWB file asynchronously.
        
        Args:
            file_path: Path to the NWB file to inspect
            
        Returns:
            Dictionary with inspection results
        """
        if not self.manager.is_available():
            return {
                "inspection_results": {},
                "summary": {"total": 0, "by_importance": {}},
                "inspection_info": {
                    "available": False,
                    "reason": "nwbinspector not installed"
                }
            }
        
        try:
            # Load NWB file for inspection
            from pynwb import NWBHDF5IO
            with NWBHDF5IO(str(file_path), mode="r") as io:
                nwbfile = io.read()
                
                # Run inspection asynchronously
                return await self.manager.extract_inspection_async(nwbfile)
                
        except Exception as e:
            return {
                "inspection_results": {},
                "summary": {"total": 0, "by_importance": {}},
                "inspection_info": {
                    "available": False,
                    "error": str(e)
                }
            }
    
    def run_inspection_sync(self, file_path: Path) -> Dict[str, Any]:
        """
        Run nwbinspector on an NWB file synchronously.
        
        Args:
            file_path: Path to the NWB file to inspect
            
        Returns:
            Dictionary with inspection results
        """
        if not self.manager.is_available():
            return {
                "inspection_results": {},
                "summary": {"total": 0, "by_importance": {}},
                "inspection_info": {
                    "available": False,
                    "reason": "nwbinspector not installed"
                }
            }
        
        try:
            # Load NWB file for inspection
            from pynwb import NWBHDF5IO
            with NWBHDF5IO(str(file_path), mode="r") as io:
                nwbfile = io.read()
                
                # Run inspection
                return self.manager.extract_inspection_to_json(nwbfile)
                
        except Exception as e:
            return {
                "inspection_results": {},
                "summary": {"total": 0, "by_importance": {}},
                "inspection_info": {
                    "available": False,
                    "error": str(e)
                }
            }
    
    def load_inspection_from_file(self, inspector_json_path: Path) -> Dict[str, Any]:
        """
        Load inspection results from a JSON file.
        
        Args:
            inspector_json_path: Path to nwbinspector JSON output file
            
        Returns:
            Dictionary with inspection results
        """
        return self.manager.load_inspection_json(inspector_json_path)