import os
import glob

print("Listing all files in directory:")
for f in os.listdir("."):
    if f.startswith("~$") or f.startswith(".~lock"):
        print(f"Found lock file: {f}")
        try:
            os.remove(f)
            print(f"Deleted {f}")
        except Exception as e:
            print(f"Could not delete {f}: {e}")
