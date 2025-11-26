# {{ service.name }} gRPC Client Examples

This document provides client implementation examples for the {{ service.name }} gRPC service.

**Service:** {{ service.name }}
**Version:** {{ service.version }}
**Generated:** {{ timestamp }}

## Python Client

```python
import grpc
import {{ service.name.lower() }}_pb2
import {{ service.name.lower() }}_pb2_grpc

def create_client():
    # Create channel
    channel = grpc.insecure_channel('localhost:50051')

    # Create stub
    stub = {{ service.name.lower() }}_pb2_grpc.{{ service.name }}Stub(channel)

    return stub

{% for method in service.grpc_methods %}
def {{ method.name.lower() }}(stub):
    """Call {{ method.name }} method."""
    {% if method.streaming == 'unary' %}
    # Create request
    request = {{ service.name.lower() }}_pb2.{{ method.input_type }}()
    # TODO: Set request fields

    # Make call
    response = stub.{{ method.name }}(request)
    return response
    {% elif method.streaming == 'client_streaming' %}
    # Create request generator
    def request_generator():
        for i in range(10):  # Example: send 10 requests
            request = {{ service.name.lower() }}_pb2.{{ method.input_type }}()
            # TODO: Set request fields
            yield request

    # Make streaming call
    response = stub.{{ method.name }}(request_generator())
    return response
    {% elif method.streaming == 'server_streaming' %}
    # Create request
    request = {{ service.name.lower() }}_pb2.{{ method.input_type }}()
    # TODO: Set request fields

    # Make streaming call
    responses = stub.{{ method.name }}(request)
    for response in responses:
        print(response)
    {% elif method.streaming == 'bidirectional' %}
    # Create request generator
    def request_generator():
        for i in range(10):  # Example: send 10 requests
            request = {{ service.name.lower() }}_pb2.{{ method.input_type }}()
            # TODO: Set request fields
            yield request

    # Make bidirectional streaming call
    responses = stub.{{ method.name }}(request_generator())
    for response in responses:
        print(response)
    {% endif %}

{% endfor %}

# Example usage
if __name__ == '__main__':
    stub = create_client()
    {% for method in service.grpc_methods %}
    {{ method.name.lower() }}(stub)
    {% endfor %}
```

## JavaScript/Node.js Client

```javascript
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');

// Load proto file
const packageDefinition = protoLoader.loadSync('{{ service.name.lower() }}.proto', {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true
});

const {{ service.name.lower() }}Proto = grpc.loadPackageDefinition(packageDefinition);

// Create client
const client = new {{ service.name.lower() }}Proto.{{ service.name }}('localhost:50051', grpc.credentials.createInsecure());

{% for method in service.grpc_methods %}
// {{ method.name }} method
{% if method.streaming == 'unary' %}
function {{ method.name.lower() }}() {
    const request = {
        // TODO: Set request fields
    };

    client.{{ method.name }}(request, (error, response) => {
        if (error) {
            console.error('Error:', error);
        } else {
            console.log('Response:', response);
        }
    });
}
{% elif method.streaming == 'client_streaming' %}
function {{ method.name.lower() }}() {
    const call = client.{{ method.name }}((error, response) => {
        if (error) {
            console.error('Error:', error);
        } else {
            console.log('Response:', response);
        }
    });

    // Send multiple requests
    for (let i = 0; i < 10; i++) {
        call.write({
            // TODO: Set request fields
        });
    }
    call.end();
}
{% elif method.streaming == 'server_streaming' %}
function {{ method.name.lower() }}() {
    const request = {
        // TODO: Set request fields
    };

    const call = client.{{ method.name }}(request);

    call.on('data', (response) => {
        console.log('Response:', response);
    });

    call.on('end', () => {
        console.log('Stream ended');
    });

    call.on('error', (error) => {
        console.error('Error:', error);
    });
}
{% elif method.streaming == 'bidirectional' %}
function {{ method.name.lower() }}() {
    const call = client.{{ method.name }}();

    call.on('data', (response) => {
        console.log('Response:', response);
    });

    call.on('end', () => {
        console.log('Stream ended');
    });

    call.on('error', (error) => {
        console.error('Error:', error);
    });

    // Send multiple requests
    for (let i = 0; i < 10; i++) {
        call.write({
            // TODO: Set request fields
        });
    }
    call.end();
}
{% endif %}

{% endfor %}
```

## Go Client

