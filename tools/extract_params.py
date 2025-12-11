import json
import os

def extract_params():
    tool_files = [
        "clean_my_data_tool.json",
        "master_my_data_tool.json",
        "profile_my_data_tool.json"
    ]
    
    all_params = []

    for filename in tool_files:
        file_path = os.path.join(os.path.dirname(__file__), filename)
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        tool_name = data['tool']['name']
        
        agents = data.get('agents', {})
        for agent_id, agent_data in agents.items():
            agent_name = agent_data['name']
            
            parameters = agent_data.get('parameters', {})
            for param_name, param_data in parameters.items():
                is_show = param_data.get('show', False)
                is_required = param_data.get('required', False)
                
                if is_show or is_required:
                    # Create a copy of param_data to avoid modifying the original
                    param_entry = param_data.copy()
                    # Add metadata
                    param_entry['name'] = param_name
                    param_entry['agent'] = agent_name
                    param_entry['tool'] = tool_name
                    all_params.append(param_entry)

    # Sort by type
    # We use a tuple for sorting to have a stable sort order (type, then name)
    all_params.sort(key=lambda x: (x.get('type', 'z_unknown'), x.get('name', '')))

    output_path = os.path.join(os.path.dirname(__file__), 'temp.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_params, f, indent=2)
    
    print(f"Extraction complete. Saved {len(all_params)} parameters to {output_path}")

if __name__ == "__main__":
    extract_params()
