#!/usr/bin/env python3
"""
INTERFACE GRAPHIQUE POUR L'AGENT D'IMPRESSION POS
Compatible Windows et Linux
"""

import json
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import asyncio
import os
from datetime import datetime
import queue

# Importer les modules de l'agent

from .agent import get_local_ip
from .printer import Printer
from .config import WEBSOCKET_CONFIG, CONFIG_FILE, CONFIG_DIR


class PrintAgentGUI:
    """Interface graphique pour l'agent d'impression POS"""

    def __init__(self, root):
        self.root = root
        self.root.title("Agent d'Impression POS")
        self.root.geometry("900x700")
        self.root.minsize(700, 500)

        # État de l'agent
        self.agent = None
        self.agent_thread = None
        self.is_running = False
        self.log_queue = queue.Queue()
        self.stats = {"total": 0, "success": 0, "errors": 0}

        # Créer l'interface
        self._create_widgets()
        self._load_config()
        self._update_status()

        # Démarrer la mise à jour des logs
        self._process_log_queue()

        # Gestion de la fermeture
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_widgets(self):
        """Crée tous les widgets de l'interface"""

        # Frame principale avec padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # === SECTION CONFIGURATION ===
        config_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="10")
        config_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        config_frame.columnconfigure(1, weight=1)

        # URL Odoo
        ttk.Label(config_frame, text="URL Odoo:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10)
        )
        # Frame pour URL
        url_frame = ttk.Frame(config_frame)
        url_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        url_frame.columnconfigure(0, weight=1)

        self.odoo_url_var = tk.StringVar()
        self.odoo_combo = ttk.Combobox(url_frame, textvariable=self.odoo_url_var)
        self.odoo_combo.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        refresh_url_btn = ttk.Button(
            url_frame, text="Rafraîchir", width=3, command=self._load_config
        )
        # Imprimante
        ttk.Label(config_frame, text="Imprimante:").grid(
            row=1, column=0, sticky=tk.W, padx=(0, 10)
        )
        printer_frame = ttk.Frame(config_frame)
        printer_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        printer_frame.columnconfigure(0, weight=1)

        self.printer_var = tk.StringVar()
        self.printer_combo = ttk.Combobox(
            printer_frame, textvariable=self.printer_var, state="readonly"
        )
        self.printer_combo.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))

        refresh_btn = ttk.Button(
            printer_frame, text="Rafraîchir", width=3, command=self._refresh_printers
        )
        refresh_btn.grid(row=0, column=1)

        # === SECTION CONTRÔLE ===
        control_frame = ttk.LabelFrame(main_frame, text="Contrôle", padding="10")
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Boutons de contrôle
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X)

        self.start_btn = ttk.Button(
            button_frame,
            text="▶️ Démarrer l'Agent",
            command=self._start_agent,
            style="success.TButton",
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_btn = ttk.Button(
            button_frame,
            text="⏹️ Arrêter l'Agent",
            command=self._stop_agent,
            state=tk.DISABLED,
            style="danger.TButton",
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))

        test_btn = ttk.Button(
            button_frame, text="Test d'impression", command=self._test_print
        )
        test_btn.pack(side=tk.LEFT)

        # Barre de statut
        self.status_var = tk.StringVar(value="⚪ Arrêté")
        status_label = ttk.Label(
            control_frame, textvariable=self.status_var, font=("", 10, "bold")
        )
        status_label.pack(pady=(10, 0))

        # === SECTION STATISTIQUES ===
        stats_frame = ttk.LabelFrame(main_frame, text="Statistiques", padding="10")
        stats_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        stats_inner = ttk.Frame(stats_frame)
        stats_inner.pack(fill=tk.X)

        # Total
        total_frame = ttk.Frame(stats_inner)
        total_frame.pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Label(total_frame, text="Total", font=("", 9)).pack()
        self.total_var = tk.StringVar(value="0")
        ttk.Label(
            total_frame, textvariable=self.total_var, font=("", 14, "bold")
        ).pack()

        # Succès
        success_frame = ttk.Frame(stats_inner)
        success_frame.pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Label(
            success_frame, text="✓ Réussis", font=("", 9), foreground="green"
        ).pack()
        self.success_var = tk.StringVar(value="0")
        ttk.Label(
            success_frame,
            textvariable=self.success_var,
            font=("", 14, "bold"),
            foreground="green",
        ).pack()

        # Erreurs
        error_frame = ttk.Frame(stats_inner)
        error_frame.pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Label(error_frame, text="✗ Erreurs", font=("", 9), foreground="red").pack()
        self.error_var = tk.StringVar(value="0")
        ttk.Label(
            error_frame,
            textvariable=self.error_var,
            font=("", 14, "bold"),
            foreground="red",
        ).pack()

        # === SECTION INFORMATIONS ===
        info_frame = ttk.LabelFrame(main_frame, text="Informations", padding="10")
        info_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        self.info_text = tk.Text(
            info_frame, height=4, wrap=tk.WORD, background="#f0f0f0", relief=tk.FLAT
        )
        self.info_text.pack(fill=tk.BOTH, expand=True)
        self.info_text.config(state=tk.DISABLED)

        # === SECTION LOGS ===
        log_frame = ttk.LabelFrame(
            main_frame, text="Journal des événements", padding="10"
        )
        log_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        main_frame.rowconfigure(4, weight=1)

        # Zone de texte avec scrollbar
        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_container,
            height=15,
            wrap=tk.WORD,
            background="black",
            foreground="white",
            font=("Consolas", 9),
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Bouton pour effacer les logs
        clear_btn = ttk.Button(
            log_frame, text="Effacer les logs", command=self._clear_logs
        )
        clear_btn.pack(pady=(5, 0))

    def _load_config(self):
        """Charge la configuration initiale"""
        config_file = CONFIG_FILE

        # Charger depuis le fichier JSON si il existe
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config_data = json.load(f)

                # Extraire les URLs uniques de l'historique
                history = config_data.get("history", [])
                unique_urls = []
                seen_urls = set()

                # Parcourir l'historique du plus récent au plus ancien
                for entry in reversed(history):  #  plus récents en premier
                    url = entry.get("odoo_url").strip()
                    # Ignorer les URLs vides ou déjà vues
                    if url and url not in seen_urls:
                        unique_urls.insert(
                            0, url
                        )  # Insérer au début (plus récent d'abord)
                        seen_urls.add(url)

                # Remplir le combobox avec les URLs uniques
                if unique_urls:
                    self.odoo_combo["values"] = unique_urls
                    self._log(
                        f"✓ {len(unique_urls)} URL(s) Odoo unique(s) en historique"
                    )
                else:
                    self.odoo_combo["values"] = []

                # Appliquer les paramètres actuels
                current = config_data.get("current", {})
                self.odoo_url_var.set(current.get("odoo_url"))

                self._log(
                    f"✓ Configuration chargée (dernière utilisation: {config_data.get('current', {}).get('last_used', 'N/A')})"
                )

                # Charger les imprimantes
                self._refresh_printers()

                # Sélectionner l'imprimante sauvegardée si elle existe
                saved_printer = config_data.get("current", {}).get("printer_name", "")
                if saved_printer and saved_printer in self.printer_combo["values"]:
                    self.printer_var.set(saved_printer)

            except Exception as e:
                self._log(f"Erreur lors du chargement de la config: {e}", "warning")
                # Fallback sur le comportement par défaut
                self.odoo_url_var.set(os.environ.get("ODOO_URL", ""))
                self._refresh_printers()
        else:
            # Pas de fichier de config, comportement par défaut
            self.odoo_url_var.set(os.environ.get("ODOO_URL", ""))
            self._refresh_printers()

        # IP locale
        local_ip = get_local_ip()
        self._log(f"IP locale détectée: {local_ip}")

    def _save_config(self):
        """Sauvegarde les paramètres dans un fichier JSON"""
        try:
            # Créer le dossier s'il n'existe pas
            config_dir = CONFIG_DIR
            config_dir.mkdir(exist_ok=True)

            config_file = CONFIG_FILE

            # Préparer les données
            # Charger l'historique existant si présent
            config_data = {}
            if config_file.exists():
                try:
                    with open(config_file, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                except Exception:
                    config_data = {}

            if (
                config_data.get("current", {}).get("odoo_url")
                != self.odoo_url_var.get()
                or config_data.get("current", {}).get("printer_name")
                != self.printer_var.get()
            ):
                history = config_data.get("history", [])
                history.append(
                    {
                        "odoo_url": self.odoo_url_var.get(),
                        "printer_name": self.printer_var.get(),
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
                config_data["current"] = {
                    "odoo_url": self.odoo_url_var.get(),
                    "printer_name": self.printer_var.get(),
                    "last_used": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                config_data["history"] = history

            # Écrire dans le fichier
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)

            self._log("✓ Configuration sauvegardée")

        except Exception as e:
            self._log(f"Impossible de sauvegarder la config: {e}", "warning")

    def _refresh_printers(self):
        """Rafraîchit la liste des imprimantes disponibles"""
        try:
            printers = Printer.list_printers()
            self.printer_combo["values"] = printers

            if printers:
                # Essayer de détecter l'imprimante par défaut
                default_printer = Printer.detect_printer()
                if default_printer and default_printer in printers:
                    self.printer_var.set(default_printer)
                else:
                    self.printer_var.set(printers[0])
                self._log(f"✓ {len(printers)} imprimante(s) détectée(s)")
            else:
                self._log("⚠️ Aucune imprimante détectée", "warning")

        except Exception as e:
            self._log(f"✗ Erreur lors de la détection des imprimantes: {e}", "error")

    def _start_agent(self):
        """Démarre l'agent d'impression"""
        if self.is_running:
            return

        # Validation
        if not self.odoo_url_var.get():
            messagebox.showerror("Erreur", "Veuillez entrer l'URL Odoo")
            return

        if not self.printer_var.get():
            messagebox.showerror("Erreur", "Veuillez sélectionner une imprimante")
            return

        try:
            self.agent = PrintAgentGUI_Wrapper(
                odoo_url=self.odoo_url_var.get(),
                printer_name=self.printer_var.get(),
                log_callback=self._log_from_agent,
                stats_callback=self._update_stats,
            )

            self.agent_thread = threading.Thread(target=self._run_agent, daemon=True)
            self.agent_thread.start()

            self.is_running = True
            self._update_status()
            self._log("✓ Agent démarré avec succès", "success")

        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de démarrer l'agent:\n{e}")
            self._log(f"✗ Erreur de démarrage: {e}", "error")

    def _run_agent(self):
        """Exécute l'agent dans un thread séparé"""
        try:
            # Créer une nouvelle boucle d'événements pour ce thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # exposer la boucle à l'agent pour permettre l'arrêt depuis le thread GUI
            try:
                self.agent._loop = loop
            except Exception:
                pass

            loop.run_until_complete(self.agent.start())
        except Exception as e:
            self._log(f"✗ Erreur dans l'agent: {e}", "error")
            self.is_running = False
            self._update_status()
        finally:
            # Assurer la mise à jour de l'interface dans le thread principal
            def _cleanup():
                self.is_running = False
                self._update_status()
                self._log("✓ Agent arrêté", "warning")

            try:
                self.root.after(0, _cleanup)
            except Exception:
                pass

    def _stop_agent(self):
        """Arrête l'agent d'impression"""
        if not self.is_running:
            return
        # Demander l'arrêt propre à l'agent
        self._log("⏹️ Arrêt de l'agent...", "warning")
        try:
            if self.agent:
                # appeler la méthode stop() exposée par le wrapper
                try:
                    self.agent.stop()
                except Exception as e:
                    self._log(
                        f"✗ Impossible d'envoyer la demande d'arrêt: {e}", "error"
                    )
        except Exception:
            pass

        # Laisser la boucle du worker terminer et mettre à jour l'UI via le cleanup

    def _test_print(self):
        """Effectue un test d'impression"""
        if not self.printer_var.get():
            messagebox.showerror("Erreur", "Veuillez sélectionner une imprimante")
            return

        try:
            printer = Printer()
            printer.printer_name = self.printer_var.get()

            # Créer un ticket de test simple
            test_data = b"\x1b\x40"  # ESC @ - Initialiser
            test_data += b"\x1b\x61\x01"  # ESC a 1 - Centrer
            test_data += b"\x1b\x21\x30"  # ESC ! 48 - Double hauteur et largeur
            test_data += b"TEST D'IMPRESSION\n\n"
            test_data += b"\x1b\x21\x00"  # ESC ! 0 - Normal
            test_data += b"\x1b\x61\x00"  # ESC a 0 - Gauche
            test_data += b"=" * 32 + b"\n"
            test_data += (
                f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n".encode(
                    "cp437"
                )
            )
            test_data += f"Imprimante: {self.printer_var.get()}\n".encode("cp437")
            test_data += b"=" * 32 + b"\n\n"
            test_data += b"Si vous lisez ceci,\n"
            test_data += b"l'impression fonctionne!\n\n\n"
            test_data += b"\x1d\x56\x00"  # GS V 0 - Couper le papier

            if printer.print_raw(test_data):
                self._log("✓ Test d'impression réussi", "success")
                messagebox.showinfo("Succès", "Test d'impression envoyé!")
            else:
                self._log("✗ Échec du test d'impression", "error")
                messagebox.showerror("Erreur", "Le test d'impression a échoué")

        except Exception as e:
            self._log(f"✗ Erreur lors du test: {e}", "error")
            messagebox.showerror("Erreur", f"Erreur lors du test:\n{e}")

    def _log(self, message, level="info"):
        """Ajoute un message au journal"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put((timestamp, message, level))

    def _log_from_agent(self, message, level="info"):
        """Callback pour les logs de l'agent"""
        self._log(message, level)

    def _process_log_queue(self):
        """Traite la queue des logs (appelé périodiquement)"""
        try:
            while True:
                timestamp, message, level = self.log_queue.get_nowait()

                # Coloration selon le niveau
                colors = {
                    "info": "white",
                    "success": "#00ff00",
                    "warning": "#ffaa00",
                    "error": "#ff0000",
                }
                color = colors.get(level, "white")

                # Ajouter au log
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
                self.log_text.insert(tk.END, f"{message}\n", level)
                self.log_text.tag_config("timestamp", foreground="#888888")
                self.log_text.tag_config(level, foreground=color)
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)

        except queue.Empty:
            pass
        finally:
            # Rappeler cette fonction après 100ms
            self.root.after(100, self._process_log_queue)

    def _update_stats(self, stat_type):
        """Met à jour les statistiques"""
        self.stats["total"] += 1
        if stat_type == "success":
            self.stats["success"] += 1
        elif stat_type == "error":
            self.stats["errors"] += 1

        self.total_var.set(str(self.stats["total"]))
        self.success_var.set(str(self.stats["success"]))
        self.error_var.set(str(self.stats["errors"]))

    def _update_status(self):
        """Met à jour l'affichage du statut"""
        if self.is_running:
            self.status_var.set("🟢 En cours d'exécution")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)

            # Afficher les infos de connexion
            local_ip = get_local_ip()
            ws_port = WEBSOCKET_CONFIG["port"]
            http_port = WEBSOCKET_CONFIG.get("http_port", 8766)

            info = f"WebSocket: ws://{local_ip}:{ws_port}\n"
            info += f"HTTP API: http://{local_ip}:{http_port}\n"
            info += f"Odoo: {self.odoo_url_var.get()}\n"
            info += f"Imprimante: {self.printer_var.get()}"

            self.info_text.config(state=tk.NORMAL)
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, info)
            self.info_text.config(state=tk.DISABLED)
        else:
            self.status_var.set("⚪ Arrêté")
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)

            self.info_text.config(state=tk.NORMAL)
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(
                1.0, "Agent arrêté. Cliquez sur 'Démarrer' pour commencer."
            )
            self.info_text.config(state=tk.DISABLED)

    def _clear_logs(self):
        """Efface le journal des événements"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self._log("Journal effacé")

    def _on_closing(self):
        """Gère la fermeture de l'application"""
        # Sauvegarder la configuration avant de quitter
        self._save_config()
        if self.is_running:
            if messagebox.askokcancel(
                "Quitter",
                "L'agent est en cours d'exécution. Voulez-vous vraiment quitter?",
            ):
                self._stop_agent()
                self.root.after(500, self.root.destroy)
        else:
            self.root.destroy()


