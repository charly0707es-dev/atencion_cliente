from backend.app import QueueManager, create_app


def test_assigns_first_four_tickets_and_queues_the_fifth():
    manager = QueueManager()
    for expected_desk in range(1, 5):
        ticket, _ = manager.create_ticket()
        assert ticket.number == expected_desk
        assert ticket.desk_id == expected_desk
        assert ticket.status == "serving"

    fifth, state = manager.create_ticket()
    assert fifth.number == 5
    assert fifth.status == "waiting"
    assert fifth.desk_id is None
    assert [ticket["number"] for ticket in state["waiting"]] == [5]


def test_next_waiting_ticket_uses_the_first_desk_that_becomes_free():
    manager = QueueManager()
    for _ in range(6):
        manager.create_ticket()

    completed, assigned, state = manager.finish_service(3)
    assert completed.number == 3
    assert assigned is not None
    assert assigned.number == 5
    assert assigned.desk_id == 3
    assert state["desks"][2]["ticket"]["number"] == 5
    assert [ticket["number"] for ticket in state["waiting"]] == [6]

    _, assigned, state = manager.finish_service(2)
    assert assigned is not None
    assert assigned.number == 6
    assert assigned.desk_id == 2
    assert state["waiting"] == []


def test_api_full_flow():
    flask_app, _ = create_app(QueueManager())
    client = flask_app.test_client()

    assert client.get("/api/health").get_json() == {"status": "ok"}
    for _ in range(5):
        assert client.post("/api/tickets").status_code == 201

    response = client.post("/api/desks/4/finish")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["assigned"]["number"] == 5
    assert payload["assigned"]["desk_id"] == 4

    assert client.post("/api/reset").status_code == 400
    reset = client.post("/api/reset", headers={"X-Confirm-Reset": "true"})
    assert reset.status_code == 200
    assert reset.get_json()["next_ticket"] == 1

