"""Fluxos relacionados a navegacao e coleta de pontos do Rewards."""

from botasaurus.browser import browser, Driver

from .config import BROWSER_KWARGS


class NavegadorRecompensas:
    """Encapsula operacoes de navegacao na pagina do Bing Rewards."""

    @staticmethod
    @browser(**{**BROWSER_KWARGS, "reuse_driver": True})
    def abrir_pagina(driver: Driver, dados=None):
        """Abre a pagina principal do Bing Rewards e aguarda interacao humana."""

        driver.enable_human_mode()
        driver.google_get("https://rewards.bing.com")
        driver.prompt()


# Alias para retrocompatibilidade, caso algum cliente ainda use a funcao
goto_rewards_page = NavegadorRecompensas.abrir_pagina


__all__ = ["NavegadorRecompensas", "goto_rewards_page"]
