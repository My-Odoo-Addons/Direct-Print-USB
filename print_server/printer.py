# SERVICE D'IMPRESSION MULTIPLATEFORME

import subprocess
import tempfile
import os
import platform
from .config import ENCODING


class Printer:
    """Gère l'impression via CUPS (Linux) ou impression directe (Windows)"""

    def __init__(self, encoding = ENCODING):
        """
        Initialise l'imprimante.
        
        Args:
            encoding: Encodage des caractères (cp437 par défaut)
        """
        self.printer_name = None
        self.encoding = encoding
        self.os_type = platform.system()

        # Tentative de détection automatique de l'imprimante par défaut
        try:
            detected = self.detect_printer()
            if detected:
                print(f"ℹ️  Imprimante détectée automatiquement: {detected}")
                self.printer_name = detected
        except Exception:
            pass

        # Vérifier la disponibilité de l'imprimante au démarrage
        self._check_printer_available()

    def _check_printer_available(self):
        """Vérifie si l'imprimante est disponible"""
        try:
            printers = self.list_printers()
            if self.printer_name not in printers:
                print(f"⚠️  Avertissement: Imprimante '{self.printer_name}' non trouvée")
                print(f"   Imprimantes disponibles: {', '.join(printers) if printers else 'Aucune'}")
        except Exception as e:
            print(f"⚠️  Impossible de vérifier les imprimantes: {e}")

    def print_text(self, text):
        """Imprime du texte sur l'imprimante thermique (Linux/Windows)"""
        try:
            data = self._encode_content(text)
            return self._send_to_printer(data)
        except Exception as e:
            print(f"✗ Erreur print_text: {e}")
            return False

    def print_raw(self, data):
        """Envoie des données binaires brutes à l'imprimante (Linux/Windows)"""
        try:
            if isinstance(data, str):
                data = data.encode(self.encoding, errors="replace")
            return self._send_to_printer(data)
        except Exception as e:
            print(f"✗ Erreur print_raw: {e}")
            return False

    def _send_to_printer(self, data):
        """Envoie les données à l'imprimante selon l'OS"""
        if self.os_type == "Windows":
            return self._print_windows(data)
        else:
            return self._print_unix(data)

    def _print_windows(self, data):
        """Impression sur Windows - Méthodes multiples avec fallback"""
        temp_file = None
        
        try:
            # Créer un fichier temporaire
            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, suffix=".prn"
            ) as f:
                f.write(data)
                temp_file = f.name

            # Méthode 1: Essayer win32print (le plus fiable pour données brutes)
            if self._try_win32print(data):
                return True

            # Méthode 2: Copie binaire directe (pour ESC/POS)
            if self._try_copy_binary(temp_file):
                return True

            # Méthode 3: Commande print (moins fiable pour raw data)
            if self._try_print_command(temp_file):
                return True

            # Méthode 4: Tentative d'écriture directe sur port
            if self._try_direct_port(data):
                return True

            print(f"✗ Toutes les méthodes d'impression Windows ont échoué")
            return False

        except Exception as e:
            print(f"✗ Erreur impression Windows: {e}")
            return False
        finally:
            # Nettoyer le fichier temporaire
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass

    def _try_win32print(self, data):
        """Essaie d'imprimer avec win32print (méthode recommandée)"""
        try:
            import win32print
            import win32api

            hPrinter = win32print.OpenPrinter(self.printer_name)
            try:
                hJob = win32print.StartDocPrinter(hPrinter, 1, ("Raw Document", None, "RAW"))
                try:
                    win32print.StartPagePrinter(hPrinter)
                    win32print.WritePrinter(hPrinter, data)
                    win32print.EndPagePrinter(hPrinter)
                    print(f"   ✓ Impression réussie (win32print)")
                    return True
                finally:
                    win32print.EndDocPrinter(hPrinter)
            finally:
                win32print.ClosePrinter(hPrinter)
        except ImportError:
            # win32print n'est pas installé
            return False
        except Exception as e:
            print(f"   ⤷ win32print échoué: {e}")
            return False

    def _try_copy_binary(self, temp_file):
        """Essaie la copie binaire (pour données ESC/POS)"""
        try:
            # Essayer différents formats de noms d'imprimante
            printer_formats = [
                self.printer_name,
                f"\\\\localhost\\{self.printer_name}",
                f"\\\\.\\{self.printer_name}"
            ]

            for printer in printer_formats:
                try:
                    result = subprocess.run(
                        ["cmd", "/c", f"copy /b \"{temp_file}\" \"{printer}\""],
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    print(f"   ✓ Impression réussie (copy /b)")
                    return True
                except subprocess.CalledProcessError:
                    continue

            return False
        except Exception as e:
            print(f"   ⤷ copy /b échoué: {e}")
            return False

    def _try_print_command(self, temp_file):
        """Essaie la commande print (moins fiable pour raw)"""
        try:
            result = subprocess.run(
                ["print", f"/D:{self.printer_name}", temp_file],
                check=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            print(f"   ✓ Impression réussie (print)")
            return True
        except Exception as e:
            print(f"   ⤷ print échoué: {e}")
            return False

    def _try_direct_port(self, data):
        """Essaie l'écriture directe sur le port"""
        try:
            ports = [
                f"\\\\localhost\\{self.printer_name}",
                "LPT1",
                "COM1",
                f"\\\\.\\{self.printer_name}"
            ]

            for port in ports:
                try:
                    with open(port, "wb") as printer:
                        printer.write(data)
                        print(f"   ✓ Impression réussie (port direct: {port})")
                        return True
                except (FileNotFoundError, PermissionError, OSError):
                    continue

            return False
        except Exception as e:
            print(f"   ⤷ Port direct échoué: {e}")
            return False

    def _print_unix(self, data):
        """Impression sur Linux/Unix via CUPS"""
        temp_file = None
        
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, suffix=".prn"
            ) as f:
                f.write(data)
                temp_file = f.name

            result = subprocess.run(
                ["lp", "-d", self.printer_name, "-o", "raw", temp_file],
                check=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            print(f"   ✓ Impression réussie (CUPS)")
            return True

        except FileNotFoundError:
            print(f"✗ CUPS non installé. Installer avec: sudo apt-get install cups")
            return False
        except subprocess.CalledProcessError as e:
            print(f"✗ Erreur CUPS: {e.stderr if e.stderr else e}")
            return False
        except Exception as e:
            print(f"✗ Erreur impression Unix: {e}")
            return False
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass

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
                    result.extend(char.encode(self.encoding, errors="replace"))
                except (UnicodeEncodeError, AttributeError):
                    if isinstance(char, int):
                        result.append(char)
                    else:
                        result.extend(str(char).encode(self.encoding, errors="replace"))

        return bytes(result)

    @staticmethod
    def list_printers():
        """Liste les imprimantes disponibles sur le système"""
        os_type = platform.system()
        printers = []

        try:
            if os_type == "Windows":
                # Méthode 1: Essayer avec win32print
                try:
                    import win32print
                    printers = [printer[2] for printer in win32print.EnumPrinters(2)]
                    return printers
                except ImportError:
                    pass

                # Méthode 2: WMIC (Windows)
                try:
                    result = subprocess.run(
                        ["wmic", "printer", "get", "name"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    lines = result.stdout.strip().split('\n')[1:]
                    printers = [line.strip() for line in lines if line.strip()]
                    return printers
                except:
                    pass

                # Méthode 3: PowerShell fallback
                try:
                    result = subprocess.run(
                        ["powershell", "-Command", "Get-Printer | Select-Object -ExpandProperty Name"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    printers = [line.strip() for line in result.stdout.split('\n') if line.strip()]
                    return printers
                except:
                    pass

            else:
                # Linux/Unix: utiliser lpstat
                result = subprocess.run(
                    ["lpstat", "-p"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in result.stdout.split('\n'):
                    if line.startswith('printer'):
                        printer_name = line.split()[1]
                        printers.append(printer_name)

        except Exception as e:
            print(f"⚠️  Erreur lors de la récupération des imprimantes: {e}")

        return printers

    @staticmethod
    def detect_printer():
        """
        Tente de détecter le nom d'imprimante par défaut sur Windows ou Linux.
        Retourne le nom de l'imprimante détectée, ou `None` si aucune trouvée.
        """
        os_type = platform.system()

        try:
            if os_type == "Windows":
                # Méthode 1: win32print si disponible
                try:
                    import win32print
                    name = win32print.GetDefaultPrinter()
                    if name:
                        return name
                except Exception:
                    pass

                # Méthode 2: PowerShell
                try:
                    result = subprocess.run(
                        ["powershell", "-NoProfile", "-Command",
                         "(Get-Printer | Where-Object {$_.Default -eq $true}).Name"],
                        capture_output=True, text=True, timeout=5
                    )
                    name = result.stdout.strip()
                    if name:
                        return name.splitlines()[0].strip()
                except Exception:
                    pass

                # Méthode 3: wmic
                try:
                    result = subprocess.run(
                        ["wmic", "printer", "where", "Default=True", "get", "Name"],
                        capture_output=True, text=True, timeout=5
                    )
                    lines = [l.strip() for l in result.stdout.splitlines() if l.strip() and l.strip().lower() != 'name']
                    if lines:
                        return lines[0]
                except Exception:
                    pass

                # Fallback: première imprimante listée
                printers = Printer.list_printers()
                return printers[0] if printers else None

            else:
                # Linux/Unix: vérifier variables d'environnement
                env_name = os.environ.get('PRINTER') or os.environ.get('LPDEST')
                if env_name:
                    return env_name

                # Méthode 1: lpstat -d
                try:
                    result = subprocess.run(["lpstat", "-d"], capture_output=True, text=True, timeout=3)
                    for line in result.stdout.splitlines():
                        if 'system default destination' in line:
                            parts = line.split(':', 1)
                            if len(parts) > 1:
                                return parts[1].strip()
                except Exception:
                    pass

                # Méthode 2: lpstat -p (prendre la première imprimante)
                try:
                    result = subprocess.run(["lpstat", "-p"], capture_output=True, text=True, timeout=3)
                    for line in result.stdout.splitlines():
                        if line.startswith('printer'):
                            parts = line.split()
                            if len(parts) >= 2:
                                return parts[1]
                except Exception:
                    pass

                # Fallback: première imprimante listée
                printers = Printer.list_printers()
                return printers[0] if printers else None

        except Exception:
            return None

    # def test_print(self):
    #     """Imprime un ticket de test pour vérifier la configuration"""
    #     test_data = b"\x1B\x40"  # ESC @ - Initialiser
    #     test_data += b"\x1B\x61\x01"  # ESC a 1 - Centrer
    #     test_data += b"TEST D'IMPRESSION\n"
    #     test_data += b"==================\n"
    #     test_data += f"Imprimante: {self.printer_name}\n".encode(self.encoding)
    #     test_data += f"OS: {self.os_type}\n".encode(self.encoding)
    #     test_data += b"==================\n\n\n"
    #     test_data += b"\x1D\x56\x00"  # GS V 0 - Couper le papier

    #     print(f"🧪 Test d'impression sur {self.printer_name}...")
    #     return self.print_raw(test_data)


# # Test autonome
# if __name__ == "__main__":
#     print("=" * 50)
#     print("TEST DU MODULE PRINTER")
#     print("=" * 50)
    
#     # Lister les imprimantes
#     print("\n📋 Imprimantes disponibles:")
#     printers = Printer.list_printers()
#     if printers:
#         for i, printer in enumerate(printers, 1):
#             print(f"   {i}. {printer}")
#     else:
#         print("   Aucune imprimante trouvée")
    
#     # Test d'impression
#     if printers:
#         printer_name = printers[0]  # Utiliser la première imprimante
#         print(f"\n🖨️  Test avec: {printer_name}")
        
#         printer = Printer(printer_name)
#         if printer.test_print():
#             print("✓ Test réussi!")
#         else:
#             print("✗ Test échoué")
    
#     print("\n" + "=" * 50)