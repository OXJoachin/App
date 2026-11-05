from __future__ import annotations

import json
import os
from datetime import date

import requests
from kivy.app import App
from kivy.factory import Factory
from kivy.lang import Builder
from kivy.uix.screenmanager import Screen, ScreenManager

API_URL = os.environ.get("PERIOD_TRACKER_API_URL", "http://127.0.0.1:8001")


class LoginScreen(Screen):
    pass


class DashboardScreen(Screen):
    pass


Factory.register("LoginScreen", cls=LoginScreen)
Factory.register("DashboardScreen", cls=DashboardScreen)
Builder.load_file("/home/joachin/Bureau/a/frontend/period_tracker.kv")


class PeriodTrackerApp(App):
    token = ""
    current_user = {}
    dashboard_data = {}

    def build(self):
        self.sm = ScreenManager()
        self.login_screen = LoginScreen(name="login")
        self.dashboard_screen = DashboardScreen(name="dashboard")
        self.sm.add_widget(self.login_screen)
        self.sm.add_widget(self.dashboard_screen)
        self.sm.current = "login"
        return self.sm

    def show_status(self, message: str, is_error: bool = False):
        target_screen = self.login_screen if self.sm.current == "login" else self.dashboard_screen
        status_widget = target_screen.ids.get("status")
        if status_widget is not None:
            status_widget.text = message
            status_widget.color = (0.9, 0.1, 0.1, 1) if is_error else (0.1, 0.6, 0.2, 1)

    def login(self):
        identifier = self.login_screen.ids.username.text.strip()
        password = self.login_screen.ids.password.text.strip()
        if not identifier or not password:
            self.show_status("Veuillez renseigner vos identifiants.", True)
            return

        response = requests.post(
            f"{API_URL}/api/login",
            json={"identifier": identifier, "password": password},
            timeout=10,
        )

        if response.status_code != 200:
            self.show_status(response.json().get("detail", "Erreur de connexion."), True)
            return

        payload = response.json()
        self.token = payload["access_token"]
        self.current_user = payload["user"]
        self.load_dashboard()
        self.sm.current = "dashboard"
        self.show_status("Connexion réussie.")

    def register(self):
        identifier = self.login_screen.ids.username.text.strip()
        password = self.login_screen.ids.password.text.strip()
        if not identifier or not password:
            self.show_status("Nom et mot de passe requis.", True)
            return

        email = identifier if "@" in identifier else f"{identifier}@example.com"
        response = requests.post(
            f"{API_URL}/api/register",
            json={"username": identifier, "email": email, "password": password},
            timeout=10,
        )

        if response.status_code != 200:
            self.show_status(response.json().get("detail", "Création du compte impossible."), True)
            return

        self.show_status("Compte créé. Vous pouvez maintenant vous connecter.")

    def logout(self):
        self.token = ""
        self.current_user = {}
        self.sm.current = "login"
        self.login_screen.ids.username.text = ""
        self.login_screen.ids.password.text = ""
        self.login_screen.ids.status.text = "Déconnecté."

    def _auth_headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def load_dashboard(self):
        response = requests.get(f"{API_URL}/api/dashboard", headers=self._auth_headers(), timeout=10)
        if response.status_code != 200:
            self.show_status(response.json().get("detail", "Impossible de charger le tableau de bord."), True)
            return

        self.dashboard_data = response.json()
        self.render_history()
        self.dashboard_screen.ids.summary.text = (
            f"Prochaine période estimée : {self.dashboard_data.get('next_period_date', 'N/A')}\n"
            f"Cycles enregistrés : {self.dashboard_data.get('total_cycles', 0)}"
        )
        self.dashboard_screen.ids.status.text = "Prédiction calculée"

    def show_prediction(self):
        data = self.dashboard_data or {}
        next_period = data.get("next_period_date", "N/A")
        text = (
            f"Prédiction des prochaines règles\n\n"
            f"Date estimée : {next_period}\n\n"
            f"Basée sur les cycles précédents enregistrés."
        )
        self.dashboard_screen.ids.summary.text = text
        self.dashboard_screen.ids.status.text = "Prédiction"

    def show_history(self):
        self.render_history()
        self.dashboard_screen.ids.summary.text = (
            "Historique\n\n"
            "Consultez les cycles précédents dans la liste ci-dessous."
        )
        self.dashboard_screen.ids.status.text = "Historique"

    def render_history(self):
        history = (self.dashboard_data or {}).get("history", [])
        history_box = self.dashboard_screen.ids.history_list
        history_box.clear_widgets()

        if not history:
            label = self._make_label("Aucun cycle enregistré pour le moment.")
            history_box.add_widget(label)
            return

        for cycle in history:
            widget = self._make_label(
                f"Du {cycle['start_date']} au {cycle['end_date']} — {cycle['duration_days']} jours"
            )
            history_box.add_widget(widget)

    def _make_label(self, text):
        from kivy.uix.label import Label

        label = Label(
            text=text,
            size_hint_y=None,
            height='36dp',
            halign='left',
            valign='middle',
            text_size=(self.dashboard_screen.width - 40, None),
            color=(0.1, 0.1, 0.1, 1),
        )
        return label

    def add_cycle(self):
        if not self.token:
            self.show_status("Veuillez vous connecter d'abord.", True)
            self.sm.current = "login"
            return

        start_date = self.dashboard_screen.ids.start_date.text.strip()
        end_date = self.dashboard_screen.ids.end_date.text.strip()
        if not start_date or not end_date:
            self.show_status("Veuillez saisir les dates de début et de fin.", True)
            return

        try:
            date.fromisoformat(start_date)
            date.fromisoformat(end_date)
        except ValueError:
            self.show_status("Format de date invalide. Utilisez YYYY-MM-DD.", True)
            return

        response = requests.post(
            f"{API_URL}/api/cycles",
            json={"start_date": start_date, "end_date": end_date},
            headers=self._auth_headers(),
            timeout=10,
        )

        if response.status_code != 200:
            self.show_status(response.json().get("detail", "Enregistrement impossible."), True)
            return

        self.dashboard_screen.ids.start_date.text = ""
        self.dashboard_screen.ids.end_date.text = ""
        self.show_status("Cycle enregistré avec succès.")
        self.load_dashboard()


if __name__ == "__main__":
    PeriodTrackerApp().run()