class PrintAgentGUI_Wrapper:
    """Wrapper de l'agent pour l'intégrer à l'interface graphique"""

    def __init__(self, odoo_url, printer_name, log_callback, stats_callback):
        self.odoo_url = odoo_url
        self.printer_name = printer_name
        self.log_callback = log_callback
        self.stats_callback = stats_callback

        # Créer le printer avec le nom spécifié
        self.printer = Printer()
        self.printer.printer_name = printer_name

        # boucle et event d'arrêt (initialisés quand start() est lancé)
        self._loop = None
        self._stop_event = None
        self._runner = None  # pour arrêter le serveur HTTP
        self._site = None  # pour arrêter le serveur HTTP
        self._ws_server = None  # pour arrêter le serveur WebSocket
        self._command_queue = (
            queue.Queue()
        )  # queue pour les commandes depuis le thread GUI

        self.log_callback(f"Initialisation avec imprimante: {printer_name}")

    def get_receipt_from_odoo(self, order_name):
        """Récupère le ticket depuis Odoo"""
        import urllib.request
        import urllib.parse

        try:
            encoded_name = urllib.parse.quote(order_name, safe="")
            url = f"{self.odoo_url}/pos_direct_print/receipt/{encoded_name}"

            self.log_callback(f"Récupération: {order_name}")

            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    return response.read()
                else:
                    self.log_callback(f"✗ Erreur HTTP: {response.status}", "error")
                    return None

        except Exception as e:
            self.log_callback(f"✗ Erreur récupération: {e}", "error")
            return None

    async def handle_connection(self, websocket):
        """Gère les connexions WebSocket"""
        import json

        async for message in websocket:
            try:
                data = json.loads(message)

                if data.get("type") == "print":
                    order_name = data.get("order_name")
                    self.log_callback(f"📥 Demande: {order_name}")

                    receipt_data = self.get_receipt_from_odoo(order_name)

                    if receipt_data:
                        if self.printer.print_raw(receipt_data):
                            self.log_callback(f"✓ Imprimé: {order_name}", "success")
                            self.stats_callback("success")
                        else:
                            self.log_callback(
                                f"✗ Échec impression: {order_name}", "error"
                            )
                            self.stats_callback("error")
                    else:
                        self.log_callback(
                            f"✗ Ticket non récupéré: {order_name}", "error"
                        )
                        self.stats_callback("error")

            except Exception as e:
                self.log_callback(f"✗ Erreur: {e}", "error")

    async def start(self):
        """Démarre l'agent"""
        import websockets
        from aiohttp import web

        host = WEBSOCKET_CONFIG["host"]
        port = WEBSOCKET_CONFIG["port"]
        http_port = WEBSOCKET_CONFIG.get("http_port", 8766)
        local_ip = get_local_ip()

        self.log_callback("=" * 40)
        self.log_callback("AGENT D'IMPRESSION DÉMARRÉ")
        self.log_callback(f"Odoo: {self.odoo_url}")
        self.log_callback(f"WebSocket: ws://{local_ip}:{port}")
        self.log_callback(f"HTTP: http://{local_ip}:{http_port}")
        self.log_callback(f"Imprimante: {self.printer_name}")
        self.log_callback("=" * 40)

        # Serveur HTTP
        app = web.Application()
        app.router.add_get("/info", self.http_info)
        app.router.add_options("/info", self.http_options)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, http_port)
        await site.start()

        # Stocker les références pour l'arrêt propre
        self._runner = runner
        self._site = site

        # Serveur WebSocket
        # Créer un event d'arrêt pour permettre la fermeture propre depuis un autre thread
        self._stop_event = asyncio.Event()
        self._loop = asyncio.get_running_loop()

        # Démarrer le serveur WebSocket
        server = await websockets.serve(self.handle_connection, host, port)
        self._ws_server = server
        self._ws_server = server
        self.log_callback("✓ Serveurs démarrés - En attente de connexions...")

        try:
            # Attendre l'événement d'arrêt ou une commande
            while not self._stop_event.is_set():
                try:
                    # Vérifier les commandes (timeout court pour ne pas bloquer)
                    command = self._command_queue.get_nowait()
                    if command == "stop":
                        break
                except queue.Empty:
                    pass
                await asyncio.sleep(0.1)  # Petit délai pour éviter de boucler trop vite
        finally:
            # Arrêter proprement le serveur WebSocket
            server.close()
            await server.wait_closed()

        # Attendre un peu pour que les serveurs se libèrent proprement
        await asyncio.sleep(0.5)

    async def http_info(self, request):
        """Endpoint HTTP pour la découverte"""
        from aiohttp import web

        local_ip = get_local_ip()
        return web.json_response(
            {
                "ip": local_ip,
                "websocket_port": WEBSOCKET_CONFIG["port"],
                "websocket_url": f"ws://{local_ip}:{WEBSOCKET_CONFIG['port']}",
            },
            headers={"Access-Control-Allow-Origin": "*"},
        )

    async def http_options(self, request):
        """Gère CORS preflight"""
        from aiohttp import web

        return web.Response(
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        )

    def stop(self):
        """Demande l'arrêt propre de l'agent (appelable depuis le thread GUI)."""
        try:
            # Envoyer la commande stop via la queue
            self._command_queue.put("stop")

            # Planifier l'arrêt propre dans la boucle de l'agent
            def _shutdown():
                async def _async_shutdown():
                    try:
                        # Arrêter les serveurs
                        if self._ws_server:
                            self._ws_server.close()
                        if self._site:
                            await self._site.stop()
                        if self._runner:
                            await self._runner.cleanup()

                        # Signaler l'arrêt
                        if self._stop_event and not self._stop_event.is_set():
                            self._stop_event.set()
                    except Exception as e:
                        try:
                            self.log_callback(
                                f"✗ Erreur lors de l'arrêt des serveurs: {e}", "error"
                            )
                        except Exception:
                            pass

                # Créer une task pour l'arrêt async
                self._loop.create_task(_async_shutdown())

            # Utiliser call_soon_threadsafe si la boucle existe
            if self._loop:
                self._loop.call_soon_threadsafe(_shutdown)
        except Exception as e:
            try:
                self.log_callback(f"✗ Erreur lors de l'arrêt: {e}", "error")
            except Exception:
                pass


def main():
    """Point d'entrée principal"""
    root = tk.Tk()

    # Définir le style
    style = ttk.Style()

    # Essayer d'utiliser un thème moderne
    try:
        style.theme_use("clam")
    except:
        pass

    # Configurer les couleurs personnalisées
    style.configure("success.TButton", foreground="green")
    style.configure("danger.TButton", foreground="red")

    app = PrintAgentGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
