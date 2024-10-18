import boto3
from botocore.exceptions import ClientError
import time

# Definir variáveis da VPN e do usuário
customer_gateway_ip = '203.0.113.12'  # IP público do gateway do cliente
vpn_name = 'User-VPN'

# Função para pegar o ID da VPC default
def get_default_vpc_id():
    ec2 = boto3.client('ec2')
    try:
        response = ec2.describe_vpcs(
            Filters=[{'Name': 'isDefault', 'Values': ['true']}]
        )
        vpc_id = response['Vpcs'][0]['VpcId']
        print(f"Default VPC ID: {vpc_id}")
        return vpc_id
    except ClientError as e:
        print(f"Error retrieving default VPC: {e}")
        return None

# Função para criar o Customer Gateway (com ASN diferente para evitar conflito)
def create_customer_gateway():
    ec2 = boto3.client('ec2')
    try:
        response = ec2.create_customer_gateway(
            BgpAsn=64512,  # ASN alterado para evitar conflito com o VPN Gateway
            PublicIp=customer_gateway_ip,
            Type='ipsec.1'
        )
        customer_gateway_id = response['CustomerGateway']['CustomerGatewayId']
        print(f"Customer Gateway created: {customer_gateway_id}")
        return customer_gateway_id
    except ClientError as e:
        print(f"Error creating Customer Gateway: {e}")
        return None

# Função para criar o VPN Gateway
def create_vpn_gateway():
    ec2 = boto3.client('ec2')
    try:
        response = ec2.create_vpn_gateway(
            Type='ipsec.1',
            AmazonSideAsn=65000  # Mantido o ASN padrão do VPN Gateway
        )
        vpn_gateway_id = response['VpnGateway']['VpnGatewayId']
        print(f"VPN Gateway created: {vpn_gateway_id}")
        return vpn_gateway_id
    except ClientError as e:
        print(f"Error creating VPN Gateway: {e}")
        return None

# Função para associar o VPN Gateway à VPC
def attach_vpn_gateway(vpn_gateway_id, vpc_id):
    ec2 = boto3.client('ec2')
    try:
        ec2.attach_vpn_gateway(
            VpnGatewayId=vpn_gateway_id,
            VpcId=vpc_id
        )
        print(f"VPN Gateway {vpn_gateway_id} attached to VPC {vpc_id}")
    except ClientError as e:
        print(f"Error attaching VPN Gateway to VPC: {e}")

# Função para aguardar manualmente o estado "available" do VPN Gateway
def wait_for_vpn_gateway(vpn_gateway_id):
    ec2 = boto3.client('ec2')
    try:
        while True:
            response = ec2.describe_vpn_gateways(VpnGatewayIds=[vpn_gateway_id])
            state = response['VpnGateways'][0]['State']
            if state == 'available':
                print(f"VPN Gateway {vpn_gateway_id} is now available.")
                break
            print(f"Waiting for VPN Gateway {vpn_gateway_id} to become available (current state: {state})...")
            time.sleep(10)  # Espera 10 segundos antes de verificar novamente
    except ClientError as e:
        print(f"Error waiting for VPN Gateway to become available: {e}")

# Função para desanexar o VPN Gateway existente
def detach_existing_vpn_gateway(vpc_id):
    ec2 = boto3.client('ec2')
    try:
        response = ec2.describe_vpn_gateways(
            Filters=[
                {'Name': 'attachment.vpc-id', 'Values': [vpc_id]},
                {'Name': 'attachment.state', 'Values': ['attached']}
            ]
        )
        if response['VpnGateways']:
            vpn_gateway_id = response['VpnGateways'][0]['VpnGatewayId']
            print(f"Detaching VPN Gateway {vpn_gateway_id} from VPC {vpc_id}")
            ec2.detach_vpn_gateway(VpnGatewayId=vpn_gateway_id, VpcId=vpc_id)
        else:
            print(f"No VPN Gateway attached to VPC {vpc_id}")
    except ClientError as e:
        print(f"Error detaching VPN Gateway: {e}")

# Função para criar a VPN Connection
def create_vpn_connection(customer_gateway_id, vpn_gateway_id):
    ec2 = boto3.client('ec2')
    try:
        response = ec2.create_vpn_connection(
            CustomerGatewayId=customer_gateway_id,
            Type='ipsec.1',
            VpnGatewayId=vpn_gateway_id,
            Options={
                'StaticRoutesOnly': False
            }
        )
        vpn_connection_id = response['VpnConnection']['VpnConnectionId']
        print(f"VPN Connection created: {vpn_connection_id}")
        return response['VpnConnection']
    except ClientError as e:
        print(f"Error creating VPN: {e}")
        return None

# Função para exibir os dados da VPN
def display_vpn_details(vpn_connection, customer_gateway_id, vpn_gateway_id):
    print(f"\n=== VPN Connection Details ===\n"
          f"VPN Connection ID: {vpn_connection['VpnConnectionId']}\n"
          f"Customer Gateway ID: {customer_gateway_id}\n"
          f"VPN Gateway ID: {vpn_gateway_id}\n"
          f"Customer Gateway IP: {customer_gateway_ip}\n"
          "===============================\n")

# Execução do processo
def main():
    vpc_id = get_default_vpc_id()
    if vpc_id:
        detach_existing_vpn_gateway(vpc_id)  # Desanexa o VPN Gateway existente, se houver
        customer_gateway_id = create_customer_gateway()
        vpn_gateway_id = create_vpn_gateway()
        if customer_gateway_id and vpn_gateway_id:
            wait_for_vpn_gateway(vpn_gateway_id)
            attach_vpn_gateway(vpn_gateway_id, vpc_id)
            vpn_details = create_vpn_connection(customer_gateway_id, vpn_gateway_id)
            if vpn_details:
                display_vpn_details(vpn_details, customer_gateway_id, vpn_gateway_id)

if __name__ == '__main__':
    main()


