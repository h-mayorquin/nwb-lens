"""Convert NWB structures to JSON representation."""

import json
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

import numpy as np
import pynwb
from pynwb import NWBHDF5IO


class NWBJSONConverter:
    """Convert NWB file structures to JSON for memory-efficient navigation."""
    
    def __init__(self):
        self.file_path = None
        self._object_registry = {}  # Track objects to handle references
        self._path_counter = 0
    
    def extract_to_json(self, file_path: Path) -> dict[str, Any]:
        """
        Extract NWB file structure to JSON representation.
        
        This performs a one-time extraction and closes the file handle,
        keeping only the JSON structure in memory.
        """
        self.file_path = str(file_path)
        self._object_registry.clear()
        
        try:
            with NWBHDF5IO(str(file_path), mode="r") as io:
                nwbfile = io.read()
                
                # Extract file metadata
                file_info = {
                    "path": str(file_path),
                    "name": file_path.name,
                    "size": file_path.stat().st_size if file_path.exists() else 0,
                }
                
                # Get NWB version from various possible sources
                if hasattr(nwbfile, 'nwb_version'):
                    file_info["nwb_version"] = str(nwbfile.nwb_version)
                elif hasattr(nwbfile, 'fields') and 'nwb_version' in nwbfile.fields:
                    file_info["nwb_version"] = str(nwbfile.fields['nwb_version'])
                else:
                    file_info["nwb_version"] = "unknown"
                
                # Build complete structure
                structure = self._build_json_structure(nwbfile, "/")
                
                return {
                    "file_info": file_info,
                    "structure": structure,
                    "extraction_time": datetime.now().isoformat()
                }
                
        except Exception as e:
            raise RuntimeError(f"Failed to extract NWB file to JSON: {e}")
    
    def _build_json_structure(self, obj: Any, path: str) -> dict[str, Any]:
        """Recursively build JSON representation of NWB objects."""
        
        # Handle None objects
        if obj is None:
            return {"type": "None", "value": None}
        
        # Get basic object information
        obj_id = id(obj)
        if obj_id in self._object_registry:
            # Handle circular references
            return {
                "type": "Reference",
                "ref_path": self._object_registry[obj_id]["path"],
                "ref_type": self._object_registry[obj_id]["type"]
            }
        
        # Extract object info
        obj_info = self._extract_object_info(obj, path)
        
        # Register object to handle references
        self._object_registry[obj_id] = {
            "path": obj_info["path"],
            "type": obj_info["type"]
        }
        
        # Extract children
        children = self._extract_children(obj, obj_info["path"])
        if children:
            obj_info["children"] = children
        
        return obj_info
    
    def _extract_object_info(self, obj: Any, path: str) -> dict[str, Any]:
        """Extract core information from an NWB object."""
        
        # Basic properties
        info = {
            "name": self._get_name(obj),
            "type": type(obj).__name__,
            "class": obj.__class__.__module__ + "." + obj.__class__.__name__,
            "path": path,
        }
        
        # Extract fields
        fields = self._extract_fields(obj)
        if fields:
            info["fields"] = fields
        
        # Extract attributes
        attributes = self._extract_attributes(obj)
        if attributes:
            info["attributes"] = attributes
        
        # Extract data information (shapes, dtypes) without loading data
        data_info = self._extract_data_info(obj)
        if data_info:
            info["data_info"] = data_info
        
        return info
    
    def _get_name(self, obj: Any) -> str:
        """Get object name."""
        if hasattr(obj, 'name'):
            return str(obj.name)
        elif hasattr(obj, 'object_id'):
            return str(obj.object_id)
        else:
            return obj.__class__.__name__
    
    def _extract_fields(self, obj: Any) -> dict[str, Any]:
        """Extract field information from container objects."""
        fields = {}
        
        # Handle NWB containers with fields
        if hasattr(obj, 'fields'):
            for field_name, field_value in obj.fields.items():
                if field_value is not None:
                    fields[field_name] = self._get_field_summary(field_value)
        
        return fields
    
    def _get_field_summary(self, value: Any) -> Any:
        """Get a JSON-serializable summary of a field value."""
        if value is None:
            return None
        elif isinstance(value, (str, int, bool)):
            return value
        elif isinstance(value, float):
            # Handle special float values
            if np.isnan(value):
                return None
            elif np.isinf(value):
                return None
            else:
                return value
        elif isinstance(value, (list, tuple)):
            return f"{type(value).__name__}[{len(value)}]"
        elif isinstance(value, dict):
            return f"dict[{len(value)} keys]"
        elif hasattr(value, 'name'):
            # Check if this is a reference to another object with a path
            value_type = type(value).__name__
            
            # Handle different types of references
            if hasattr(value, 'object') and hasattr(value.object, 'name'):
                # For references like imaging planes, electrodes, etc.
                ref_name = value.object.name
                ref_type = type(value.object).__name__
                
                # Try to determine the path based on object type and name
                if ref_type == 'ImagingPlane':
                    return f"{ref_type}: /imaging_planes/{ref_name}"
                elif ref_type == 'Device':
                    return f"{ref_type}: /devices/{ref_name}"
                elif ref_type == 'ElectrodeGroup':
                    return f"{ref_type}: /electrode_groups/{ref_name}"
                elif 'table' in value_type.lower():
                    # For table references like electrodes
                    if 'electrode' in ref_name.lower():
                        return f"{ref_type}: /electrodes"
                    else:
                        return f"{ref_type}: /{ref_name}"
                else:
                    return f"{ref_type}: {ref_name}"
            elif hasattr(value, 'table') and hasattr(value.table, 'name'):
                # Handle DynamicTableRegion references
                table_name = value.table.name
                if 'electrode' in table_name.lower():
                    return f"{value_type}: /electrodes"
                else:
                    return f"{value_type}: /{table_name}"
            else:
                return f"{value_type}: {value.name}"
        else:
            return type(value).__name__
    
    def _extract_attributes(self, obj: Any) -> dict[str, Any]:
        """Extract attributes and metadata."""
        attributes = {}
        
        # Common NWB attributes
        common_attrs = [
            'description', 'comments', 'source', 'unit', 'units',
            'resolution', 'conversion', 'offset', 'starting_time',
            'rate', 'sampling_rate', 'help'
        ]
        
        for attr in common_attrs:
            if hasattr(obj, attr):
                value = getattr(obj, attr)
                if value is not None:
                    attributes[attr] = self._serialize_value(value)
        
        # Handle timestamps
        if hasattr(obj, 'timestamps') and obj.timestamps is not None:
            if hasattr(obj.timestamps, 'shape'):
                attributes['timestamps_shape'] = list(obj.timestamps.shape)
            else:
                attributes['has_timestamps'] = True
        
        return attributes
    
    def _extract_data_info(self, obj: Any) -> Optional[dict[str, Any]]:
        """Extract data shape and type information without loading data."""
        data_info = {}
        
        # Handle data arrays
        if hasattr(obj, 'data') and obj.data is not None:
            data = obj.data
            
            # Get shape
            if hasattr(data, 'shape'):
                data_info['shape'] = list(data.shape)
            
            # Get dtype
            if hasattr(data, 'dtype'):
                data_info['dtype'] = str(data.dtype)
            
            # Get chunking info for HDF5 datasets
            if hasattr(data, 'chunks'):
                data_info['chunks'] = data.chunks
            
            # Add compression information (following HDMF approach)
            # Check if it's an HDF5 dataset
            try:
                import h5py
                if isinstance(data, h5py.Dataset):
                    # Get compression info
                    if hasattr(data, 'compression') and data.compression is not None:
                        data_info['compression'] = data.compression
                    
                    if hasattr(data, 'compression_opts') and data.compression_opts is not None:
                        data_info['compression_opts'] = data.compression_opts
                    
                    # Calculate compression ratio and sizes
                    try:
                        compressed_size = data.id.get_storage_size()
                        if hasattr(data, "nbytes"):
                            uncompressed_size = data.nbytes
                        else:
                            uncompressed_size = data.size * data.dtype.itemsize
                        
                        # Store raw sizes in bytes
                        data_info['uncompressed_size_bytes'] = uncompressed_size
                        data_info['compressed_size_bytes'] = compressed_size
                        
                        if compressed_size != 0:
                            compression_ratio = uncompressed_size / compressed_size
                            data_info['compression_ratio'] = round(compression_ratio, 2)
                    except Exception:
                        # Skip compression info if we can't calculate it
                        pass
            except ImportError:
                # h5py not available, skip compression info
                pass
            
            # Check if it's a link/reference
            if hasattr(data, 'file') and hasattr(data, 'name'):
                data_info['hdf5_path'] = data.name
        
        return data_info if data_info else None
    
    def _extract_children(self, obj: Any, parent_path: str) -> list[dict[str, Any]]:
        """Extract child objects."""
        children = []
        
        # Handle NWBFile root containers
        if isinstance(obj, pynwb.file.NWBFile):
            # Standard NWBFile containers
            # Process devices first so references appear elsewhere, then tables, then other containers
            containers = [
                ('devices', obj.devices if hasattr(obj, 'devices') else None),
                ('electrode_groups', obj.electrode_groups if hasattr(obj, 'electrode_groups') else None),
                ('imaging_planes', obj.imaging_planes if hasattr(obj, 'imaging_planes') else None),
                ('electrodes', obj.electrodes if hasattr(obj, 'electrodes') else None),
                ('units', obj.units if hasattr(obj, 'units') else None),
                ('acquisition', obj.acquisition if hasattr(obj, 'acquisition') else None),
                ('processing', obj.processing if hasattr(obj, 'processing') else None),
                ('analysis', obj.analysis if hasattr(obj, 'analysis') else None),
                ('intervals', obj.intervals if hasattr(obj, 'intervals') else None),
                ('general', obj.general if hasattr(obj, 'general') else None),
            ]
            
            for name, container in containers:
                if container:
                    child_path = f"{parent_path}/{name}" if parent_path != "/" else f"/{name}"
                    # Check if it's a DynamicTable (units, electrodes, etc.)
                    if hasattr(container, 'columns'):
                        # It's a table, extract it directly
                        children.append(self._build_json_structure(container, child_path))
                    elif hasattr(container, '__len__') and not isinstance(container, str):
                        # Handle collections
                        collection_info = {
                            "name": name,
                            "type": "Collection",
                            "class": type(container).__name__,
                            "path": child_path,
                            "children": []
                        }
                        
                        # Extract items from collection
                        try:
                            items = dict(container) if hasattr(container, 'items') else list(container)
                            if isinstance(items, dict):
                                for item_name, item in items.items():
                                    item_path = f"{child_path}/{item_name}"
                                    collection_info["children"].append(
                                        self._build_json_structure(item, item_path)
                                    )
                            else:
                                for i, item in enumerate(items):
                                    item_name = getattr(item, 'name', f"item_{i}")
                                    item_path = f"{child_path}/{item_name}"
                                    collection_info["children"].append(
                                        self._build_json_structure(item, item_path)
                                    )
                            
                            # Sort collection children alphabetically by name
                            collection_info["children"].sort(key=lambda x: x.get("name", "").lower())
                        except Exception:
                            # If iteration fails, just add as single child
                            collection_info = self._build_json_structure(container, child_path)
                        
                        children.append(collection_info)
                    else:
                        # Single container
                        children.append(self._build_json_structure(container, child_path))
        
        # Handle DynamicTable objects (includes Units, ElectrodesTable, etc.)
        elif hasattr(obj, 'columns'):
            # Extract all columns from the table
            if hasattr(obj, 'colnames'):
                for col_name in obj.colnames:
                    if hasattr(obj, col_name):
                        col_obj = getattr(obj, col_name)
                        child_path = f"{parent_path}/{col_name}"
                        children.append(self._build_json_structure(col_obj, child_path))
            
            # Also add the id column if it exists
            if hasattr(obj, 'id'):
                id_path = f"{parent_path}/id"
                children.append(self._build_json_structure(obj.id, id_path))
        
        # Handle ProcessingModule and other containers with data_interfaces
        elif hasattr(obj, 'data_interfaces') and obj.data_interfaces:
            for name, interface in obj.data_interfaces.items():
                child_path = f"{parent_path}/{name}"
                children.append(self._build_json_structure(interface, child_path))
        
        # Handle containers with fields
        elif hasattr(obj, 'fields') and obj.fields:
            for field_name, field_value in obj.fields.items():
                if field_value is not None:
                    child_path = f"{parent_path}/{field_name}"
                    
                    # Check if field_value is directly a container
                    if self._is_container(field_value):
                        children.append(self._build_json_structure(field_value, child_path))
                    # Check if field_value is a dict/LabelledDict containing containers
                    elif hasattr(field_value, 'items'):
                        try:
                            # Create a collection node for the field
                            collection_info = {
                                "name": field_name,
                                "type": "Collection",
                                "class": type(field_value).__name__,
                                "path": child_path,
                                "children": []
                            }
                            
                            # Extract items from the field collection
                            for item_name, item in field_value.items():
                                if self._is_container(item):
                                    item_path = f"{child_path}/{item_name}"
                                    collection_info["children"].append(
                                        self._build_json_structure(item, item_path)
                                    )
                            
                            # Only add if we found containers
                            if collection_info["children"]:
                                children.append(collection_info)
                        except (AttributeError, TypeError):
                            # If iteration fails, skip this field
                            pass
        
        # Sort children alphabetically by name for consistent ordering
        children.sort(key=lambda x: x.get("name", "").lower())
        
        return children
    
    def _is_container(self, obj: Any) -> bool:
        """Check if object is a container that should be traversed."""
        # Don't traverse basic types
        if isinstance(obj, (str, int, float, bool, bytes, type(None))):
            return False
        
        # Don't traverse numpy arrays or similar
        if hasattr(obj, 'shape') and hasattr(obj, 'dtype'):
            return False
        
        # Check for NWB container types
        return hasattr(obj, '__class__') and (
            hasattr(obj, 'fields') or
            hasattr(obj, 'name') or
            hasattr(obj, 'data_interfaces')
        )
    
    def _serialize_value(self, value: Any) -> Any:
        """Convert value to JSON-serializable format."""
        if isinstance(value, (str, int, bool, type(None))):
            return value
        elif isinstance(value, float):
            # Handle special float values that aren't JSON-compliant
            if np.isnan(value):
                return None  # or "NaN" as string if you prefer
            elif np.isinf(value):
                return None  # or "Infinity"/"-Infinity" as string
            else:
                return value
        elif isinstance(value, (list, tuple)):
            return [self._serialize_value(v) for v in value]
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        elif isinstance(value, np.ndarray):
            return {
                "type": "ndarray",
                "shape": list(value.shape),
                "dtype": str(value.dtype)
            }
        elif hasattr(value, 'isoformat'):  # datetime
            return value.isoformat()
        else:
            return str(value)
    
    def save_json(self, data: dict[str, Any], output_path: Path) -> None:
        """Save extracted structure to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_json(self, json_path: Path) -> dict[str, Any]:
        """Load previously extracted JSON structure."""
        with open(json_path, 'r') as f:
            return json.load(f)