# Petstore Domain Architecture

This example shows a simple, scalable flow for a pet shop with delivery.

## Services
- **Pet Service**: Manages pet profiles (source of truth for pet records)
- **Store Service**: Customer-facing storefront that sells pets and asks the delivery board to ship orders
- **Delivery Board Service**: Manages delivery trucks, assigns capacity, and auto-scales trucks when demand spikes

## Flow
1. Browse pets via the Store Service catalog.
2. Place an order; stock is reserved in the Store Service.
3. If delivery is requested, the Store Service calls the Delivery Board to schedule a truck.
4. The Delivery Board assigns the lightest-loaded truck or auto-provisions a surge truck and returns a delivery ticket.
5. Orders can be checked later to refresh delivery status.

## Ports (defaults)
- Pet Service: `8000`
- Store Service: `8001`
- Delivery Board Service: `8002`
