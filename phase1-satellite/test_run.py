import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from train import train_model

print("Starting test run of train_model...")
try:
    train_model(epochs=1, batch_size=4, synthetic=True)
    print("train_model completed successfully!")
except Exception as e:
    import traceback
    print(f"Caught exception: {e}")
    traceback.print_exc()
