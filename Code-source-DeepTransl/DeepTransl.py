
import sys
import os
import json
import shutil
from pathlib import Path

if getattr(sys, "frozen", False):
    dossier = Path(sys.executable).resolve().parent
else:
    dossier = Path(__file__).resolve().parent

MODELS_DIR = dossier / "models"
PACKAGES_DIR = MODELS_DIR / "packages"
DOWNLOADS_DIR = MODELS_DIR / "downloads"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

fichier_historique = dossier / "history.json"

os.environ["ARGOS_PACKAGES_DIR"] = str(PACKAGES_DIR)
os.environ["ARGOS_CHUNK_TYPE"] = "SPACY"

import argostranslate.package
import argostranslate.translate

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QComboBox, QMainWindow, QMessageBox
)


LANGUES = {
    "Français": "fr",
    "English": "en",
    "Türkçe": "tr"
}

NOMS = {code: nom for nom, code in LANGUES.items()}

DIRECTIONS = [
    ("fr", "en"),
    ("en", "fr"),
    ("tr", "en"),
    ("en", "tr")
]


STYLE = """
QMainWindow, QWidget {
    font-family: "Bahnschrift SemiLight";
    font-size: 13px;
    color: #1f2937;
}

QMenuBar {
    background-color: white;
    padding: 4px;
}

QMenuBar::item {
    background: transparent;
    padding: 6px 12px;
    border-radius: 2px;
}

QMenuBar::item:selected {
    background-color: #ececec;
}

QMenu {
    background-color: #ececec;
    border: 1px solid #e5e7eb;
    padding: 5px;
}

QMenu::item {
    padding: 7px 26px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #ececec;
    color: #1f2937;
}

QMenu::item:disabled {
    color: #9ca3af;
}

QMenu::separator {
    height: 1px;
    background: #000000;
    margin: 6px 8px;
}

QLabel {
    background: transparent;
    font-weight: bold;
    color: #4b5563;
}

QComboBox {
    background-color: transparent;
    border: 1px solid #111827;
    border-radius: 8px;
    padding: 8px 12px;
    min-height: 22px;
}

QTextEdit {
    background-color: white;
    color: #111827;
    border: 1px solid #d1d5db;
    border-radius: 10px;
    padding: 12px;
    font-size: 16px;
}

QTextEdit:focus {
    border: 1px solid #111111;
}

QTextEdit#sortie {
    background-color: #f9fafb;
}

QPushButton#boutonSwap {
    background-color: transparent;
    font-size: 24px;
    color: #111111;
}

QPushButton#boutonTraduire {
    background-color: #111111;
    color: white;
    border: none;
    border-radius: 20px;
    font-size: 16px;
}

QPushButton#boutonTraduire:hover {
    background-color: #333333;
}

QPushButton#boutonTraduire:pressed {
    background-color: #000000;
}

QPushButton#boutonTraduire:disabled {
    background-color: #d1d5db;
    color: #6b7280;
}
"""


def actualiser_cache():
    argostranslate.translate.get_installed_languages.cache_clear()


def obtenir_traduction(source, cible):

    actualiser_cache()

    langues = argostranslate.translate.get_installed_languages()

    langue_source = next(
        (lang for lang in langues if lang.code == source),
        None
    )

    langue_cible = next(
        (lang for lang in langues if lang.code == cible),
        None
    )

    if langue_source is None or langue_cible is None:
        return None

    return langue_source.get_translation(langue_cible)


def modele_installe(source, cible):

    try:
        return obtenir_traduction(source, cible) is not None

    except Exception:
        return False


def tous_modeles_installes():

    return all(
        modele_installe(source, cible)
        for source, cible in DIRECTIONS
    )


def chemin_modele(source, cible):

    nom = f"translate-{source}_{cible}.argosmodel"

    return DOWNLOADS_DIR / nom


def trouver_package(disponibles, source, cible):

    return next(
        (
            paquet for paquet in disponibles
            if paquet.type == "translate"
            and paquet.from_code == source
            and paquet.to_code == cible
        ),
        None
    )


def installer_modele_local(source, cible):

    chemin = chemin_modele(source, cible)

    if not chemin.is_file():
        return False

    argostranslate.package.install_from_path(chemin)

    actualiser_cache()

    return modele_installe(source, cible)


