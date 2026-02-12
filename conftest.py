import sys
from pathlib import Path

# Add the root directory to the path so pytest can find the 'awm' module
sys.path.insert(0, str(Path(__file__).parent))
