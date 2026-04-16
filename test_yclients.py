import asyncio
from datetime import datetime, timedelta

from src.services.yclients import YClientsClient


async def test_client_init() -> None:
    client = YClientsClient()
    assert client.base_url.startswith("https://")
    assert client.branch_id >= 1
    await client.close()


async def test_rate_limit_tracking() -> None:
    client = YClientsClient()
    client._max_requests_per_minute = 5
    for _ in range(5):
        await client._check_rate_limit()
    assert len(client._request_times) == 5
    await client.close()


async def test_get_records_mapping() -> None:
    client = YClientsClient()

    async def fake_collect_paginated(endpoint: str, params: dict):
        assert endpoint == "/visits"
        assert params["branch_id"] == client.branch_id
        return [
            {
                "id": 123,
                "start": "2026-04-12 10:30:00",
                "patient": {"id": 10, "fname": "Иван", "lname": "Иванов", "phone": "+79991234567"},
                "doctor": {"id": 3, "fname": "Анна", "lname": "Петрова"},
                "is_cancelled": False,
            }
        ]

    client._collect_paginated = fake_collect_paginated  # type: ignore[method-assign]

    now = datetime.now()
    records = await client.get_records(now, now + timedelta(days=1))
    assert len(records) == 1
    rec = records[0]
    assert rec["id"] == 123
    assert rec["client"]["id"] == 10
    assert rec["staff"]["id"] == 3
    assert rec["datetime"].startswith("2026-04-12T10:30:00")
    await client.close()


async def test_find_client_match_by_phone() -> None:
    client = YClientsClient()

    async def fake_make_request(method: str, endpoint: str, **kwargs):
        assert method == "GET"
        assert endpoint == "/patients"
        return {
            "data": [
                {"id": 1, "fname": "Петр", "lname": "Сидоров", "phone": "+79990000001", "email": "a@a.com"},
                {"id": 2, "fname": "Иван", "lname": "Иванов", "phone": "+79991234567", "email": "b@b.com"},
            ]
        }

    client._make_request = fake_make_request  # type: ignore[method-assign]
    found = await client.find_client(phone="+7 (999) 123-45-67")
    assert found is not None
    assert found["id"] == 2
    assert "Иванов" in found["name"]
    await client.close()


async def main() -> None:
    await test_client_init()
    await test_rate_limit_tracking()
    await test_get_records_mapping()
    await test_find_client_match_by_phone()
    print("PASS: Dentist plus client tests")


if __name__ == "__main__":
    asyncio.run(main())