class GestionnaireModeles(QThread):

    message = pyqtSignal(str)
    resultat = pyqtSignal(bool, str)

    def run(self):

        try:

            erreurs = []
            manquants = []

            self.message.emit(
                "Vérification des modèles installés..."
            )

            for source, cible in DIRECTIONS:

                if modele_installe(source, cible):
                    continue

                chemin = chemin_modele(source, cible)

                if chemin.is_file():

                    self.message.emit(
                        f"Installation locale : "
                        f"{source.upper()} → {cible.upper()}"
                    )

                    try:

                        if installer_modele_local(source, cible):
                            continue

                    except Exception as e:

                        erreurs.append(
                            f"{source} → {cible} : {str(e)}"
                        )

                        continue

                manquants.append((source, cible))

            if manquants:

                self.message.emit(
                    "Connexion au catalogue des modèles..."
                )

                argostranslate.package.update_package_index()

                disponibles = (
                    argostranslate.package.get_available_packages()
                )

                if not disponibles:

                    raise RuntimeError(
                        "Catalogue des modèles inaccessible. "
                        "Vérifie ta connexion Internet."
                    )

                for source, cible in manquants:

                    if modele_installe(source, cible):
                        continue

                    self.message.emit(
                        f"Recherche : {source.upper()} → {cible.upper()}"
                    )

                    paquet = trouver_package(
                        disponibles,
                        source,
                        cible
                    )

                    if paquet is None:

                        erreurs.append(
                            f"Modèle introuvable : {source} → {cible}"
                        )

                        continue

                    chemin = chemin_modele(source, cible)

                    if not chemin.exists():

                        self.message.emit(
                            f"Téléchargement : "
                            f"{source.upper()} → {cible.upper()}"
                        )

                        chemin_telecharge = paquet.download()

                        shutil.copy2(
                            chemin_telecharge,
                            chemin
                        )

                    self.message.emit(
                        f"Installation : "
                        f"{source.upper()} → {cible.upper()}"
                    )

                    try:

                        if not installer_modele_local(source, cible):

                            erreurs.append(
                                f"Installation non vérifiée : "
                                f"{source} → {cible}"
                            )

                    except Exception as e:

                        erreurs.append(
                            f"{source} → {cible} : {str(e)}"
                        )

            actualiser_cache()

            if not tous_modeles_installes():

                if erreurs:
                    detail = "\n".join(erreurs)
                else:
                    detail = "Un ou plusieurs modèles sont indisponibles."

                raise RuntimeError(detail)

            self.resultat.emit(
                True,
                "Tous les modèles sont prêts. "
                "DeepTransl peut fonctionner hors ligne."
            )

        except Exception as e:

            self.resultat.emit(
                False,
                "Impossible de préparer les modèles :\n\n" + str(e)
            )


def charger_historique():

    if not fichier_historique.exists():
        return []

    try:

        with open(
            fichier_historique,
            "r",
            encoding="utf-8"
        ) as fichier:

            data = json.load(fichier)

            return data if isinstance(data, list) else []

    except Exception:
        return []


def sauvegarder_historique(historique):

    try:

        with open(
            fichier_historique,
            "w",
            encoding="utf-8"
        ) as fichier:

            json.dump(
                historique,
                fichier,
                ensure_ascii=False,
                indent=4
            )

    except Exception as e:

        print("Erreur sauvegarde historique :", e)


def traduire_texte(texte, source, cible):

    if source == cible:
        return texte

    if not modele_installe(source, cible):

        raise RuntimeError(
            f"Le modèle {source} → {cible} est indisponible."
        )

    resultat = argostranslate.translate.translate(
        texte,
        source,
        cible
    )

    if resultat is None:

        raise RuntimeError(
            f"Impossible de traduire {source} → {cible}."
        )

    return resultat


