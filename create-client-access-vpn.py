import boto3
import os

# Nome dos arquivos de chave e certificado
client_cert_file = "client.crt"
client_key_file = "client.key"
ca_cert_file = "server.crt"

# Função para baixar o arquivo .ovpn da AWS
def download_ovpn(vpn_endpoint_id, output_file):
    ec2 = boto3.client('ec2')
    
    print(f"Downloading .ovpn configuration for VPN Endpoint ID: {vpn_endpoint_id}...")
    response = ec2.export_client_vpn_client_configuration(
        ClientVpnEndpointId=vpn_endpoint_id
    )
    
    ovpn_content = response['ClientConfiguration']
    
    with open(output_file, 'w') as file:
        file.write(ovpn_content)
    
    print(f".ovpn configuration downloaded to {output_file}")

# Função para inserir certificados e chaves no arquivo .ovpn
def insert_certificates_into_ovpn(ovpn_file):
    # Ler o conteúdo do arquivo .ovpn baixado
    with open(ovpn_file, 'r') as file:
        ovpn_content = file.read()

    # Verificar se os arquivos de certificado e chave estão disponíveis
    if not (os.path.exists(client_cert_file) and os.path.exists(client_key_file) and os.path.exists(ca_cert_file)):
        print("Error: Missing one or more certificate/key files.")
        return

    # Ler os arquivos de certificado e chave
    with open(client_cert_file, 'r') as client_cert:
        client_cert_content = client_cert.read()

    with open(client_key_file, 'r') as client_key:
        client_key_content = client_key.read()

    with open(ca_cert_file, 'r') as ca_cert:
        ca_cert_content = ca_cert.read()

    # Verificar e adicionar as seções de certificado e chave
    if '<ca>' not in ovpn_content:
        ovpn_content += f"\n<ca>\n{ca_cert_content}\n</ca>\n"
    else:
        ovpn_content = ovpn_content.replace('<ca></ca>', f'<ca>\n{ca_cert_content}\n</ca>')

    if '<cert>' not in ovpn_content:
        ovpn_content += f"\n<cert>\n{client_cert_content}\n</cert>\n"
    else:
        ovpn_content = ovpn_content.replace('<cert></cert>', f'<cert>\n{client_cert_content}\n</cert>')

    if '<key>' not in ovpn_content:
        ovpn_content += f"\n<key>\n{client_key_content}\n</key>\n"
    else:
        ovpn_content = ovpn_content.replace('<key></key>', f'<key>\n{client_key_content}\n</key>')

    # Salvar o arquivo .ovpn modificado
    with open(ovpn_file, 'w') as file:
        file.write(ovpn_content)

    print(f"Certificates and keys inserted into {ovpn_file}")

# Função principal para executar o processo
def main():
    vpn_endpoint_id = input("Enter the VPN Endpoint ID: ")
    output_file = "client_vpn_config.ovpn"

    # Step 1: Download the .ovpn file from AWS
    download_ovpn(vpn_endpoint_id, output_file)

    # Step 2: Insert the certificates and keys into the .ovpn file
    insert_certificates_into_ovpn(output_file)

    print(f"The VPN configuration file is ready: {output_file}")

if __name__ == "__main__":
    main()


