import sys
import os

# Asegurar que la carpeta API esté en sys.path
api_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "API")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from traductor_srt_srt import traducir_srt

if __name__ == "__main__":
    traducir_srt()
