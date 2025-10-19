"""
Vault configuration and deployment examples for the Marty Microservices Framework
"""

# vault-config.hcl
import os

VAULT_CONFIG = '''
ui = true

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1
}

storage "file" {
  path = "/vault/data"
}

# API address for client connections
api_addr = "http://127.0.0.1:8200"

# Enable audit logging
audit {
  file {
    file_path = "/vault/logs/audit.log"
  }
}
'''

# vault-init.sh - Vault initialization script
VAULT_INIT_SCRIPT = '''#!/bin/bash

# Start Vault server
vault server -config=/vault/config/vault.hcl &

# Wait for Vault to start
sleep 5

# Initialize Vault (do this only once)
vault operator init -key-shares=5 -key-threshold=3

# Unseal Vault (use your actual unseal keys)
vault operator unseal <UNSEAL_KEY_1>
vault operator unseal <UNSEAL_KEY_2>
vault operator unseal <UNSEAL_KEY_3>

# Enable auth methods
vault auth enable kubernetes
vault auth enable userpass
vault auth enable approle

# Enable secret engines
vault secrets enable -path=secret kv-v2
vault secrets enable -path=database database
vault secrets enable -path=pki pki
vault secrets enable -path=transit transit

# Configure PKI engine
vault secrets tune -max-lease-ttl=87600h pki
vault write pki/root/generate/internal \\
    common_name="Marty MSF Root CA" \\
    ttl=87600h

vault write pki/config/urls \\
    issuing_certificates="http://127.0.0.1:8200/v1/pki/ca" \\
    crl_distribution_points="http://127.0.0.1:8200/v1/pki/crl"

# Create role for service certificates
vault write pki/roles/marty-msf \\
    allowed_domains="marty.local,*.marty.local" \\
    allow_subdomains=true \\
    max_ttl="720h"

# Configure Kubernetes auth
vault write auth/kubernetes/config \\
    token_reviewer_jwt="$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)" \\
    kubernetes_host="https://$KUBERNETES_PORT_443_TCP_ADDR:443" \\
    kubernetes_ca_cert=@/var/run/secrets/kubernetes.io/serviceaccount/ca.crt

# Create policies
vault policy write marty-msf-policy - <<EOF
# Allow read access to secrets
path "secret/data/marty-msf/*" {
  capabilities = ["read"]
}

# Allow certificate generation
path "pki/issue/marty-msf" {
  capabilities = ["create", "update"]
}

# Allow encryption/decryption
path "transit/encrypt/marty-msf" {
  capabilities = ["create", "update"]
}

path "transit/decrypt/marty-msf" {
  capabilities = ["create", "update"]
}
EOF

# Create Kubernetes role
vault write auth/kubernetes/role/marty-msf \\
    bound_service_account_names=marty-msf \\
    bound_service_account_namespaces=default \\
    policies=marty-msf-policy \\
    ttl=24h

echo "Vault setup completed!"
'''

# Kubernetes deployment for Vault
VAULT_K8S_DEPLOYMENT = '''
apiVersion: v1
kind: ServiceAccount
metadata:
  name: vault
  namespace: default

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: vault-config
  namespace: default
data:
  vault.hcl: |
    ui = true

    listener "tcp" {
      address     = "0.0.0.0:8200"
      tls_disable = 1
    }

    storage "file" {
      path = "/vault/data"
    }

    api_addr = "http://vault:8200"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vault
  namespace: default
  labels:
    app: vault
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vault
  template:
    metadata:
      labels:
        app: vault
    spec:
      serviceAccountName: vault
      containers:
      - name: vault
        image: vault:1.15.0
        args:
          - "vault"
          - "server"
          - "-config=/vault/config/vault.hcl"
        env:
        - name: VAULT_ADDR
          value: "http://127.0.0.1:8200"
        - name: VAULT_DEV_ROOT_TOKEN_ID
          value: "hvs.dev-token"
        ports:
        - containerPort: 8200
          name: http
        volumeMounts:
        - name: vault-config
          mountPath: /vault/config
        - name: vault-data
          mountPath: /vault/data
        securityContext:
          capabilities:
            add:
              - IPC_LOCK
      volumes:
      - name: vault-config
        configMap:
          name: vault-config
      - name: vault-data
        emptyDir: {}

---
apiVersion: v1
kind: Service
metadata:
  name: vault
  namespace: default
  labels:
    app: vault
spec:
  type: ClusterIP
  ports:
  - port: 8200
    targetPort: 8200
    name: http
  selector:
    app: vault
'''

