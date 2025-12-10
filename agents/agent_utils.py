"""
Agent Utilities

Shared utility functions for all agents to ensure consistent behavior
and reduce code duplication.
"""

import json
import ast
from typing import Any, Dict, List, Optional, Union


def parse_parameter(
    value: Any,
    expected_type: type,
    default: Any = None,
    param_name: str = "parameter"
) -> Any:
    """
    Parse a parameter that might be a string representation of a complex type.
    
    Handles parameters that come from JSON/API calls where complex types
    (lists, dicts) might be serialized as strings.
    
    Args:
        value: The parameter value to parse
        expected_type: The expected Python type (list, dict, etc.)
        default: Default value if parsing fails
        param_name: Name of the parameter (for debugging)
    
    Returns:
        Parsed value of the expected type, or default if parsing fails
    
    Examples:
        >>> parse_parameter("['col1', 'col2']", list, [])
        ['col1', 'col2']
        
        >>> parse_parameter('{"key": "value"}', dict, {})
        {'key': 'value'}
        
        >>> parse_parameter(['col1', 'col2'], list, [])
        ['col1', 'col2']
    """
    # If already the correct type, return as-is
    if isinstance(value, expected_type):
        return value
    
    # If None or empty, return default
    if value is None:
        return default if default is not None else expected_type()
    
    # If it's a string, try to parse it
    if isinstance(value, str):
        # Empty string -> default
        if not value.strip():
            return default if default is not None else expected_type()
        
        # Try JSON parsing first (handles double quotes)
        try:
            parsed = json.loads(value)
            if isinstance(parsed, expected_type):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Try Python literal_eval (handles single quotes and Python literals)
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, expected_type):
                return parsed
        except (SyntaxError, ValueError):
            pass
        
        # If expected type is list and parsing failed, treat as single item
        if expected_type == list:
            return [value]
        
        # If expected type is dict and parsing failed, return default
        if expected_type == dict:
            return default if default is not None else {}
    
    # If we can't parse it, try to convert it
    try:
        if expected_type == list:
            return list(value)
        elif expected_type == dict:
            return dict(value)
        else:
            return expected_type(value)
    except (TypeError, ValueError):
        pass
    
    # Last resort: return default
    return default if default is not None else expected_type()


def parse_parameters(
    parameters: Dict[str, Any],
    parameter_specs: Dict[str, tuple]
) -> Dict[str, Any]:
    """
    Parse multiple parameters at once using specifications.
    
    Args:
        parameters: Dictionary of parameter values
        parameter_specs: Dictionary of parameter_name -> (expected_type, default_value)
    
    Returns:
        Dictionary of parsed parameters
    
    Example:
        >>> params = {
        ...     "match_keys": "['id', 'email']",
        ...     "rules": '{"col1": "rule1"}',
        ...     "threshold": "0.5"
        ... }
        >>> specs = {
        ...     "match_keys": (list, []),
        ...     "rules": (dict, {}),
        ...     "threshold": (float, 0.5)
        ... }
        >>> parse_parameters(params, specs)
        {'match_keys': ['id', 'email'], 'rules': {'col1': 'rule1'}, 'threshold': 0.5}
    """
    parsed = {}
    
    for param_name, (expected_type, default) in parameter_specs.items():
        value = parameters.get(param_name, default)
        parsed[param_name] = parse_parameter(value, expected_type, default, param_name)
    
    return parsed


def safe_get_list(parameters: Dict[str, Any], key: str, default: List = None) -> List:
    """
    Safely get a list parameter, parsing from string if needed.
    
    Args:
        parameters: Parameters dictionary
        key: Parameter key
        default: Default value if not found or parsing fails
    
    Returns:
        List value
    """
    if default is None:
        default = []
    return parse_parameter(parameters.get(key, default), list, default, key)


def safe_get_dict(parameters: Dict[str, Any], key: str, default: Dict = None) -> Dict:
    """
    Safely get a dict parameter, parsing from string if needed.
    
    Args:
        parameters: Parameters dictionary
        key: Parameter key
        default: Default value if not found or parsing fails
    
    Returns:
        Dict value
    """
    if default is None:
        default = {}
    return parse_parameter(parameters.get(key, default), dict, default, key)


def validate_required_parameters(
    parameters: Dict[str, Any],
    required: List[str]
) -> Optional[str]:
    """
    Validate that required parameters are present.
    
    Args:
        parameters: Parameters dictionary
        required: List of required parameter names
    
    Returns:
        Error message if validation fails, None if all required params present
    """
    missing = [param for param in required if param not in parameters or parameters[param] is None]
    
    if missing:
        return f"Missing required parameters: {', '.join(missing)}"
    
    return None


def normalize_column_names(
    columns: List[str],
    available_columns: List[str],
    case_sensitive: bool = False
) -> List[str]:
    """
    Normalize column names to match available columns.
    
    Handles case mismatches and whitespace differences.
    
    Args:
        columns: Column names to normalize
        available_columns: Available columns in the dataset
        case_sensitive: Whether to match case-sensitively
    
    Returns:
        List of normalized column names that exist in available_columns
    """
    if case_sensitive:
        col_map = {col: col for col in available_columns}
    else:
        col_map = {col.strip().lower(): col for col in available_columns}
    
    normalized = []
    for col in columns:
        if case_sensitive:
            if col in col_map:
                normalized.append(col_map[col])
        else:
            col_clean = col.strip().lower()
            if col_clean in col_map:
                normalized.append(col_map[col_clean])
    
    return normalized
