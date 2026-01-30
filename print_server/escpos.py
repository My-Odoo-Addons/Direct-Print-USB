# COMMANDES ESC/POS POUR IMPRIMANTES THERMIQUES

# Caractères de contrôle
ESC = "\x1b"
GS = "\x1d"
FS = "\x1c"

# Styles de texte
BOLD_ON = ESC + "E\x01"
BOLD_OFF = ESC + "E\x00"
UNDERLINE_ON = ESC + "-\x01"
UNDERLINE_OFF = ESC + "-\x00"

# Alignement
ALIGN_LEFT = ESC + "a\x00"
ALIGN_CENTER = ESC + "a\x01"
ALIGN_RIGHT = ESC + "a\x02"

# Taille du texte
SIZE_NORMAL = ESC + "!\x00"
SIZE_DOUBLE_HEIGHT = ESC + "!\x10"
SIZE_DOUBLE_WIDTH = ESC + "!\x20"
SIZE_DOUBLE = ESC + "!\x30"

# Actions
CUT_PAPER = GS + "V\x00"
CUT_PAPER_PARTIAL = GS + "V\x01"
FEED_LINES = lambda n: ESC + f"d{chr(n)}"

# Initialisation
INIT_PRINTER = ESC + "@"

# CODES-BARRES ESC/POS


def barcode_height(height=80):
    """Définit la hauteur du code-barres (1-255 pixels)"""
    return GS + "h" + chr(min(255, max(1, height)))


def barcode_width(width=2):
    """Définit la largeur du code-barres (2-6)"""
    return GS + "w" + chr(min(6, max(2, width)))


def barcode_text_position(position=2):
    """Position du texte: 0=none, 1=above, 2=below, 3=both"""
    return GS + "H" + chr(position)


def barcode_font(font=0):
    """Police du texte: 0=Font A, 1=Font B"""
    return GS + "f" + chr(font)


def barcode_ean13(data):
    """
    Génère un code-barres EAN-13
    data: 12 ou 13 chiffres (checksum auto-calculé si 12)
    """
    # Prendre seulement les chiffres
    digits = "".join(filter(str.isdigit, str(data)))[:12]
    digits = digits.zfill(12)

    # Configuration + impression - TAILLE AUGMENTÉE
    return (
        barcode_height(100)  # Augmenté de 80 à 100
        + barcode_width(3)   # Augmenté de 2 à 3
        + barcode_text_position(2)
        + barcode_font(0)
        + GS
        + "k"
        + "\x02"  # Type EAN-13 (format A)
        + digits
        + "\x00"  # Données + NUL terminator
    )


def barcode_code39(data):
    """
    Génère un code-barres Code 39
    data: chaîne alphanumérique (jusqu'à 32 caractères)
    """
    # Limiter à 32 caractères maximum et convertir en majuscules
    data_str = str(data).upper()[:32]

    # Configuration + impression
    return (
        barcode_height(80)
        + barcode_width(2)
        + barcode_text_position(2)
        + barcode_font(0)
        + GS
        + "k"
        + "\x04"  # Type Code 39
        + data_str
        + "\x00"  # NUL terminator
    )

# IMPRESSION D'IMAGES / LOGO


def print_raster_image(image_data, width_bytes, height):
    """
    Imprime une image raster
    image_data: bytes de l'image (1 bit par pixel)
    width_bytes: largeur en octets
    height: hauteur en pixels
    """
    # GS v 0 m xL xH yL yH d1...dk
    xL = width_bytes % 256
    xH = width_bytes // 256
    yL = height % 256
    yH = height // 256

    # Tout doit être en bytes
    header = bytes([0x1D, 0x76, 0x30, 0x00, xL, xH, yL, yH])
    return header + image_data


def convert_image_to_raster(image_path, max_width=384):
    """
    Convertit une image PNG en données raster pour imprimante thermique
    Retourne (data_bytes, width_bytes, height) ou None si erreur
    """
    try:
        from PIL import Image

        # Charger l'image
        img = Image.open(image_path)

        # Convertir en niveaux de gris puis en noir/blanc
        img = img.convert("L")  # Grayscale

        # Redimensionner si nécessaire
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)

        # Convertir en noir et blanc (1 bit)
        img = img.point(lambda x: 0 if x < 128 else 255, "1")

        width = img.width
        height = img.height

        # Largeur doit être multiple de 8
        width_bytes = (width + 7) // 8

        # Convertir en bytes
        pixels = list(img.getdata())
        data = bytearray()

        for y in range(height):
            for x_byte in range(width_bytes):
                byte = 0
                for bit in range(8):
                    x = x_byte * 8 + bit
                    if x < width:
                        pixel_index = y * width + x
                        if pixel_index < len(pixels) and pixels[pixel_index] == 0:
                            byte |= 1 << (7 - bit)
                data.append(byte)

        return bytes(data), width_bytes, height

    except ImportError:
        print("PIL non installé, logo non supporté")
        return None
    except FileNotFoundError:
        print(f"Image non trouvée: {image_path}")
        return None
    except Exception as e:
        print(f"Erreur conversion image: {e}")
        return None


def print_logo(image_path, max_width=384):
    """
    Retourne les commandes ESC/POS pour imprimer un logo
    """
    result = convert_image_to_raster(image_path, max_width)
    if result:
        data, width_bytes, height = result
        return print_raster_image(data, width_bytes, height)
    return ""
