
# SERVICE D'IMPRESSION


import subprocess
import tempfile
from .config import PRINTER_CONFIG


class Printer:
    """Gère l'impression via CUPS"""
    
    def __init__(self):
        self.printer_name = PRINTER_CONFIG["name"]
        self.encoding = PRINTER_CONFIG["encoding"]
    
    def print_text(self, text):
        """Imprime du texte sur l'imprimante thermique"""
        try:
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as f:
                f.write(text.encode(self.encoding, errors='replace'))
                f.flush()
                
                result = subprocess.run([
                    "lp",
                    "-d", self.printer_name,
                    "-o", "raw",
                    f.name
                ], check=True, capture_output=True, text=True)
                
                return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Erreur d'impression: {e}")
            return False
        except Exception as e:
            print(f"✗ Erreur: {e}")
            return False
