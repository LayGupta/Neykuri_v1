import h5py

with h5py.File("densenet121.h5", "r") as f:
    print("Extracting the hidden layer size...")
    
    def print_shapes(name, obj):
        if isinstance(obj, h5py.Dataset):
            print(f" -> {obj.shape}")
            
    # Look inside the missing 'dense' layer
    f['model_weights']['dense'].visititems(print_shapes)