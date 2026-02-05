import asyncio
import logging
from datetime import datetime, timedelta

from src.services.yclients import YClientsClient, YClientsAPIError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_client_init():
    """Тест инициализации клиента"""
    client = YClientsClient()

    print(f"Base URL: {client.base_url}")
    print(f"Company ID: {client.company_id}")
    print(f"Session: {client._session}")
    print(f"Max requests/min: {client._max_requests_per_minute}")

    assert client.base_url is not None
    assert client.company_id is not None
    print("PASS: client init")

    await client.close()


async def test_headers():
    """Тест генерации заголовков"""
    client = YClientsClient()
    headers = client._get_headers()

    print(f"Headers: {headers}")

    assert "Authorization" in headers
    assert "Bearer" in headers["Authorization"]
    assert "User" in headers["Authorization"]
    assert headers["Accept"] == "application/vnd.api.v2+json"
    print("PASS: headers")

    await client.close()


async def test_rate_limit():
    """Тест rate limiting"""
    client = YClientsClient()
    client._max_requests_per_minute = 5  # Снижаем для теста

    # Добавляем 5 запросов
    for i in range(5):
        await client._check_rate_limit()

    print(f"Recorded requests: {len(client._request_times)}")
    assert len(client._request_times) == 5
    print("PASS: rate limit tracking")

    await client.close()


async def test_api_connection():
    """Тест подключения к реальному API (нужны токены)"""
    client = YClientsClient()

    try:
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        records = await client.get_records(
            start_date=today,
            end_date=tomorrow,
        )
        print(f"Records found: {len(records)}")
        if records:
            print(f"First record keys: {records[0].keys()}")
        print("PASS: api connection")

    except YClientsAPIError as e:
        print(f"API Error (expected if no tokens): {e}")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        await client.close()


async def main():
    print("=== Test 1: Client Init ===")
    await test_client_init()

    print("\n=== Test 2: Headers ===")
    await test_headers()

    print("\n=== Test 3: Rate Limit ===")
    await test_rate_limit()

    print("\n=== Test 4: API Connection ===")
    await test_api_connection()

    print("\n=== All tests completed ===")


if __name__ == "__main__":
    asyncio.run(main())