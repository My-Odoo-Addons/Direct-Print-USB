/** @odoo-module */

/**
 * Module d'impression directe POS
 * Intercepte la validation de commande pour envoyer à l'imprimante via WebSocket
 */

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

// Valeurs par défaut (utilisées si config Odoo non disponible)
const DEFAULT_CONFIG = {
    HTTP_PORT: 8766,
    WS_PORT: 8765,
    TIMEOUT: 3000,
};

// Cache pour l'URL du serveur
let cachedServerUrl = null;

patch(PaymentScreen.prototype, {
    
    /**
     * Récupère la configuration depuis pos.config
     */
    _getDirectPrintConfig() {
        const config = this.pos.config;
        return {
            enabled: config.use_direct_print || false,
            host: config.direct_print_host ,//|| "localhost",
            httpPort: DEFAULT_CONFIG.HTTP_PORT,
            wsPort: DEFAULT_CONFIG.WS_PORT,
            timeout: DEFAULT_CONFIG.TIMEOUT,
        };
    },

    async validateOrder(isForceValidate) {
        await super.validateOrder(isForceValidate);

        const order = this.pos.get_order();
        if (!order) return;

        // Vérifier si l'impression directe est activée
        const printConfig = this._getDirectPrintConfig();
        if (!printConfig.enabled) {
            console.log("ℹ Impression directe désactivée dans la config POS");
            return;
        }

        // Attendre que les données soient enregistrées dans Odoo
        await new Promise(resolve => setTimeout(resolve, 500));
        
        this._printReceipt(order.name, printConfig);
    },

    /**
     * Découvre le serveur d'impression via l'API HTTP
     */
    async _discoverPrintServer(config) {
        if (cachedServerUrl) {
            return cachedServerUrl;
        }

        const ipsToTry = [
            "localhost",
            "127.0.0.1",
        ].filter((v, i, a) => a.indexOf(v) === i); // Dédupliquer

        for (const ip of ipsToTry) {
            try {
                const response = await Promise.race([
                    fetch(`http://${ip}:${config.httpPort}/info`),
                    new Promise((_, reject) => 
                        setTimeout(() => reject(new Error("Timeout")), config.timeout)
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

        // Fallback: construire l'URL depuis la config
        const fallbackUrl = `ws://${config.host}:${config.wsPort}`;
        console.warn("⚠ Serveur non détecté via /info, fallback:", fallbackUrl);
        return fallbackUrl;
    },

    /**
     * Envoie une demande d'impression au serveur
     */
    async _printReceipt(orderName, config) {
        try {
            const wsUrl = await this._discoverPrintServer(config);
            const ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                const payload = { type: "print", order_name: orderName };
                ws.send(JSON.stringify(payload));
                console.log("✓ Impression demandée:", orderName);
                // Fermer après un court délai pour s'assurer que le message est envoyé
                setTimeout(() => ws.close(), 100);
            };

            ws.onerror = (error) => {
                console.error("✗ Erreur WebSocket:", error);
                cachedServerUrl = null;
            };

            ws.onclose = () => {
                // Connexion fermée normalement
            };
        } catch (error) {
            console.error("✗ Erreur d'impression:", error);
            cachedServerUrl = null;
        }
    }
});
