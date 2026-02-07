/** @odoo-module */

import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { patch } from "@web/core/utils/patch";

patch(Navbar.prototype, {
  async onReprintReceipt() {
    console.log("🖨️ Réimpression du ticket...");

    try {
      // Connexion au serveur d'impression local
      const ws = new WebSocket("ws://localhost:8765");

      ws.onopen = () => {
        const configId = this.pos.config.id;

        // Envoyer la demande de réimpression
        const message = {
          type: "print",
          order_name: "last",
          config_id: configId,
        };

        ws.send(JSON.stringify(message));
        console.log("📤 Demande envoyée:", message);

        // Fermer la connexion après envoi
        ws.close();
      };

      ws.onerror = (error) => {
        console.error("❌ Erreur WebSocket:", error);
        this.pos.showTempScreen("ErrorPopup", {
          title: "Erreur d'impression",
          body: "Impossible de se connecter au serveur d'impression local. Vérifiez que l'agent d'impression est démarré.",
        });
      };

      ws.onclose = () => {
        console.log("🔌 Connexion fermée");
      };
    } catch (error) {
      console.error("❌ Erreur lors de la réimpression:", error);
      this.pos.showTempScreen("ErrorPopup", {
        title: "Erreur",
        body: "Une erreur est survenue lors de la réimpression.",
      });
    }
  },
});
