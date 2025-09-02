from __future__ import annotations
import asyncio
import argparse
import signal
from typing import Optional

from src.nodo import Node  # usa from src.node import Node si tu archivo se llama node.py

async def _run_node(env_path: Optional[str],
                    send_dst: Optional[str],
                    send_body: str,
                    show_table: bool,
                    wait_secs: float) -> None:
    node = Node(env_path=env_path)
    await node.start()

    # Mostrar tabla de ruteo (dar tiempo a que circulen HELLO/INFO y LSR recalcule)
    if show_table and node.state:
        await asyncio.sleep(wait_secs)
        await node.state.print_routing_table()

    # Si pidieron enviar un mensaje al arrancar
    if send_dst:
        await node.send_message(send_dst, send_body)

    # Espera hasta Ctrl+C
    stop_event = asyncio.Event()

    def _graceful_stop(*_):
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _graceful_stop)
        except NotImplementedError:
            # Windows no soporta signal handlers en ProactorEventLoop
            pass

    await stop_event.wait()
    await node.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Runner para nodo LSR con Redis Pub/Sub"
    )
    parser.add_argument(
        "--env",
        dest="env_path",
        default=None,
        help="Ruta al archivo .env (si no, usa ./.env)"
    )
    parser.add_argument(
        "--send",
        dest="send_dst",
        default=None,
        help="Destino del mensaje (ID del nodo). Si se omite, no envía nada al iniciar."
    )
    parser.add_argument(
        "--body",
        dest="send_body",
        default="hola",
        help="Cuerpo del mensaje a enviar con --send (por defecto: 'hola')"
    )
    parser.add_argument(
        "--show-table",
        action="store_true",
        help="Imprime la tabla de ruteo tras iniciar (espera unos segundos primero)."
    )
    parser.add_argument(
        "--wait",
        dest="wait_secs",
        type=float,
        default=8.0,
        help="Segundos a esperar antes de imprimir la tabla (por defecto: 8.0)."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(_run_node(
        args.env_path,
        args.send_dst,
        args.send_body,
        args.show_table,
        args.wait_secs
    ))


if __name__ == "__main__":
    main()
