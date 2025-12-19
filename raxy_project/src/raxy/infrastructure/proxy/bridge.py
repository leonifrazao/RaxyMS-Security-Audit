# -*- coding: utf-8 -*-
"""
Gerenciador de pontes HTTP locais usando Xray/V2Ray.

Este módulo é responsável por:
- Localizar o binário do Xray/V2Ray
- Criar configurações de ponte HTTP
- Gerenciar processos Xray (iniciar, parar, rotacionar)
- Alocar portas TCP disponíveis
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from raxy.infrastructure.proxy.models import BridgeRuntime, Outbound
from raxy.infrastructure.proxy.utils import decode_bytes


class XrayBridgeManager:
    """
    Gerencia pontes HTTP locais usando Xray/V2Ray.
    
    Cria processos Xray que atuam como proxies HTTP locais,
    redirecionando tráfego para proxies V2Ray remotas.
    
    Attributes:
        base_port: Porta base para alocação (não mais usado)
        bridges: Lista de pontes ativas
        
    Example:
        >>> manager = XrayBridgeManager()
        >>> bridge = manager.create_bridge(outbound, timeout=5.0)
        >>> print(bridge.url)  # http://127.0.0.1:54321
        >>> manager.stop_all()
    """
    
    def __init__(self) -> None:
        """Inicializa o gerenciador de pontes."""
        self._bridges: List[BridgeRuntime] = []
        self._running = False
        self._atexit_registered = False
        self._stop_event = threading.Event()
        self._wait_thread: Optional[threading.Thread] = None
        self._port_allocation_lock = threading.Lock()
        self._allocated_ports: set[int] = set()
    
    @property
    def bridges(self) -> List[BridgeRuntime]:
        """Retorna lista de pontes ativas."""
        return self._bridges.copy()
    
    @property
    def is_running(self) -> bool:
        """Indica se há pontes em execução."""
        return self._running
    
    def find_available_port(self) -> int:
        """
        Encontra uma porta TCP disponível.
        
        Usa o SO para alocar uma porta livre dinamicamente.
        
        Returns:
            Número da porta disponível
            
        Raises:
            RuntimeError: Se não conseguir alocar porta
        """
        with self._port_allocation_lock:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
                
                if port in self._allocated_ports:
                    return self.find_available_port()
                
                self._allocated_ports.add(port)
                return port
            except OSError as e:
                raise RuntimeError(
                    "Não foi possível alocar uma porta TCP disponível."
                ) from e
            finally:
                sock.close()
    
    def release_port(self, port: Optional[int]) -> None:
        """
        Libera uma porta registrada.
        
        Args:
            port: Porta para liberar
        """
        if port is None:
            return
        with self._port_allocation_lock:
            self._allocated_ports.discard(port)
    
    @staticmethod
    def which_xray() -> str:
        """
        Descobre o binário do Xray/V2Ray.
        
        Verifica variável XRAY_PATH primeiro, depois procura
        no PATH do sistema.
        
        Returns:
            Caminho para o executável
            
        Raises:
            FileNotFoundError: Se não encontrar o binário
        """
        env_path = os.environ.get("XRAY_PATH")
        if env_path and Path(env_path).exists():
            return env_path
        
        for candidate in ("xray", "xray.exe", "v2ray", "v2ray.exe"):
            found = shutil.which(candidate)
            if found:
                return found
        
        raise FileNotFoundError(
            "Não foi possível localizar o binário do Xray/V2Ray. "
            "Instale o xray-core ou configure XRAY_PATH."
        )
    
    def make_xray_config(
        self, 
        port: int, 
        outbound: Outbound
    ) -> Dict[str, Any]:
        """
        Monta configuração do Xray para uma ponte HTTP local.
        
        Args:
            port: Porta local para a ponte
            outbound: Configuração do outbound
            
        Returns:
            Dict com configuração completa do Xray
        """
        cfg: Dict[str, Any] = {
            "log": {"loglevel": "warning"},
            "inbounds": [{
                "tag": "http-in",
                "listen": "127.0.0.1",
                "port": port,
                "protocol": "http",
                "settings": {}
            }],
            "outbounds": [
                outbound.config,
                {"tag": "direct", "protocol": "freedom", "settings": {}},
                {"tag": "block", "protocol": "blackhole", "settings": {}}
            ],
            "routing": {
                "domainStrategy": "AsIs",
                "rules": [
                    {"type": "field", "outboundTag": outbound.tag, "network": "tcp,udp"}
                ]
            }
        }
        
        if "tag" not in cfg["outbounds"][0]:
            cfg["outbounds"][0]["tag"] = outbound.tag
        
        return cfg
    
    def launch_bridge(
        self, 
        xray_bin: str, 
        cfg: Dict[str, Any], 
        name: str
    ) -> Tuple[subprocess.Popen[bytes], Path]:
        """
        Inicializa o Xray com captura de stdout/stderr.
        
        Args:
            xray_bin: Caminho para o binário Xray
            cfg: Configuração JSON
            name: Nome para o diretório temporário
            
        Returns:
            Tuple de (processo, caminho do config)
        """
        tmpdir = Path(tempfile.mkdtemp(prefix=f"xray_{name}_"))
        cfg_path = tmpdir / "config.json"
        cfg_path.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), 
            encoding="utf-8"
        )

        proc = subprocess.Popen(
            [xray_bin, "-config", str(cfg_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return proc, cfg_path
    
    def create_bridge(
        self,
        outbound: Outbound,
        raw_uri: str,
        *,
        xray_bin: Optional[str] = None
    ) -> BridgeRuntime:
        """
        Cria uma nova ponte HTTP para um outbound.
        
        Args:
            outbound: Configuração do outbound
            raw_uri: URI original do proxy
            xray_bin: Caminho do binário (opcional)
            
        Returns:
            BridgeRuntime com a ponte criada
        """
        if xray_bin is None:
            xray_bin = self.which_xray()
        
        port = self.find_available_port()
        cfg = self.make_xray_config(port, outbound)
        scheme = raw_uri.split("://", 1)[0].lower()
        
        proc, cfg_path = self.launch_bridge(xray_bin, cfg, outbound.tag)
        
        bridge = BridgeRuntime(
            tag=outbound.tag,
            port=port,
            scheme=scheme,
            uri=raw_uri,
            process=proc,
            workdir=cfg_path.parent,
        )
        
        self._bridges.append(bridge)
        self._running = True
        
        return bridge
    
    def create_bridges(
        self,
        outbounds_with_uri: List[Tuple[str, Outbound]],
        *,
        xray_bin: Optional[str] = None
    ) -> List[BridgeRuntime]:
        """
        Cria múltiplas pontes HTTP.
        
        Args:
            outbounds_with_uri: Lista de (uri, outbound) tuples
            xray_bin: Caminho do binário (opcional)
            
        Returns:
            Lista de BridgeRuntime criados
        """
        if xray_bin is None:
            xray_bin = self.which_xray()
        
        bridges = []
        try:
            for raw_uri, outbound in outbounds_with_uri:
                bridge = self.create_bridge(outbound, raw_uri, xray_bin=xray_bin)
                bridges.append(bridge)
        except Exception:
            # Em caso de erro, limpa bridges já criados
            for bridge in bridges:
                self.stop_bridge(bridge)
            raise
        
        if not self._atexit_registered:
            atexit.register(self.stop_all)
            self._atexit_registered = True
        
        return bridges
    
    def stop_bridge(self, bridge: BridgeRuntime) -> None:
        """
        Para uma ponte específica.
        
        Args:
            bridge: Ponte para parar
        """
        self._terminate_process(bridge.process)
        self._safe_remove_dir(bridge.workdir)
        self.release_port(bridge.port)
        
        if bridge in self._bridges:
            self._bridges.remove(bridge)
        
        if not self._bridges:
            self._running = False
    
    def stop_all(self) -> None:
        """Para todas as pontes ativas."""
        if not self._running and not self._bridges:
            return

        self._stop_event.set()
        
        bridges_to_stop = list(self._bridges)
        for bridge in bridges_to_stop:
            self._terminate_process(bridge.process)
            self._safe_remove_dir(bridge.workdir)
            self.release_port(bridge.port)

        self._bridges = []
        self._running = False

        if self._wait_thread and self._wait_thread is not threading.current_thread():
            self._wait_thread.join(timeout=1.0)
        self._wait_thread = None
    
    def wait(self, console: Optional[Any] = None) -> None:
        """
        Bloqueia até que todas as pontes terminem ou stop seja chamado.
        
        Args:
            console: Console Rich para mensagens (opcional)
        """
        if not self._running:
            raise RuntimeError("Nenhuma ponte ativa para aguardar.")
        
        try:
            while not self._stop_event.is_set():
                alive = any(
                    bridge.process and bridge.process.poll() is None
                    for bridge in self._bridges
                )
                if not alive:
                    if console:
                        console.print("\n[yellow]Todos os processos xray finalizaram.[/yellow]")
                    break
                time.sleep(0.5)
        except KeyboardInterrupt:
            if console:
                console.print("\n[yellow]Interrupção recebida, encerrando pontes...[/yellow]")
        finally:
            self.stop_all()
    
    def start_wait_thread(self) -> None:
        """Dispara thread em segundo plano para monitorar processos."""
        if self._wait_thread and self._wait_thread.is_alive():
            return
        
        thread = threading.Thread(
            target=self._wait_loop_wrapper, 
            name="ProxyWaitThread", 
            daemon=True
        )
        self._wait_thread = thread
        thread.start()
    
    def _wait_loop_wrapper(self) -> None:
        """Executa wait capturando exceções para término limpo da thread."""
        try:
            self.wait()
        except RuntimeError:
            pass
    
    def rotate_bridge(
        self, 
        bridge_id: int, 
        new_outbound: Outbound,
        new_uri: str
    ) -> Optional[BridgeRuntime]:
        """
        Rotaciona a proxy de uma ponte para outra.
        
        Args:
            bridge_id: ID da ponte a rotacionar
            new_outbound: Novo outbound a usar
            new_uri: Nova URI
            
        Returns:
            Nova BridgeRuntime ou None se falhou
        """
        if not self._running or not (0 <= bridge_id < len(self._bridges)):
            return None
        
        old_bridge = self._bridges[bridge_id]
        old_port = old_bridge.port
        
        # Para a ponte antiga (mas mantém a porta)
        self._terminate_process(old_bridge.process)
        self._safe_remove_dir(old_bridge.workdir)
        
        try:
            xray_bin = self.which_xray()
            cfg = self.make_xray_config(old_port, new_outbound)
            new_scheme = new_uri.split("://", 1)[0].lower()
            
            new_proc, new_cfg_path = self.launch_bridge(xray_bin, cfg, new_outbound.tag)
            
            new_bridge = BridgeRuntime(
                tag=new_outbound.tag,
                port=old_port,
                scheme=new_scheme,
                uri=new_uri,
                process=new_proc,
                workdir=new_cfg_path.parent,
            )
            
            self._bridges[bridge_id] = new_bridge
            return new_bridge
            
        except Exception:
            # Marca como inativa
            old_bridge.process = None
            return None
    
    @staticmethod
    def _terminate_process(
        proc: Optional[subprocess.Popen[bytes]], 
        *, 
        wait_timeout: float = 3.0
    ) -> None:
        """Finaliza um processo de forma silenciosa."""
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=wait_timeout)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    
    @staticmethod
    def _safe_remove_dir(path: Optional[Path]) -> None:
        """Remove diretórios temporários sem propagar exceções."""
        if path is None:
            return
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass


__all__ = ["XrayBridgeManager"]
