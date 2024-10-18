import boto3
import subprocess
import time

# Function to generate server and client keys using OpenSSL
def generate_keys():
    print("Generating server and client keys...")
    # Generate server key and certificate
    subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-out", "server.key", "-pkeyopt", "rsa_keygen_bits:2048"])
    subprocess.run(["openssl", "req", "-new", "-x509", "-key", "server.key", "-out", "server.crt", "-days", "365", "-subj", "/CN=vpn.example.com"])
    print("Server keys generated.")

    # Generate client key and certificate
    subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-out", "client.key", "-pkeyopt", "rsa_keygen_bits:2048"])
    subprocess.run(["openssl", "req", "-new", "-key", "client.key", "-out", "client.csr", "-subj", "/CN=vpn-client.example.com"])
    subprocess.run(["openssl", "x509", "-req", "-in", "client.csr", "-CA", "server.crt", "-CAkey", "server.key", "-CAcreateserial", "-out", "client.crt", "-days", "365"])
    print("Client keys generated.")

# Function to upload keys to ACM
def upload_to_acm(cert_file, key_file):
    print("Uploading keys to ACM...")
    acm = boto3.client('acm')
    with open(cert_file, 'r') as cert, open(key_file, 'r') as key:
        response = acm.import_certificate(
            Certificate=cert.read(),
            PrivateKey=key.read(),
        )
    print(f"Certificate uploaded to ACM with ARN: {response['CertificateArn']}")
    return response['CertificateArn']

# Function to get default VPC and associated subnets
def get_default_vpc_and_subnets():
    print("Getting default VPC and associated subnets...")
    ec2 = boto3.client('ec2')
    
    # Get default VPC
    response = ec2.describe_vpcs(
        Filters=[{'Name': 'isDefault', 'Values': ['true']}]
    )
    vpc_id = response['Vpcs'][0]['VpcId']
    vpc_cidr_block = response['Vpcs'][0]['CidrBlock']
    print(f"Default VPC obtained: {vpc_id}, CIDR: {vpc_cidr_block}")

    # Get subnets associated with the default VPC
    response = ec2.describe_subnets(
        Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
    )
    
    subnets = [subnet['SubnetId'] for subnet in response['Subnets']]
    print(f"Subnets obtained: {subnets}")
    
    return vpc_id, subnets, vpc_cidr_block

# Function to check if the Security Group already exists
def find_security_group(vpc_id, group_name):
    print(f"Checking if Security Group {group_name} already exists in VPC {vpc_id}...")
    ec2 = boto3.client('ec2')
    response = ec2.describe_security_groups(
        Filters=[
            {'Name': 'group-name', 'Values': [group_name]},
            {'Name': 'vpc-id', 'Values': [vpc_id]}
        ]
    )
    if response['SecurityGroups']:
        print(f"Security Group {group_name} found with ID: {response['SecurityGroups'][0]['GroupId']}")
        return response['SecurityGroups'][0]['GroupId']
    print(f"Security Group {group_name} not found.")
    return None

# Function to create a Security Group open to all traffic
def create_security_group(vpc_id):
    ec2 = boto3.client('ec2')
    group_name = 'ClientVPN-SG'
    
    # Check if the Security Group already exists
    security_group_id = find_security_group(vpc_id, group_name)
    
    if security_group_id:
        return security_group_id

    print(f"Creating new Security Group {group_name}...")
    response = ec2.create_security_group(
        GroupName=group_name,
        Description='Security Group for Client VPN, open to all traffic',
        VpcId=vpc_id
    )

    security_group_id = response['GroupId']
    print(f"Security Group {group_name} created with ID: {security_group_id}")

    # Add rule to allow all traffic (inbound)
    print(f"Adding traffic rules to Security Group {security_group_id}...")
    ec2.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            {
                'IpProtocol': '-1',
                'FromPort': -1,
                'ToPort': -1,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
            }
        ]
    )
    print("Traffic rules added.")
    return security_group_id

# Function to create CloudWatch log group
def create_cloudwatch_log_group(log_group_name):
    logs = boto3.client('logs')

    try:
        logs.create_log_group(logGroupName=log_group_name)
        print(f"Log group {log_group_name} created successfully.")
    except logs.exceptions.ResourceAlreadyExistsException:
        print(f"Log group {log_group_name} already exists.")

# Function to create CloudWatch log stream
def create_cloudwatch_log_stream(log_group_name, log_stream_name):
    logs = boto3.client('logs')

    try:
        logs.create_log_stream(
            logGroupName=log_group_name,
            logStreamName=log_stream_name
        )
        print(f"Log stream {log_stream_name} created successfully in group {log_group_name}.")
    except logs.exceptions.ResourceAlreadyExistsException:
        print(f"Log stream {log_stream_name} already exists in group {log_group_name}.")

