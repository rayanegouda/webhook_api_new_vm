# webhook_api_new_vm
curl -X POST https://webhook-api-new-vm.onrender.com/create-connection \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "12.34.56.78",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEArf0...END RSA PRIVATE KEY-----",
    "connection_protocol": "ssh",
    "connection_name": "SSH - 12.34.56.78"
  }'