class Traducteur(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("DeepTransl")

        self.setMinimumSize(900, 550)
        self.resize(1100, 650)

        ecran = QApplication.primaryScreen().availableGeometry()

        geo = self.frameGeometry()
        geo.moveCenter(ecran.center())

        self.move(geo.topLeft())

        self.historique = charger_historique()

        self.modeles_prets = False
        self.thread_modeles = None

        self.creer_menu()
        self.creer_interface()

        self.statusBar().showMessage(
            "Préparation des modèles linguistiques..."
        )

    def creer_menu(self):

        barre = self.menuBar()

        menu_fichier = barre.addMenu("Fichier")

        action_nouvelle = menu_fichier.addAction(
            "Nouvelle traduction"
        )

        action_nouvelle.triggered.connect(
            self.nouvelle_traduction
        )

        menu_fichier.addSeparator()

        action_quitter = menu_fichier.addAction("Quitter")

        action_quitter.triggered.connect(self.close)

        menu_trad = barre.addMenu("Traduction")

        action_traduire = menu_trad.addAction("Traduire")

        action_traduire.triggered.connect(self.traduire)

        action_effacer = menu_trad.addAction("Effacer")

        action_effacer.triggered.connect(self.effacer)

        self.menu_historique = barre.addMenu("Historique")

        self.maj_menu_historique()

    def creer_interface(self):

        page = QWidget()

        layout_principal = QVBoxLayout()

        layout_principal.setContentsMargins(
            24, 20, 24, 24
        )

        layout_principal.setSpacing(16)

        layout_langues = QHBoxLayout()
        layout_langues.setSpacing(14)

        layout_source = QVBoxLayout()
        layout_source.setSpacing(6)

        self.source = QComboBox()

        self.source.addItems(
            list(LANGUES.keys())
        )

        self.source.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        layout_source.addWidget(self.source)

        bouton_swap = QPushButton("⇄")

        bouton_swap.setObjectName("boutonSwap")
        bouton_swap.setFixedSize(36, 36)

        bouton_swap.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        bouton_swap.setToolTip("Inverser les langues")

        bouton_swap.clicked.connect(self.inverser)

        layout_cible = QVBoxLayout()
        layout_cible.setSpacing(6)

        self.cible = QComboBox()

        self.cible.addItems(
            list(LANGUES.keys())
        )

        self.cible.setCurrentText("English")

        self.cible.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        layout_cible.addWidget(self.cible)

        layout_langues.addLayout(layout_source, 1)

        layout_langues.addWidget(
            bouton_swap,
            0,
            Qt.AlignmentFlag.AlignBottom
        )

        layout_langues.addLayout(layout_cible, 1)

        layout_principal.addLayout(layout_langues)

        layout_textes = QHBoxLayout()
        layout_textes.setSpacing(16)

        layout_gauche = QVBoxLayout()
        layout_gauche.setSpacing(6)

        self.texte_entree = QTextEdit()

        self.texte_entree.setPlaceholderText(
            "Entrez votre texte..."
        )

        layout_gauche.addWidget(self.texte_entree)

        layout_droite = QVBoxLayout()
        layout_droite.setSpacing(6)

        self.texte_sortie = QTextEdit()

        self.texte_sortie.setObjectName("sortie")
        self.texte_sortie.setReadOnly(True)

        self.texte_sortie.setPlaceholderText(
            "La traduction apparaîtra ici..."
        )

        layout_droite.addWidget(self.texte_sortie)

        layout_textes.addLayout(layout_gauche)
        layout_textes.addLayout(layout_droite)

        layout_principal.addLayout(
            layout_textes,
            1
        )

        self.bouton_traduire = QPushButton("Traduire")

        self.bouton_traduire.setObjectName(
            "boutonTraduire"
        )

        self.bouton_traduire.setFixedHeight(48)

        self.bouton_traduire.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.bouton_traduire.setEnabled(False)

        self.bouton_traduire.clicked.connect(
            self.traduire
        )

        layout_principal.addWidget(
            self.bouton_traduire
        )

        page.setLayout(layout_principal)

        self.setCentralWidget(page)

    def demarrer_modeles(self):

        if self.thread_modeles is not None:
            return

        self.bouton_traduire.setEnabled(False)

        self.statusBar().showMessage(
            "Vérification des modèles linguistiques..."
        )

        self.thread_modeles = GestionnaireModeles(self)

        self.thread_modeles.message.connect(
            self.afficher_progression
        )

        self.thread_modeles.resultat.connect(
            self.installation_terminee
        )

        self.thread_modeles.finished.connect(
            self.nettoyer_thread_modeles
        )

        self.thread_modeles.start()

    def afficher_progression(self, message):

        self.statusBar().showMessage(message)

    def installation_terminee(self, succes, message):

        self.modeles_prets = (
            succes and tous_modeles_installes()
        )

        self.bouton_traduire.setEnabled(
            self.modeles_prets
        )

        if self.modeles_prets:

            self.statusBar().showMessage(
                "Traduction hors ligne disponible"
            )

        else:

            self.statusBar().showMessage(
                "Modèles indisponibles · Vérifie ta connexion"
            )

            QMessageBox.critical(
                self,
                "Préparation des modèles",
                message
            )

    def nettoyer_thread_modeles(self):

        thread = self.thread_modeles

        self.thread_modeles = None

        if thread is not None:
            thread.deleteLater()

    def traduire(self):

        texte = self.texte_entree.toPlainText().strip()

        if not texte:
            return

        if not self.modeles_prets:

            QMessageBox.warning(
                self,
                "Modèles indisponibles",
                "Les modèles linguistiques ne sont pas encore prêts."
            )

            return

        code_source = LANGUES[
            self.source.currentText()
        ]

        code_cible = LANGUES[
            self.cible.currentText()
        ]

        if code_source == code_cible:

            self.texte_sortie.setPlainText(texte)

            return

        self.bouton_traduire.setEnabled(False)

        try:

            resultat = traduire_texte(
                texte,
                code_source,
                code_cible
            )

            self.texte_sortie.setPlainText(
                resultat
            )

            element = {
                "source": code_source,
                "target": code_cible,
                "text": texte,
                "translation": resultat
            }

            self.historique.insert(
                0,
                element
            )

            self.historique = self.historique[:100]

            sauvegarder_historique(
                self.historique
            )

            self.maj_menu_historique()

        except Exception as e:

            QMessageBox.critical(
                self,
                "Erreur de traduction",
                str(e)
            )

        finally:

            self.bouton_traduire.setEnabled(
                self.modeles_prets
            )

    def maj_menu_historique(self):

        self.menu_historique.clear()

        if not self.historique:

            action = self.menu_historique.addAction(
                "Aucune traduction"
            )

            action.setEnabled(False)

            return

        for i, item in enumerate(self.historique):

            texte = item.get("text", "")

            if len(texte) > 50:
                texte = texte[:50] + "..."

            titre = (
                item.get("source", "").upper()
                + " → "
                + item.get("target", "").upper()
                + " : "
                + texte
            )

            action = self.menu_historique.addAction(
                titre
            )

            action.triggered.connect(
                lambda checked=False, index=i:
                self.charger_element(index)
            )

        self.menu_historique.addSeparator()

        action_vider = self.menu_historique.addAction(
            "Vider l'historique"
        )

        action_vider.triggered.connect(
            self.vider_historique
        )

    def charger_element(self, index):

        if index < 0 or index >= len(self.historique):
            return

        item = self.historique[index]

        self.texte_entree.setPlainText(
            item.get("text", "")
        )

        self.texte_sortie.setPlainText(
            item.get("translation", "")
        )

        if item.get("source") in NOMS:

            self.source.setCurrentText(
                NOMS[item["source"]]
            )

        if item.get("target") in NOMS:

            self.cible.setCurrentText(
                NOMS[item["target"]]
            )

    def vider_historique(self):

        reponse = QMessageBox.question(
            self,
            "Vider l'historique",
            "Voulez-vous vraiment supprimer tout l'historique ?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
        )

        if reponse == QMessageBox.StandardButton.Yes:

            self.historique = []

            sauvegarder_historique(
                self.historique
            )

            self.maj_menu_historique()

    def nouvelle_traduction(self):

        self.texte_entree.clear()
        self.texte_sortie.clear()

        self.texte_entree.setFocus()

    def effacer(self):

        self.texte_entree.clear()
        self.texte_sortie.clear()

    def inverser(self):

        langue_source = self.source.currentText()
        langue_cible = self.cible.currentText()

        self.source.setCurrentText(langue_cible)
        self.cible.setCurrentText(langue_source)

        entree = self.texte_entree.toPlainText()
        sortie = self.texte_sortie.toPlainText()

        self.texte_entree.setPlainText(sortie)
        self.texte_sortie.setPlainText(entree)

    def closeEvent(self, event):

        if (
            self.thread_modeles is not None
            and self.thread_modeles.isRunning()
        ):

            self.thread_modeles.wait()

        event.accept()


if __name__ == "__main__":

    app = QApplication(sys.argv)

    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)

    fenetre = Traducteur()
    fenetre.show()

    fenetre.demarrer_modeles()

    sys.exit(app.exec())
