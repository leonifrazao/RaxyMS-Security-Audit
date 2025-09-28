#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API Flask para gerenciamento de proxys V2Ray/Xray."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Callable

from flask import Blueprint, Response, current_app, jsonify, request
from flask.views import MethodView

from interfaces.services import IProxyService
from .manager import Proxy as ProxyService

__all__ = ["ProxyAPI"]


class _BaseProxyView(MethodView):
    """Fornece acesso simplificado ao serviço de proxys dentro das views."""

    def __init__(self, api: "ProxyAPI") -> None:
        self._api = api

    @property
    def service(self) -> IProxyService:
        return self._api.service

    def _extract_payload(self) -> tuple[Mapping[str, Any], Response | None]:
        payload = request.get_json(silent=True)
        if payload is None:
            return {}, None
        if not isinstance(payload, Mapping):
            return {}, self._api._json_error("Corpo JSON deve ser um objeto.", 400)
        return payload, None


class _ProxyEntriesView(_BaseProxyView):
    def get(self) -> Response:
        entries = self._api._serialize_entries(self.service.entries)
        return jsonify({"entries": entries, "count": len(entries)})


class _ProxyErrorsView(_BaseProxyView):
    def get(self) -> Response:
        erros = list(self.service.parse_errors)
        return jsonify({"errors": erros, "count": len(erros)})


class _ProxyProxiesView(_BaseProxyView):
    def post(self) -> Response:
        payload, error = self._extract_payload()
        if error:
            return error
        try:
            proxies = self._api._coerce_str_sequence(payload.get("proxies"), "proxies")
        except ValueError as exc:
            return self._api._json_error(str(exc), 400)
        if not proxies:
            return self._api._json_error("Informe ao menos uma proxy em 'proxies'.", 400)

        try:
            adicionadas = self.service.add_proxies(proxies)
        except Exception:  # pragma: no cover - logging auxiliar
            self._api._log_exception("Falha ao adicionar proxys manualmente")
            return self._api._json_error("Erro interno ao adicionar proxys.", 500)

        entries = self._api._serialize_entries(self.service.entries)
        return jsonify({"added": adicionadas, "entries": entries, "total": len(entries)})


class _ProxySourcesView(_BaseProxyView):
    def post(self) -> Response:
        payload, error = self._extract_payload()
        if error:
            return error
        try:
            fontes = self._api._coerce_str_sequence(payload.get("sources"), "sources")
        except ValueError as exc:
            return self._api._json_error(str(exc), 400)
        if not fontes:
            return self._api._json_error("Informe ao menos uma fonte em 'sources'.", 400)

        try:
            carregadas = self.service.add_sources(fontes)
        except Exception:  # pragma: no cover - logging auxiliar
            self._api._log_exception("Falha ao carregar proxys a partir das fontes")
            return self._api._json_error("Erro interno ao carregar fontes.", 500)

        entries = self._api._serialize_entries(self.service.entries)
        return jsonify({"loaded": carregadas, "entries": entries, "total": len(entries)})


class _ProxyTestView(_BaseProxyView):
    def post(self) -> Response:
        payload, error = self._extract_payload()
        if error:
            return error
        try:
            country = self._api._coerce_optional_str(payload.get("country"), "country")
            verbose = self._api._coerce_optional_bool(payload.get("verbose"), "verbose")
            force_refresh = self._api._coerce_bool(payload.get("force_refresh"), "force_refresh", default=False)
        except ValueError as exc:
            return self._api._json_error(str(exc), 400)

        try:
            entries = self.service.test(country=country, verbose=verbose, force_refresh=force_refresh)
        except Exception:  # pragma: no cover - logging auxiliar
            self._api._log_exception("Falha ao executar testes de proxys")
            return self._api._json_error("Erro interno ao testar proxys.", 500)

        serialized = self._api._serialize_entries(entries)
        return jsonify({"entries": serialized, "count": len(serialized)})


class _ProxyStartView(_BaseProxyView):
    def post(self) -> Response:
        payload, error = self._extract_payload()
        if error:
            return error
        try:
            country = self._api._coerce_optional_str(payload.get("country"), "country")
            auto_test = self._api._coerce_bool(payload.get("auto_test"), "auto_test", default=True)
            wait_flag = self._api._coerce_bool(payload.get("wait"), "wait", default=False)
        except ValueError as exc:
            return self._api._json_error(str(exc), 400)

        try:
            bridges = self.service.start(country=country, auto_test=auto_test, wait=wait_flag)
        except RuntimeError as exc:
            return self._api._json_error(str(exc), 409)
        except Exception:  # pragma: no cover - logging auxiliar
            self._api._log_exception("Falha ao iniciar pontes HTTP para proxys")
            return self._api._json_error("Erro interno ao iniciar proxys.", 500)

        entries = self._api._serialize_entries(self.service.entries)
        return jsonify({
            "bridges": list(bridges),
            "count": len(bridges),
            "entries": entries,
            "running": True,
        })


class _ProxyStopView(_BaseProxyView):
    def post(self) -> Response:
        try:
            self.service.stop()
        except Exception:  # pragma: no cover - logging auxiliar
            self._api._log_exception("Falha ao encerrar pontes HTTP")
            return self._api._json_error("Erro interno ao encerrar proxys.", 500)
        return jsonify({"running": False})


