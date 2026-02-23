import h5py

print("Scanning the model's brain...")
with h5py.File("densenet121.h5", "r") as f:
    weights = f['model_weights']
    
    print("\n--- THE LAST 10 LAYERS ---")
    layer_names = list(weights.keys())
    
    for name in layer_names[-10:]:
        print(f"Layer: {name}")
        # If it's a dense layer, print its size so we can copy it!
        if 'dense' in name.lower() and name in weights:
            try:
                # Keras weight structure
                weight_group = weights[name][name] 
                for param_name in weight_group.keys():
                    print(f"  -> {param_name}: {weight_group[param_name].shape}")
            except:
                pass