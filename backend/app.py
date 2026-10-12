from __future__ import annotations

import os
import sys
import threading
import webbrowser
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO


@dataclass
class Ticket:
    number: int
    status: str = "waiting"
    desk_id: int | None = None


class QueueManager:
    """Thread-safe, in-memory ticket queue for four service desks."""

    def __init__(self, desk_count: int = 4) -> None:
        self.desk_count = desk_count
        self._lock = threading.RLock()
        self.reset()

    def reset(self) -> dict:
        with self._lock:
            self._next_number = 1
            self._waiting: deque[Ticket] = deque()
            self._desks: dict[int, Ticket | None] = {
                desk_id: None for desk_id in range(1, self.desk_count + 1)
            }
            self._completed: list[Ticket] = []
            return self.snapshot()

    def create_ticket(self) -> tuple[Ticket, dict]:
        with self._lock:
            ticket = Ticket(number=self._next_number)
            self._next_number += 1

            free_desk = next(
                (desk_id for desk_id, current in self._desks.items() if current is None),
                None,
            )
            if free_desk is None:
                self._waiting.append(ticket)
            else:
                ticket.status = "serving"
                ticket.desk_id = free_desk
                self._desks[free_desk] = ticket
            return ticket, self.snapshot()

    def finish_service(self, desk_id: int) -> tuple[Ticket, Ticket | None, dict]:
        with self._lock:
            self._validate_desk(desk_id)
            completed = self._desks[desk_id]
            if completed is None:
                raise ValueError(f"La mesa {desk_id} ya está disponible")

            completed.status = "completed"
            self._completed.append(completed)
            self._desks[desk_id] = None

            next_ticket = None
            if self._waiting:
                next_ticket = self._waiting.popleft()
                next_ticket.status = "serving"
                next_ticket.desk_id = desk_id
                self._desks[desk_id] = next_ticket
            return completed, next_ticket, self.snapshot()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "next_ticket": self._next_number,
                "waiting": [asdict(ticket) for ticket in self._waiting],
                "desks": [
                    {
                        "id": desk_id,
                        "ticket": asdict(ticket) if ticket else None,
                    }
                    for desk_id, ticket in self._desks.items()
                ],
                "completed_count": len(self._completed),
                "last_completed": (
                    asdict(self._completed[-1]) if self._completed else None
                ),
            }

    def _validate_desk(self, desk_id: int) -> None:
        if desk_id not in self._desks:
            raise KeyError(f"La mesa {desk_id} no existe")


ROOT_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist" / "frontend" / "browser"


def create_app(manager: QueueManager | None = None) -> tuple[Flask, SocketIO]:
    app = Flask(__name__, static_folder=None)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "local-development")
    queue_manager = manager or QueueManager()
    allowed_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "*")
    cors_origins: str | list[str] = (
        "*"
        if allowed_origins == "*"
        else [origin.strip() for origin in allowed_origins.split(",") if origin.strip()]
    )
    CORS(app, resources={r"/api/*": {"origins": cors_origins}})
    socketio = SocketIO(
        app,
        cors_allowed_origins=cors_origins,
        async_mode="threading",
    )

    def publish(state: dict) -> None:
        socketio.emit("queue_updated", state)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/state")
    def state():
        return jsonify(queue_manager.snapshot())

    @app.post("/api/tickets")
    def create_ticket_endpoint():
        ticket, current_state = queue_manager.create_ticket()
        publish(current_state)
        return jsonify({"ticket": asdict(ticket), "state": current_state}), 201

    @app.post("/api/desks/<int:desk_id>/finish")
    def finish_service_endpoint(desk_id: int):
        try:
            completed, assigned, current_state = queue_manager.finish_service(desk_id)
        except (KeyError, ValueError) as error:
            return jsonify({"error": str(error)}), 409
        publish(current_state)
        return jsonify(
            {
                "completed": asdict(completed),
                "assigned": asdict(assigned) if assigned else None,
                "state": current_state,
            }
        )

    @app.post("/api/reset")
    def reset_endpoint():
        if request.headers.get("X-Confirm-Reset") != "true":
            return jsonify({"error": "Se requiere confirmación"}), 400
        current_state = queue_manager.reset()
        publish(current_state)
        return jsonify(current_state)

    @app.get("/")
    @app.get("/<path:path>")
    def angular_app(path: str = ""):
        requested = FRONTEND_DIST / path
        if path and requested.is_file():
            return send_from_directory(FRONTEND_DIST, path)
        index = FRONTEND_DIST / "index.html"
        if index.is_file():
            return send_from_directory(FRONTEND_DIST, "index.html")
        return jsonify(
            {
                "message": "Frontend aún no compilado",
                "hint": "Ejecuta npm run build dentro de frontend",
            }
        ), 503

    app.extensions["queue_manager"] = queue_manager
    return app, socketio


app, socketio = create_app()

if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))

