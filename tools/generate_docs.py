import json
import os

def generate_markdown():
    with open('tools/temp.json', 'r') as f:
        params = json.load(f)

    # Group by Tool -> Agent
    structure = {}
    for p in params:
        tool = p['tool']
        agent = p['agent']
        if tool not in structure:
            structure[tool] = {}
        if agent not in structure[tool]:
            structure[tool][agent] = []
        structure[tool][agent].append(p)

    md_lines = ["# Agent Parameters Reference", "", "This document lists all configurable parameters for Agensium agents where the parameter is either required or exposed in the UI (`show: true`).", ""]

    # Generate Tables
    for tool, agents in structure.items():
        md_lines.append(f"## Tool: {tool}")
        for agent, agent_params in agents.items():
            md_lines.append(f"\n### Agent: {agent}")
            # Add agent description if available (hardcoding common ones or skipping)
            # For now, we'll skip the italicized description to keep it simple, or I could try to preserve it if I read the old file. 
            # But the user asked to "cover all params present in temp.json", implying the table content is the priority.
            
            md_lines.append("")
            md_lines.append("| Parameter | Type | Required | Description | Perfect Example |")
            md_lines.append("| :--- | :--- | :--- | :--- | :--- |")
            
            for p in agent_params:
                name = f"`{p['name']}`"
                type_ = f"`{p['type']}`"
                required = "**Yes**" if p.get('required') else "No"
                desc = p.get('description', '')
                example = json.dumps(p.get('example', ''))
                # Escape pipes in example if any
                example = f"`{example}`"
                
                md_lines.append(f"| {name} | {type_} | {required} | {desc} | {example} |")
        md_lines.append("")

    # Generate UI Section
    md_lines.append("# UI Implementation Notes")
    md_lines.append("")
    md_lines.append("This section outlines the UI components required for different parameter types.")
    md_lines.append("")

    # Categorize
    categories = {
        "array_object": [],
        "array_string": [],
        "object": [],
        "string_allowed": [],
        "string_column": [],
        "string_other": []
    }

    seen_params = set() # To avoid duplicates in the summary list if multiple agents use same param name/type

    for p in params:
        key = f"{p['name']}_{p['type']}"
        # We want to list unique parameter definitions for UI purposes
        
        if p['type'] == 'array':
            if p.get('items') == 'object':
                categories['array_object'].append(p['name'])
            elif p.get('items') == 'string':
                categories['array_string'].append(p['name'])
        elif p['type'] == 'object':
            categories['object'].append(p['name'])
        elif p['type'] == 'string':
            if 'allowed' in p:
                categories['string_allowed'].append(p['name'])
            elif 'column' in p['name'].lower():
                categories['string_column'].append(p['name'])
            else:
                categories['string_other'].append(p['name'])

    # Deduplicate lists
    for k in categories:
        categories[k] = sorted(list(set(categories[k])))

    # 1. Array of Objects
    md_lines.append("## Type: Array | Items: Object")
    md_lines.append("**Status:** `Yet to Decide`")
    md_lines.append("**Comment:** Complex nested structures. Need to design a proper UI for these cases.")
    md_lines.append("**Parameters:**")
    for name in categories['array_object']:
        md_lines.append(f"- `{name}`")
    md_lines.append("")

    # 2. Array of Strings (Columns)
    md_lines.append("## Type: Array | Items: String")
    md_lines.append("**Status:** `Multi-Select Column Dropdown`")
    md_lines.append("**Comment:** These parameters accept a list of columns. The UI should show all columns from the file for the user to select.")
    md_lines.append("**Parameters:**")
    for name in categories['array_string']:
        md_lines.append(f"- `{name}`")
    md_lines.append("")

    # 3. Object
    md_lines.append("## Type: Object")
    md_lines.append("**Status:** `Yet to Decide`")
    md_lines.append("**Comment:** Complex mappings or configurations (dictionaries).")
    md_lines.append("**Parameters:**")
    for name in categories['object']:
        md_lines.append(f"- `{name}`")
    md_lines.append("")

    # 4. String (Allowed)
    md_lines.append("## Type: String | Allowed Values")
    md_lines.append("**Status:** `Dropdown`")
    md_lines.append("**Comment:** Already showing dropdown for parameters with allowed values.")
    md_lines.append("**Parameters:**")
    for name in categories['string_allowed']:
        md_lines.append(f"- `{name}`")
    md_lines.append("")

    # 5. String (Column)
    md_lines.append("## Type: String | Column Reference")
    md_lines.append("**Status:** `Single-Select Column Dropdown`")
    md_lines.append("**Comment:** Parameter refers to a single column. Show columns which can be selected.")
    md_lines.append("**Parameters:**")
    for name in categories['string_column']:
        md_lines.append(f"- `{name}`")
    md_lines.append("")

    # 6. String (Other)
    md_lines.append("## Type: String | Free Text")
    md_lines.append("**Status:** `Text Input`")
    md_lines.append("**Comment:** Standard text input.")
    md_lines.append("**Parameters:**")
    for name in categories['string_other']:
        md_lines.append(f"- `{name}`")
    md_lines.append("")

    with open('tools/parameters_v2.md', 'w') as f:
        f.write('\n'.join(md_lines))

if __name__ == "__main__":
    generate_markdown()