```go
package main

import (
    "context"
    "log"
    "time"

    "google.golang.org/grpc"
    pb "path/to/{{ service.name.lower() }}"
)

func main() {
    // Set up connection
    conn, err := grpc.Dial("localhost:50051", grpc.WithInsecure())
    if err != nil {
        log.Fatalf("Failed to connect: %v", err)
    }
    defer conn.Close()

    // Create client
    client := pb.New{{ service.name }}Client(conn)

    ctx, cancel := context.WithTimeout(context.Background(), time.Second)
    defer cancel()

    {% for method in service.grpc_methods %}
    // {{ method.name }} method
    {% if method.streaming == 'unary' %}
    req := &pb.{{ method.input_type }}{
        // TODO: Set request fields
    }

    resp, err := client.{{ method.name }}(ctx, req)
    if err != nil {
        log.Fatalf("{{ method.name }} failed: %v", err)
    }
    log.Printf("Response: %v", resp)
    {% endif %}

    {% endfor %}
}
```

## Java Client

```java
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import {{ service.name.lower() }}.{{ service.name }}Grpc;
import {{ service.name.lower() }}.{{ method.input_type }};
import {{ service.name.lower() }}.{{ method.output_type }};

public class {{ service.name }}Client {

    private final ManagedChannel channel;
    private final {{ service.name }}Grpc.{{ service.name }}BlockingStub blockingStub;

    public {{ service.name }}Client(String host, int port) {
        channel = ManagedChannelBuilder.forAddress(host, port)
                .usePlaintext()
                .build();
        blockingStub = {{ service.name }}Grpc.newBlockingStub(channel);
    }

    {% for method in service.grpc_methods %}
    {% if method.streaming == 'unary' %}
    public {{ method.output_type }} {{ method.name.lower() }}() {
        {{ method.input_type }} request = {{ method.input_type }}.newBuilder()
                // TODO: Set request fields
                .build();

        return blockingStub.{{ method.name.lower() }}(request);
    }
    {% endif %}

    {% endfor %}

    public void shutdown() throws InterruptedException {
        channel.shutdown().awaitTermination(5, TimeUnit.SECONDS);
    }

    public static void main(String[] args) throws Exception {
        {{ service.name }}Client client = new {{ service.name }}Client("localhost", 50051);
        try {
            {% for method in service.grpc_methods %}
            {% if method.streaming == 'unary' %}
            {{ method.output_type }} response = client.{{ method.name.lower() }}();
            System.out.println("Response: " + response);
            {% endif %}
            {% endfor %}
        } finally {
            client.shutdown();
        }
    }
}
```

## Error Handling

### Python

```python
import grpc

try:
    response = stub.{{ service.grpc_methods[0].name if service.grpc_methods }}(request)
except grpc.RpcError as e:
    print(f"gRPC error: {e.code()}: {e.details()}")
```

### JavaScript

```javascript
client.{{ service.grpc_methods[0].name if service.grpc_methods }}(request, (error, response) => {
    if (error) {
        console.error(`gRPC error: ${error.code}: ${error.details}`);
    }
});
```

### Go

```go
resp, err := client.{{ service.grpc_methods[0].name if service.grpc_methods }}(ctx, req)
if err != nil {
    if st, ok := status.FromError(err); ok {
        log.Printf("gRPC error: %s: %s", st.Code(), st.Message())
    }
}
```

## Configuration

### TLS/SSL Configuration

#### Python

```python
import grpc
import ssl

# Create SSL credentials
credentials = grpc.ssl_channel_credentials()
channel = grpc.secure_channel('your-service:443', credentials)
```

#### JavaScript

```javascript
const fs = require('fs');
const grpc = require('@grpc/grpc-js');

// Create SSL credentials
const credentials = grpc.credentials.createSsl(
    fs.readFileSync('ca-cert.pem'),
    fs.readFileSync('client-key.pem'),
    fs.readFileSync('client-cert.pem')
);

const client = new serviceProto.{{ service.name }}('your-service:443', credentials);
```

### Authentication

#### Metadata (Python)

```python
import grpc

# Add metadata for authentication
metadata = [('authorization', 'Bearer your-token')]
response = stub.{{ service.grpc_methods[0].name if service.grpc_methods }}(request, metadata=metadata)
```

#### Interceptors (JavaScript)

```javascript
const authInterceptor = (options, nextCall) => {
    return new grpc.InterceptingCall(nextCall(options), {
        start: (metadata, listener, next) => {
            metadata.add('authorization', 'Bearer your-token');
            next(metadata, listener);
        }
    });
};

const client = new serviceProto.{{ service.name }}('localhost:50051',
    grpc.credentials.createInsecure(),
    { interceptors: [authInterceptor] }
);
```
