import httpx
import pytest
from pact import Pact


@pytest.mark.contract
def test_pact_poc():
    """
    Proof of Concept for Consumer-Driven Contract Testing using Pact (v3).

    This test demonstrates how to define a contract between a Consumer and a Provider.
    The Consumer defines the expected interaction (request & response), and Pact
    verifies that the Consumer's expectations are met by the mock provider.
    """

    # Define the consumer and provider
    pact = Pact("OrderService", "UserService")

    expected_user = {"id": 1, "name": "John Doe", "email": "john@example.com"}

    # Define the expected interaction
    (
        pact.upon_receiving("a request for User 1")
        .given("User 1 exists")
        .with_request("GET", "/users/1")
        .will_respond_with(200)
        .with_body(expected_user)
    )

    # Verify the interaction
    with pact.serve() as srv:
        # Act: Make the request to the mock service provided by Pact
        # In a real scenario, this would be your service client code
        # Note: srv.url provides the mock server URL
        response = httpx.get(f"{srv.url}/users/1")

        # Assert: Check if the response matches what we expect
        assert response.status_code == 200
        assert response.json() == expected_user