class _ProxyWaitView(_BaseProxyView):
    def post(self) -> Response:
        try:
            self.service.wait()
        except RuntimeError as exc:
            return self._api._json_error(str(exc), 409)
        except Exception:  # pragma: no cover - logging auxiliar
            self._api._log_exception("Falha ao aguardar término das pontes HTTP")
            return self._api._json_error("Erro interno ao aguardar pontes.", 500)
        return jsonify({"running": False})


class _ProxyHttpView(_BaseProxyView):
    def get(self) -> Response:
        try:
            proxies = self.service.get_http_proxy()
        except RuntimeError as exc:
            return self._api._json_error(str(exc), 409)
        except Exception:  # pragma: no cover - logging auxiliar
            self._api._log_exception("Falha ao listar proxys HTTP locais")
            return self._api._json_error("Erro interno ao listar proxys.", 500)
        return jsonify({"http": list(proxies), "count": len(proxies)})


class ProxyAPI:
    """Encapsula rotas Flask para o gerenciamento de proxys V2Ray/Xray."""

    def __init__(
        self,
        service: IProxyService | None = None,
        *,
        service_factory: Callable[[], IProxyService] | None = None,
    ) -> None:
        if service is not None and service_factory is not None:
            raise ValueError("Informe 'service' ou 'service_factory', não ambos.")

        factory = service_factory or ProxyService
        self._service = service or factory()

        self._blueprint = Blueprint("proxy_management", __name__)
        self._register_routes()

    @property
    def service(self) -> IProxyService:
        return self._service

    @property
    def blueprint(self) -> Blueprint:
        return self._blueprint

    def _register_routes(self) -> None:
        entries_view = _ProxyEntriesView.as_view("proxy_entries", api=self)
        errors_view = _ProxyErrorsView.as_view("proxy_errors", api=self)
        proxies_view = _ProxyProxiesView.as_view("proxy_add", api=self)
        sources_view = _ProxySourcesView.as_view("proxy_sources", api=self)
        test_view = _ProxyTestView.as_view("proxy_test", api=self)
        start_view = _ProxyStartView.as_view("proxy_start", api=self)
        stop_view = _ProxyStopView.as_view("proxy_stop", api=self)
        wait_view = _ProxyWaitView.as_view("proxy_wait", api=self)
        http_view = _ProxyHttpView.as_view("proxy_http", api=self)

        self._blueprint.add_url_rule("/proxy/entries", view_func=entries_view, methods=["GET"])
        self._blueprint.add_url_rule("/proxy/errors", view_func=errors_view, methods=["GET"])
        self._blueprint.add_url_rule("/proxy/proxies", view_func=proxies_view, methods=["POST"])
        self._blueprint.add_url_rule("/proxy/sources", view_func=sources_view, methods=["POST"])
        self._blueprint.add_url_rule("/proxy/test", view_func=test_view, methods=["POST"])
        self._blueprint.add_url_rule("/proxy/start", view_func=start_view, methods=["POST"])
        self._blueprint.add_url_rule("/proxy/stop", view_func=stop_view, methods=["POST"])
        self._blueprint.add_url_rule("/proxy/wait", view_func=wait_view, methods=["POST"])
        self._blueprint.add_url_rule("/proxy/http", view_func=http_view, methods=["GET"])

    @staticmethod
    def _parse_bool(value: str | None) -> bool:
        if value is None:
            return False
        normalized = value.strip().lower()
        return normalized in {"1", "true", "t", "yes", "y", "on"}

    def _coerce_optional_bool(self, value: Any, field: str) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            if not value.strip():
                return None
            return self._parse_bool(value)
        raise ValueError(f"O campo '{field}' deve ser booleano.")

    def _coerce_bool(self, value: Any, field: str, *, default: bool = False) -> bool:
        coerced = self._coerce_optional_bool(value, field)
        if coerced is None:
            return default
        return coerced

    @staticmethod
    def _coerce_optional_str(value: Any, field: str) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            texto = value.strip()
            return texto or None
        raise ValueError(f"O campo '{field}' deve ser uma string.")

    @staticmethod
    def _coerce_str_sequence(value: Any, field: str) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            candidatos = [value]
        elif isinstance(value, Iterable) and not isinstance(value, Mapping):
            candidatos = list(value)
        else:
            raise ValueError(f"O campo '{field}' deve ser uma lista de strings.")

        resultado: list[str] = []
        for item in candidatos:
            if not isinstance(item, str):
                raise ValueError(f"O campo '{field}' deve conter apenas strings.")
            texto = item.strip()
            if texto:
                resultado.append(texto)
        return resultado

    @staticmethod
    def _sanitize_value(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, Mapping):
            return {str(k): ProxyAPI._sanitize_value(v) for k, v in value.items()}
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
            return [ProxyAPI._sanitize_value(item) for item in value]
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()  # datetime e similares
            except Exception:
                pass
        return str(value)

    def _serialize_entries(self, entries: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            sanitized = {str(key): self._sanitize_value(val) for key, val in entry.items()}
            serialized.append(sanitized)
        return serialized

    @staticmethod
    def _log_exception(message: str) -> None:
        logger = getattr(current_app, "logger", None)
        if logger:
            logger.exception(message)

    @staticmethod
    def _json_error(message: str, status_code: int) -> Response:
        resposta = jsonify({"error": {"message": message}})
        resposta.status_code = status_code
        return resposta
