from typing import Any, Dict, Optional
from botasaurus.request import Request, request as botasaurus_request
from raxy.core.domain.proxy import Proxy


class BotasaurusHttpClient:
    """
    HTTP Client implementation using Botasaurus.
    Adapts the logic from the original RequestExecutor.
    """

    def __init__(
        self, 
        proxy: Proxy | dict | None = None,
        cookies: dict[str, str] | None = None,
        user_agent: str | None = None
    ):
        self.cookies = cookies or {}
        self.user_agent = user_agent
        
        # Normalize proxy
        if isinstance(proxy, dict):
            self.proxy = Proxy(
                id=proxy.get("id", ""),
                url=proxy.get("url", ""),
                type=proxy.get("type", "http"),
                country=proxy.get("country"),
                city=proxy.get("city")
            )
        elif isinstance(proxy, Proxy):
            self.proxy = proxy
        else:
            self.proxy = Proxy(id="", url="")

    def update_session(
        self,
        cookies: dict[str, str] | None = None,
        user_agent: str | None = None
    ):
        """Updates session state (cookies, UA)."""
        if cookies is not None:
            self.cookies = cookies
        if user_agent is not None:
            self.user_agent = user_agent

    def execute(
        self, 
        method: str, 
        url: str, 
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        json: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs: Any
    ) -> Any:
        """
        Executes a request using Botasaurus.
        """
        # Prepare headers
        final_headers = headers.copy() if headers else {}
        if self.user_agent:
            final_headers.setdefault("User-Agent", self.user_agent)
        
        # Build request args dict
        req_data = {
            "method": method.lower(),
            "url": url,
            "params": params,
            "data": data,
            "json_data": json,  # Renamed to avoid conflict
            "headers": final_headers,
            "cookies": self.cookies,
        }

        # Execute via static decorated method
        proxy_url = self.proxy.url if self.proxy.is_valid else None
        return _send_request(req_data, proxy=proxy_url)

    def get(self, url: str, **kwargs: Any) -> Any:
        return self.execute("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Any:
        return self.execute("POST", url, **kwargs)


@botasaurus_request(cache=False, raise_exception=True, create_error_logs=False, output=None, max_retry=3, retry_wait=2)
def _send_request(req: Request, data: dict, proxy: str | None = None):
    """
    Module-level function decorated with botasaurus request.
    The decorator passes (Request, data_dict, proxy=...).
    """
    method = data["method"]
    url = data["url"]
    
    # Build kwargs for the request
    kwargs = {}
    if data.get("params"):
        kwargs["params"] = data["params"]
    if data.get("data"):
        kwargs["data"] = data["data"]
    if data.get("json_data"):
        kwargs["json"] = data["json_data"]
    if data.get("headers"):
        kwargs["headers"] = data["headers"]
    if data.get("cookies"):
        kwargs["cookies"] = data["cookies"]
    
    # Botasaurus request object has methods like .get(), .post()
    request_method = getattr(req, method)
    return request_method(url, **kwargs)
