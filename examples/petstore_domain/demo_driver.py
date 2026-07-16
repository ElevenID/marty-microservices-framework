import asyncio
import random
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

console = Console()

PET_SERVICE_URL = "http://localhost:8000"
STORE_SERVICE_URL = "http://localhost:8001"
DELIVERY_SERVICE_URL = "http://localhost:8002"
JWT_SECRET = "development_secret_key"  # pragma: allowlist secret

def generate_token():
    payload = {
        "sub": "demo_user",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "roles": ["user"]
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type(httpx.ConnectError))
async def create_pet(client, name, species):
    try:
        response = await client.post(
            f"{PET_SERVICE_URL}/pets",
            json={"name": name, "species": species, "age": random.randint(1, 10)}
        )
        return response.json() if response.status_code == 201 else None
    except httpx.ConnectError:
        console.print(f"[yellow]Warning: Pet Service not reachable, retrying...[/yellow]")
        raise

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type(httpx.ConnectError))
async def create_order(client, pet_id):
    headers = {"Authorization": f"Bearer {generate_token()}"}
    try:
        response = await client.post(
            f"{STORE_SERVICE_URL}/store/orders",
            json={
                "pet_id": pet_id,
                "quantity": 1,
                "customer_name": "Demo User",
                "delivery_address": "123 Demo St, Tech City",
                "delivery_requested": True
            },
            headers=headers
        )
        if response.status_code != 201:
            console.print(f"[red]Error creating order for pet {pet_id}: {response.status_code} - {response.text}[/red]")
            return None
        return response.json()
    except httpx.ConnectError:
        console.print(f"[yellow]Warning: Store Service not reachable, retrying...[/yellow]")
        raise

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type(httpx.ConnectError))
async def check_deliveries(client):
    try:
        response = await client.get(f"{DELIVERY_SERVICE_URL}/deliveries")
        if response.status_code == 200:
            data = response.json()
            return data.get("deliveries", [])
        return []
    except httpx.ConnectError:
        console.print(f"[yellow]Warning: Delivery Service not reachable, retrying...[/yellow]")
        raise

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type(httpx.ConnectError))
async def complete_delivery(client, delivery_id):
    try:
        response = await client.post(f"{DELIVERY_SERVICE_URL}/deliveries/{delivery_id}/complete")
        if response.status_code != 200:
            console.print(f"[red]Error completing delivery {delivery_id}: {response.status_code} - {response.text}[/red]")
            return None
        return response.json()
    except httpx.ConnectError:
        console.print(f"[yellow]Warning: Delivery Service not reachable, retrying...[/yellow]")
        raise

async def run_scenario():
    async with httpx.AsyncClient() as client:
        console.print("[bold green]Starting Petstore Demo Scenario[/bold green]")

        # 1. Create Pets
        pets = []
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
            task = progress.add_task(description="Creating pets...", total=None)
            for i in range(5):
                name = f"Pet-{random.randint(1000, 9999)}"
                species = random.choice(["Dog", "Cat", "Parrot", "Hamster"])
                pet = await create_pet(client, name, species)
                if pet:
                    pets.append(pet)
                    console.print(f"  ✅ Created {species} named {name} (ID: {pet['id']})")
                else:
                    console.print(f"  ❌ Failed to create {species} named {name}")
                await asyncio.sleep(0.5)

        # 2. Place Orders
        orders = []
        # Order items that exist in the catalog (Store Service is seeded with these)
        catalog_items = [
            {"id": "corgi", "name": "Pembroke Welsh Corgi"},
            {"id": "siamese-cat", "name": "Siamese Cat"},
            {"id": "macaw", "name": "Blue and Gold Macaw"}
        ]

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
            task = progress.add_task(description="Placing orders...", total=None)
            for item in catalog_items:
                order = await create_order(client, item['id'])
                if order:
                    orders.append(order)
                    console.print(f"  ✅ Placed order for {item['name']} (Order ID: {order['order_id']})")
                else:
                    console.print(f"  ❌ Failed to place order for {item['name']}")
                await asyncio.sleep(0.5)

        # 3. Check Deliveries
        deliveries = []
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
            task = progress.add_task(description="Checking deliveries...", total=None)
            # Wait a bit for async processing if any (though here it's synchronous in the store service)
            await asyncio.sleep(1)

            deliveries = await check_deliveries(client)
            for delivery in deliveries:
                console.print(f"  🚚 Delivery found: {delivery['id']} (Status: {delivery['status']})")

                # Complete the first delivery as a test
                if delivery['status'] in ['queued', 'assigned', 'in_transit']:
                    # Note: In our simple implementation, status starts as 'queued'.
                    # Let's just try to complete it.
                    updated = await complete_delivery(client, delivery['id'])
                    if updated:
                        console.print(f"     ✅ Completed delivery {delivery['id']}")
                    else:
                        console.print(f"     ❌ Failed to complete delivery {delivery['id']}")

        # 4. Summary
        table = Table(title="Demo Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="magenta")
        table.add_row("Pets Created", str(len(pets)))
        table.add_row("Orders Placed", str(len(orders)))
        table.add_row("Deliveries Found", str(len(deliveries)))
        console.print(table)

if __name__ == "__main__":
    try:
        asyncio.run(run_scenario())
    except KeyboardInterrupt:
        console.print("\n[bold red]Demo stopped by user[/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]Error running demo: {e}[/bold red]")
