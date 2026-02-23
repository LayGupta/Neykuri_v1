import h5py
import json

filename = "densenet121.h5"

def flatten_dtype(obj):
    # If it's a dictionary, check if it's the annoying DTypePolicy
    if isinstance(obj, dict):
        if obj.get('class_name') == 'DTypePolicy' and 'config' in obj:
            # Extract just the string (e.g., 'float32')
            return obj['config'].get('name', 'float32')
        # Otherwise, keep digging through the dictionary
        for k, v in obj.items():
            obj[k] = flatten_dtype(v)
    # If it's a list, dig through the items
    elif isinstance(obj, list):
        for i in range(len(obj)):
            obj[i] = flatten_dtype(obj[i])
    return obj

print("Opening model...")
with h5py.File(filename, 'r+') as f:
    model_config = f.attrs.get('model_config')
    
    if model_config is not None:
        # 1. Read the data
        is_bytes = isinstance(model_config, bytes)
        config_str = model_config.decode('utf-8') if is_bytes else model_config
        
        # 2. Parse it as JSON and clean it
        config_dict = json.loads(config_str)
        cleaned_dict = flatten_dtype(config_dict)
        
        # 3. Save it back as a string
        fixed_str = json.dumps(cleaned_dict)
        
        if is_bytes:
            f.attrs['model_config'] = fixed_str.encode('utf-8')
        else:
            f.attrs['model_config'] = fixed_str
            
        print("✅ DTypePolicy fixed! Model architecture is perfectly downgraded.")
    else:
        print("Could not find model_config.")