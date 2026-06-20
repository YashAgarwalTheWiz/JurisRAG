from datasets import load_dataset

ds = load_dataset("Exploration-Lab/IL-TUR", "cjpe")
print(ds)
print(ds['single_train'][0])