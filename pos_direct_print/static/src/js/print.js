/** @odoo-module */

//Interception de la validation de la commande pour envoyer les données à l'imprimante via WebSocket

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

// Configuration du serveur d'impression
const CONFIG = {
    HTTP_PORT: 8766,      // Port de l'API HTTP (détection serveur)
    WS_PORT: 8765,        // Port WebSocket
    TIMEOUT: 2000,        // Timeout en ms
};

// Cache pour l'URL du serveur (évite de re-détecter à chaque impression)
let cachedServerUrl = null;

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        await super.validateOrder(isForceValidate);

        const order = this.pos.get_order();
        if (!order) return;

        this._printReceipt(order.name);
    },

    /**
     * Découvre le serveur d'impression via l'API HTTP
     * @returns {Promise<string>} L'URL WebSocket du serveur
     */
    async _discoverPrintServer() {
        // Utiliser le cache si disponible
        if (cachedServerUrl) {
            return cachedServerUrl;
        }

        const ipsToTry = [
            "localhost",
            "127.0.0.1",
            window.location.hostname
        ];

        for (const ip of ipsToTry) {
            try {
                const response = await Promise.race([
                    fetch(`http://${ip}:${CONFIG.HTTP_PORT}/info`),
                    new Promise((_, reject) => 
                        setTimeout(() => reject(new Error("Timeout")), CONFIG.TIMEOUT)
                    )
                ]);

                if (response.ok) {
                    const info = await response.json();
                    cachedServerUrl = info.websocket_url;
                    console.log("✓ Serveur d'impression trouvé:", cachedServerUrl);
                    return cachedServerUrl;
                }
            } catch (e) {
                // Continuer avec la prochaine IP
            }
        }

        // Fallback si aucun serveur trouvé
        // const fallbackUrl = `ws://${CONFIG.FALLBACK_IP}:${CONFIG.WS_PORT}`;
        // console.warn("⚠ Serveur non détecté, utilisation de:", fallbackUrl);
        // return fallbackUrl;
    },

    /**
     * Envoie une demande d'impression au serveur
     * @param {string} orderName - Nom de la commande à imprimer
     */
    async _printReceipt(orderName) {
        try {
            const wsUrl = await this._discoverPrintServer();
            const ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                const payload = { type: "print", order_name: orderName };
                ws.send(JSON.stringify(payload));
                ws.close();
                console.log("✓ Impression demandée:", orderName);
            };

            ws.onerror = (error) => {
                console.error("✗ Erreur WebSocket:", error);
                // Invalider le cache pour re-détecter au prochain essai
                cachedServerUrl = null;
            };
        } catch (error) {
            console.error("✗ Erreur d'impression:", error);
            cachedServerUrl = null;
        }
    }
});
