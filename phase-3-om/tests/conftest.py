import sys
from pathlib import Path

# Ensure phase3-attribution root is on sys.path
package_dir = Path(__file__).resolve().parent.parent
if str(package_dir) not in sys.path:
    sys.path.insert(0, str(package_dir))