# Function to create the Client VPN
def create_client_vpn(acm_arn, vpc_id, subnets, security_group_id):
    ec2 = boto3.client('ec2')
    log_group_name = '/aws/vpn/log'
    log_stream_name = 'vpn-stream'
    
    # Create the CloudWatch log group if it doesn't exist
    create_cloudwatch_log_group(log_group_name)

    # Create the log stream in the log group
    create_cloudwatch_log_stream(log_group_name, log_stream_name)

    print("Creating Client VPN...")
    response = ec2.create_client_vpn_endpoint(
        ClientCidrBlock='10.0.0.0/16',
        ServerCertificateArn=acm_arn,
        AuthenticationOptions=[
            {
                'Type': 'certificate-authentication',
                'MutualAuthentication': {
                    'ClientRootCertificateChainArn': acm_arn
                }
            }
        ],
        ConnectionLogOptions={
            'Enabled': True,
            'CloudwatchLogGroup': log_group_name,
            'CloudwatchLogStream': log_stream_name
        },
        VpcId=vpc_id,
        SecurityGroupIds=[security_group_id]
    )

    vpn_endpoint_id = response['ClientVpnEndpointId']
    print(f"Client VPN created with ID: {vpn_endpoint_id}")

    # Associate subnets
    for subnet in subnets:
        print(f"Associating subnet {subnet} with Client VPN {vpn_endpoint_id}...")
        ec2.associate_client_vpn_target_network(
            ClientVpnEndpointId=vpn_endpoint_id,
            SubnetId=subnet
        )
        time.sleep(5)  # Small pause between associations
    print(f"Subnets associated with Client VPN {vpn_endpoint_id}.")
    return vpn_endpoint_id

# Function to add an Authorization Rule for the VPC CIDR block
def authorize_vpn_cidr(vpn_endpoint_id, vpc_cidr_block):
    print(f"Adding Authorization Rule for CIDR {vpc_cidr_block} on VPN {vpn_endpoint_id}...")
    ec2 = boto3.client('ec2')

    # Parameters for rule authorization without AccessGroupId
    params = {
        'ClientVpnEndpointId': vpn_endpoint_id,
        'TargetNetworkCidr': vpc_cidr_block,
        'AuthorizeAllGroups': True  # Authorize all groups
    }

    # Call the API without AccessGroupId
    response = ec2.authorize_client_vpn_ingress(**params)
    
    print(f"Authorization Rule added for CIDR {vpc_cidr_block}.")

# Function to add internet routes to all subnets
def add_internet_routes(vpn_endpoint_id, subnets):
    ec2 = boto3.client('ec2')
    print(f"Adding internet routes to all subnets for VPN {vpn_endpoint_id}...")
    for subnet in subnets:
        ec2.create_client_vpn_route(
            ClientVpnEndpointId=vpn_endpoint_id,
            DestinationCidrBlock='0.0.0.0/0',  # Internet traffic
            TargetVpcSubnetId=subnet
        )
        print(f"Internet route added for subnet {subnet}")
        time.sleep(10)  # Add a pause to avoid hitting the concurrent mutation limit
    print(f"Internet routes added for all subnets.")

# Function to get connection report
def get_connection_report(vpn_endpoint_id):
    print(f"Getting connection report for VPN {vpn_endpoint_id}...")
    ec2 = boto3.client('ec2')
    response = ec2.describe_client_vpn_connections(
        ClientVpnEndpointId=vpn_endpoint_id
    )

    report = []
    for connection in response['Connections']:
        report.append({
            'Username': connection['Username'],
            'ConnectionStartTime': connection['ConnectionStartTime'],
            'ConnectionEndTime': connection.get('ConnectionEndTime', 'Active'),
            'Status': connection['Status']['Code']
        })

    return report

def main():
    # Generate keys
    generate_keys()

    # Upload keys to ACM
    server_cert_arn = upload_to_acm('server.crt', 'server.key')

    # Get the default VPC, associated subnets, and CIDR block
    vpc_id, subnets, vpc_cidr_block = get_default_vpc_and_subnets()

    # Create or reuse Security Group open to all traffic
    security_group_id = create_security_group(vpc_id)

    # Create the VPN
    vpn_endpoint_id = create_client_vpn(server_cert_arn, vpc_id, subnets, security_group_id)

    # Add Authorization Rule for VPC CIDR block
    authorize_vpn_cidr(vpn_endpoint_id, vpc_cidr_block)

    # Add internet routes for all subnets
    add_internet_routes(vpn_endpoint_id, subnets)

    # Generate connection report
    report = get_connection_report(vpn_endpoint_id)

    print("Connection Report:")
    for r in report:
        print(r)

if __name__ == "__main__":
    main()


