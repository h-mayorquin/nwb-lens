# NWB Explorer - Technical Specification

## Project Overview

**Goal**: Create an interactive terminal-based NWB file explorer for debugging and exploration, similar to `h5ls` but NWB-aware, with integrated validation capabilities.

## Core Requirements

### Primary Use Cases
- **Interactive Exploration**: Navigate NWB file structure in a rich TUI interface
- **Problem Identification**: Identify naming issues, incorrect shapes, missing data/metadata
- **Validation Integration**: On-demand nwbinspector integration to highlight problems
- **Structured Export**: JSON output for programmatic analysis or LLM consumption

### Target Problems to Address
- Incorrect naming conventions
- Data shape mismatches
- Missing required data and metadata
- Schema compliance issues

## Technical Architecture

### Technology Stack
- **TUI Framework**: Textual (rich terminal interface)
- **NWB Loading**: PyNWB (for file loading and object access)
- **Structure Generation**: Custom tree builder (decoupled from PyNWB's _repr_html_)
- **Validation**: nwbinspector package (on-demand integration)
- **CLI Framework**: Typer (for argument parsing and non-interactive modes)
- **Output Format**: JSON (structured, machine-readable)

### Core Design Philosophy

#### Decoupled Structure Representation
- **Inspiration**: Use PyNWB's _repr_html_ patterns as reference for what to display
- **Implementation**: Build independent tree structure representation
- **Benefits**: Full control over display logic, easier to extend/modify
- **Approach**: Extract information from PyNWB objects but render independently

#### JSON-First Architecture (Optional)
- **Design**: Extract NWB structure to JSON representation, close file handle
- **Benefits**: Memory efficiency, faster UI navigation, clean serialization
- **Optionality**: System supports both JSON mode (default) and live PyNWB mode
- **Validation**: Re-open file temporarily when nwbinspector is needed

#### Custom Tree Builder
```python
class NWBStructureBuilder:
    """Independent structure builder inspired by _repr_html_ patterns"""
    
    def build_structure(self, nwbfile):
        # Extract structure info from PyNWB objects
        # But build our own representation tree
        return self._build_container_tree(nwbfile)
    
    def _build_container_tree(self, container):
        # Mirror the logic of _repr_html_ but for our tree structure
        # Extract: name, type, fields, attributes
        # Don't depend on PyNWB's HTML generation
```

### Core Components

#### 1. Interactive TUI Application
```
┌─ NWB Explorer: filename.nwb ─────────────────────────────────┐
│ File: test.nwb │ NWB 2.5.0 │ 45.2MB                         │
├──────────────────────────────────────────────────────────────┤
│ 📁 Object Tree            │ 📋 Attributes & Metadata        │
│ ├─📂 acquisition          │ Selected: /acquisition           │
│ ├─📂 processing           │ Type: NWBContainer               │
│ ├─📂 analysis             │ Class: LazyDataInterface         │
│ ├─📂 intervals            │ Fields: 2 items                  │
│ ├─📂 general              │ - neural_data (TimeSeries)       │
│ └─📂 devices              │ - behavior_data (TimeSeries)     │
│                           │                                  │
├──────────────────────────────────────────────────────────────┤
│ [I] Inspector | [O] Output | [Q] Quit                        │
└──────────────────────────────────────────────────────────────┘
```

#### 2. Command Line Interface
```bash
# Interactive mode (default)
nwb-explorer file.nwb

# Interactive with inspector pre-loaded
nwb-explorer file.nwb --inspect

# JSON output mode
nwb-explorer file.nwb --output structure.json

# Combined: output + inspector
nwb-explorer file.nwb --output analysis.json --inspect
```

### Interface Specifications

#### Interactive Mode Features
- **Navigation**: Arrow keys to navigate tree, Enter to expand/collapse
- **Selection**: Click or navigate to show object details in right panel
- **Inspector Button**: 'I' key to run nwbinspector on current file
- **Output Button**: 'O' key to export current view to JSON
- **Problem Highlighting**: Visual indicators (❌⚠️💡) for objects with issues

#### Object Tree Structure
- **Start Collapsed**: All containers collapsed by default for clean initial view
- **Hierarchical Display**: Mirror PyNWB's object hierarchy (but independently built)
- **Expandable Nodes**: Follow _repr_html_ content patterns but with custom rendering
- **Problem Indicators**: Visual markers for objects with validation issues

#### Attributes Panel
- **Object Information**: Type, class, basic metadata
- **Fields Listing**: Available fields/attributes (no data preview)
- **Problem Details**: When object is selected and inspector has run
- **Navigation Path**: Full path to current object

### Structure Extraction Strategy

#### Inspired by _repr_html_ but Independent
```python
class NWBObjectInspector:
    """Extract displayable information from PyNWB objects"""
    
    def extract_object_info(self, obj):
        """Extract info similar to what _repr_html_ shows but independently"""
        return {
            'name': self._get_object_name(obj),
            'type': self._get_object_type(obj), 
            'class': obj.__class__.__name__,
            'fields': self._extract_fields(obj),
            'attributes': self._extract_attributes(obj),
            'path': self._get_object_path(obj)
        }
    
    def _extract_fields(self, obj):
        """Extract field information (similar to _repr_html_ field extraction)"""
        # Look at obj.fields if available
        # Extract nested containers
        # Build independent representation
```

#### JSON Extraction Mode
```python
class NWBJSONExtractor:
    """Extract NWB structure to JSON for memory-efficient navigation"""
    
    def extract_to_json(self, file_path):
        """One-time extraction to JSON, then close file"""
        with NWBHDF5IO(file_path, mode='r') as io:
            nwbfile = io.read()
            structure = self._build_json_structure(nwbfile)
        # File handle closed, only JSON in memory
        return structure
    
    def _build_json_structure(self, obj):
        """Recursively build JSON representation"""
        # Extract all metadata, shapes, types
        # Resolve dynamic properties during extraction
        # Return pure JSON-serializable structure
```

### Inspector Integration

#### On-Demand Execution
- **Button Trigger**: 'I' key in TUI launches nwbinspector
- **CLI Flag**: `--inspect` runs inspector at startup
- **Results Overlay**: Problems highlighted in tree structure
- **Problem Details**: Shown in attributes panel when problematic object selected

#### Problem Visualization
```
📁 acquisition
├─❌ bad_timeseries (CRITICAL: naming violation)
├─⚠️ neural_data (WARNING: missing metadata)  
└─✅ good_timeseries (no issues)
```

### JSON Output Format

#### Structure Export
```json
{
  "file_info": {
    "path": "test.nwb",
    "nwb_version": "2.5.0",
    "file_size": "45.2MB"
  },
  "structure": {
    "acquisition": {
      "type": "NWBContainer",
      "class": "LazyDataInterface",
      "children": {
        "neural_data": {
          "type": "TimeSeries",
          "class": "TimeSeries",
          "attributes": {...}
        }
      }
    },
    "processing": {...},
    "general": {...}
  },
  "inspector_results": [
    {
      "path": "/acquisition/bad_timeseries",
      "severity": "CRITICAL", 
      "message": "TimeSeries name violates convention",
      "check_name": "check_name_slashes"
    }
  ],
  "export_timestamp": "2024-01-15T10:30:00Z"
}
```

## Key Design Decisions

### 1. Decoupled but Inspired Architecture
- **Design**: Build independent structure representation inspired by _repr_html_
- **Rationale**: Full control over display logic while leveraging proven patterns
- **Implementation**: Extract same information but render independently

### 2. Interactive-First Design
- **Default Mode**: TUI interface for rich exploration
- **Rationale**: Primary use case is debugging/exploration, not batch processing
- **Non-Interactive Access**: Available via `--output` flag for automation

### 3. On-Demand Validation
- **Design**: Inspector runs only when requested (button or CLI flag)
- **Rationale**: Avoid automatic validation overhead, user controls when needed
- **Integration**: Results overlay on existing structure, don't rebuild interface

### 4. No Data Preview
- **Scope**: Focus on structure, attributes, metadata only
- **Rationale**: Debugging typically involves structural issues, not data content
- **Performance**: Avoids loading large datasets unnecessarily

### 5. PyNWB for Loading Only
- **Implementation**: Use PyNWB for file loading and object access
- **Structure Building**: Independent extraction and tree building
- **Trade-off**: More work upfront but full control over representation
- **JSON Mode**: Extract once, then operate on JSON without PyNWB

### 6. JSON Output Format
- **Format**: Structured JSON for programmatic consumption
- **Rationale**: Machine-readable, suitable for LLM analysis, widely supported
- **Flexibility**: Can be extended with additional metadata as needed

## Success Criteria

### Primary Goals
1. **Fast Problem Identification**: User can quickly identify naming, shape, metadata issues
2. **Intuitive Navigation**: Easy to explore complex NWB file structures
3. **Validation Integration**: Seamless nwbinspector integration with visual problem indicators
4. **Structured Export**: Clean JSON output suitable for further analysis

### Performance Requirements  
- **Startup Time**: < 5 seconds for typical NWB files (< 1GB)
- **Navigation Responsiveness**: Immediate response to user input
- **Inspector Integration**: Results displayed within 10 seconds for typical files

### User Experience
- **Learning Curve**: Intuitive for users familiar with file explorers
- **Problem Visibility**: Clear visual indicators for validation issues
- **Export Accessibility**: Easy access to structured output from both CLI and TUI