# Docker Compose for development
DOCKER_COMPOSE_VAULT = '''
version: '3.8'

services:
  vault:
    image: vault:1.15.0
    container_name: vault-dev
    ports:
      - "8200:8200"
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: hvs.dev-token
      VAULT_DEV_LISTEN_ADDRESS: 0.0.0.0:8200
    cap_add:
      - IPC_LOCK
    command: vault server -dev -dev-listen-address=0.0.0.0:8200
    volumes:
      - vault_data:/vault/data
      - ./vault-policies:/vault/policies
    networks:
      - marty-msf

  vault-ui:
    image: vault:1.15.0
    container_name: vault-ui
    depends_on:
      - vault
    environment:
      VAULT_ADDR: http://vault:8200
      VAULT_TOKEN: hvs.dev-token
    command: |
      sh -c "
        sleep 10 &&
        vault auth enable userpass &&
        vault secrets enable -path=secret kv-v2 &&
        vault policy write marty-msf-policy /vault/policies/marty-msf.hcl &&
        vault write auth/userpass/users/admin password=admin policies=marty-msf-policy
      "
    volumes:
      - ./vault-policies:/vault/policies
    networks:
      - marty-msf

volumes:
  vault_data:

networks:
  marty-msf:
    driver: bridge
'''

# Sample Vault policy
VAULT_POLICY = '''
# Marty MSF Service Policy
path "secret/data/marty-msf/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/metadata/marty-msf/*" {
  capabilities = ["list"]
}

# Database secrets
path "database/creds/marty-msf-*" {
  capabilities = ["read"]
}

# PKI certificates
path "pki/issue/marty-msf" {
  capabilities = ["create", "update"]
}

path "pki/cert/ca" {
  capabilities = ["read"]
}

# Transit encryption
path "transit/encrypt/marty-msf" {
  capabilities = ["create", "update"]
}

path "transit/decrypt/marty-msf" {
  capabilities = ["create", "update"]
}

path "transit/datakey/plaintext/marty-msf" {
  capabilities = ["create", "update"]
}

# System health
path "sys/health" {
  capabilities = ["read"]
}

# Self token operations
path "auth/token/lookup-self" {
  capabilities = ["read"]
}

path "auth/token/renew-self" {
  capabilities = ["update"]
}
'''

if __name__ == "__main__":
    # Write configuration files

    config_dir = "vault-configs"
    os.makedirs(config_dir, exist_ok=True)

    # Write Vault configuration
    with open(f"{config_dir}/vault.hcl", "w") as f:
        f.write(VAULT_CONFIG)

    # Write init script
    with open(f"{config_dir}/vault-init.sh", "w") as f:
        f.write(VAULT_INIT_SCRIPT)
    os.chmod(f"{config_dir}/vault-init.sh", 0o755)

    # Write Kubernetes deployment
    with open(f"{config_dir}/vault-k8s.yaml", "w") as f:
        f.write(VAULT_K8S_DEPLOYMENT)

    # Write Docker Compose
    with open(f"{config_dir}/docker-compose.yaml", "w") as f:
        f.write(DOCKER_COMPOSE_VAULT)

    # Write policy
    with open(f"{config_dir}/marty-msf.hcl", "w") as f:
        f.write(VAULT_POLICY)

    print(f"Vault configuration files written to {config_dir}/")
    print("To start Vault with Docker Compose:")
    print(f"  cd {config_dir} && docker-compose up -d")
    print("To deploy to Kubernetes:")
    print(f"  kubectl apply -f {config_dir}/vault-k8s.yaml")
