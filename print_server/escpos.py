
# COMMANDES ESC/POS POUR IMPRIMANTES THERMIQUES

# Caractères de contrôle
ESC = "\x1b"
GS = "\x1d"

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
FEED_LINES = lambda n: ESC + f"d{chr(n)}"

# Initialisation
INIT_PRINTER = ESC + "@"
