# 🖨️ POS Direct Print

> **Impression directe des tickets Point de Vente Odoo sur imprimante USB/CUPS, rapide et sans serveur intermédiaire !**

---
## ✨ Fonctionnalités

- ⚡ **Impression instantanée** des tickets POS sur imprimante locale (USB/CUPS)
- 🧾 **Génération du ticket** au format ESC/POS côté Odoo
- 🔗 **API HTTP/WebSocket** pour récupération et impression par un agent local
- 🎛️ **Configuration avancée** : largeur, encodage, logo, barcode, fidélité, messages personnalisés
- 🤝 **Compatible avec l’agent Python** [`print_server`](../print_server)

---
## 🚀 Installation

```bash
# 1. Copier le dossier dans vos modules Odoo (addons)
# 2. Redémarrer le serveur Odoo
# 3. Installer le module via Apps
```

---
## ⚙️ Configuration

1. **Accédez à** : Point de Vente → Configuration → Points de Vente
2. **Éditez** la configuration du POS
3. **Activez** l’option `Impression Directe USB`
4. **Paramétrez** : largeur, logo, barcode, fidélité, messages personnalisés…
5. *(Optionnel)* Saisissez l’adresse et le port de l’agent si nécessaire

---
## 🛠️ Utilisation

1. **Validez une commande** dans le POS Odoo
2. Le ticket est généré et envoyé à l’agent local
3. L’agent récupère le ticket via l’API HTTP et l’imprime sur l’imprimante USB/CUPS

---
## 📦 Dépendances

- Odoo : module `point_of_sale`
- Agent d’impression local [`print_server`](../print_server) installé sur le poste de travail

---
## 🆘 Dépannage

- Vérifiez que l’agent d’impression est **lancé** et **connecté** à Odoo
- Vérifiez que l’imprimante est **installée** et **accessible**
- Consultez les **logs** en cas de problème

---
## 🔒 Sécurité

- Les communications entre Odoo et l’agent passent par **HTTP/WebSocket**
- Configurez les **ports** et l’**IP** selon votre réseau

---
## 👤 Auteur

**Sarobidy**