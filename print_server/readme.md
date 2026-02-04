# 🖨️ Agent d'Impression POS - Interface Graphique

Interface graphique moderne et multiplateforme pour l'agent d'impression POS.


## ✨ Fonctionnalités

- 🎨 **Interface moderne et intuitive**
- 🖥️ **Multiplateforme** : Windows et Linux
- 🔄 **Détection automatique** des imprimantes
- 🧪 **Test d'impression** intégré
- ⚙️ **Configuration facile** (URL Odoo, imprimante, ports)
- 🔌 **WebSocket + HTTP** pour communication avec Odoo

## 📋 Prérequis

### Windows
```bash
# Python 3.8 ou supérieur
python --version

# Modules Python requis (voir requirements.txt)
```

### Linux 
```bash
# Python 3.8 ou supérieur
python3 --version

# CUPS pour la gestion des imprimantes
sudo apt-get install cups cups-client # Dérivé de Debian (Ubuntu, Linux Mint, ...)
sudo dnf install cups cups-client # Dérivé de RedHat (Fedora, PopOS, ...)
# Bibliothèques système
sudo apt-get install python3-tk # Debian
sudo dnf install python3-tkinter # Fedora
```

## 🚀 Installation

### Installer les dépendances Python

```bash
# Windows
pip install -r requirements.txt

# Linux
pip3 install -r requirements.txt --break-system-packages
```

**Contenu de requirements.txt :**
```
websockets>=12.0
aiohttp>=3.9.0
pywin32>=306 ; platform_system == "Windows"
```


## 🎮 Utilisation

### Lancer l'interface graphique

**Windows :**
```bash
python gui.py
```

**Linux :**
```bash
python3 gui.py
```

### Étapes d'utilisation

1. **Configuration initiale :**
   - Entrez l'URL de votre serveur Odoo (ex: `http://192.168.1.100:8069`)
   - Sélectionnez votre imprimante dans la liste déroulante

2. **Test d'impression :**
   - Cliquez sur "🧪 Test d'impression" pour vérifier que l'imprimante fonctionne
   - Un ticket de test sera imprimé

3. **Démarrer l'agent :**
   - Cliquez sur "▶️ Démarrer l'Agent"
   - L'agent est maintenant en écoute des demandes d'impression depuis Odoo
   - Les informations de connexion s'affichent dans la section "ℹ️ Informations"

4. **Surveillance :**
   - Consultez les **statistiques** en temps réel
   - Suivez le **journal des événements** pour voir les impressions
   - Les logs sont colorés selon le niveau (succès en vert, erreurs en rouge)

5. **Arrêt :**
   - Cliquez sur "⏹️ Arrêter l'Agent" pour stopper le service
   - Ou fermez simplement la fenêtre


## 🔧 Configuration Odoo

Dans Odoo, configurer le module de point de vente pour utiliser l'agent :

1. **Installer le module `pos_direct_print`**

2. **Configurer l'endpoint** :
   - URL : `http://<IP_DE_L_AGENT>:8766/info`
   - L'agent expose automatiquement ses informations

3. **Dans le POS** :
   - Activer "Impression directe"
   - L'URL WebSocket sera : `ws://<IP_DE_L_AGENT>:8765`

## 📊 Structure du projet

```
pos-print-agent/
├── agent.py           # Logique principale de l'agent
├── printer.py         # Gestion multiplateforme des imprimantes
├── config.py          # Configuration
├── gui.py             # Interface graphique (nouveau)
├── __init__.py        # Module Python
├── requirements.txt   # Dépendances Python
└── README.md          # Ce fichier
```

## 🐛 Dépannage

### L'imprimante n'est pas détectée

**Windows :**
- Vérifier que l'imprimante est bien installée dans "Périphériques et imprimantes"
- Essayer d'imprimer une page de test depuis Windows
- Installer `pywin32` : `pip install pywin32`

**Linux :**
- Vérifier CUPS : `systemctl status cups`
- Lister les imprimantes : `lpstat -p`
- Vérifier les permissions : `usermod -a -G lpadmin $USER`
- Redémarrer la session

### Erreur "Module not found"

```bash
# Réinstaller les dépendances
pip install -r requirements.txt --force-reinstall

# Linux : utiliser pip3
pip3 install -r requirements.txt --break-system-packages
```

### L'agent ne se connecte pas à Odoo

- Vérifier que l'URL Odoo est correcte et accessible
- Tester l'URL dans un navigateur : `http://<url-odoo>/pos_direct_print/receipt/TEST`
- Vérifier le pare-feu (ports 8765 et 8766 doivent être ouverts)

### Erreur d'impression

- Faire un test d'impression depuis l'interface
- Vérifier les logs dans le journal des événements
- S'assurer que l'imprimante est allumée et a du papier
- Vérifier que le format des données ESC/POS est correct

## 🔒 Sécurité

- L'agent écoute sur `0.0.0.0` (toutes les interfaces)
- Assurez-vous que votre réseau est sécurisé
- Pour un usage en production, configurez un pare-feu approprié
- Utilisez HTTPS/WSS pour les connexions sur Internet

## 📝 Licence

Ce projet est fourni tel quel, à des fins éducatives et professionnelles.

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :
- Signaler des bugs
- Proposer des améliorations
- Soumettre des pull requests

## 📞 Support

Pour toute question ou problème :
1. Consulter ce README
2. Vérifier les logs dans l'interface
3. Créer une issue sur le dépôt du projet

---

**Développé avec ❤️ pour simplifier l'impression POS**