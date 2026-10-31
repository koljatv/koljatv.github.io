"""Exit 0 when a python with PIL + numpy exists for the vignettes (used by instalar.command)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import midia
sys.exit(0 if midia.pil_python() else 1)
