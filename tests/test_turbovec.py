from turbovec import IdMapIndex
import numpy as np

index = IdMapIndex(dim=8)
vecs = np.zeros((2, 8), dtype=np.float32)

print("1. Testing with int32...")
try:
    index.add_with_ids(vecs, np.arange(2, dtype=np.int32))
    print("Success: int32")
except Exception as e:
    print("Error:", e)

print("2. Testing with int64...")
try:
    index.add_with_ids(vecs, np.arange(2, dtype=np.int64))
    print("Success: int64")
except Exception as e:
    print("Error:", e)
    
print("3. Testing add() instead of add_with_ids...")
try:
    index.add(vecs)
    print("Success: add()")
except Exception as e:
    print("Error:", e)
