"""Fluxos relacionados à navegação do Microsoft Rewards."""

from __future__ import annotations

from typing import Optional

from botasaurus.browser import browser, Driver

from .config import BROWSER_KWARGS, REWARDS_BASE_URL
from .logging import log


class NavegadorRecompensas:
    """Encapsula operações de navegação na página do Bing Rewards."""

    _CONFIG_PADRAO = {**BROWSER_KWARGS, "reuse_driver": False}

    @classmethod
    def abrir_pagina(
        cls,
        *,
        reuse_driver: Optional[bool] = None,
        **kwargs,
    ):
        """Abre a página principal do Rewards com configuração flexível."""

        configuracao = dict(cls._CONFIG_PADRAO)
        if reuse_driver is not None:
            configuracao["reuse_driver"] = reuse_driver

        @browser(**configuracao)
        def _abrir(driver: Driver, dados=None):
            driver.enable_human_mode()
            driver.google_get(REWARDS_BASE_URL)
            html = getattr(driver, "page_source", "") or ""
            if "Sign in" in html or "Entrar" in html:
                log.aviso(
                    "Parece que voce nao esta logado no Rewards",
                    detalhe="Acesse https://rewards.microsoft.com/ e entre com sua conta Microsoft",
                )
            driver.prompt()

        return _abrir(**kwargs)


__all__ = ["NavegadorRecompensas"]
