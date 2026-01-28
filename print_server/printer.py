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
            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, suffix=".bin"
            ) as f:
                # Encoder le texte en bytes
                # Gérer les caractères spéciaux ESC/POS qui sont déjà des bytes ou strings
                data = self._encode_content(text)
                f.write(data)
                f.flush()

                result = subprocess.run(
                    ["lp", "-d", self.printer_name, "-o", "raw", f.name],
                    check=True,
                    capture_output=True,
                    text=True,
                )

                return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Erreur d'impression: {e}")
            return False
        except Exception as e:
            print(f"✗ Erreur: {e}")
            return False

    def _encode_content(self, content):
        """
        Encode le contenu pour l'imprimante en préservant les commandes ESC/POS
        """
        result = bytearray()

        for char in content:
            if isinstance(char, bytes):
                result.extend(char)
            else:
                try:
                    # Essayer d'encoder avec l'encodage de l'imprimante
                    result.extend(char.encode(self.encoding, errors="replace"))
                except (UnicodeEncodeError, AttributeError):
                    # Caractère brut
                    if isinstance(char, int):
                        result.append(char)
                    else:
                        result.extend(str(char).encode(self.encoding, errors="replace"))

        return bytes(result)

    def print_raw(self, data):
        """Envoie des données binaires brutes à l'imprimante"""
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, suffix=".bin"
            ) as f:
                if isinstance(data, str):
                    data = data.encode(self.encoding, errors="replace")
                f.write(data)
                f.flush()

                result = subprocess.run(
                    ["lp", "-d", self.printer_name, "-o", "raw", f.name],
                    check=True,
                    capture_output=True,
                    text=True,
                )

                return True
        except Exception as e:
            print(f"✗ Erreur d'impression raw: {e}")
            return False
