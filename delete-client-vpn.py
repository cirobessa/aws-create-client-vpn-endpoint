import boto3
import time

# Function to disassociate target networks (subnets) from the Client VPN
def disassociate_target_networks(vpn_endpoint_id):
    ec2 = boto3.client('ec2')
    
    # Get the current associations for the VPN endpoint
    response = ec2.describe_client_vpn_target_networks(
        ClientVpnEndpointId=vpn_endpoint_id
    )
    
    associations = response.get('ClientVpnTargetNetworks', [])
    
    if not associations:
        print(f"No target networks found for VPN {vpn_endpoint_id}.")
        return
    
    # Disassociate each target network
    for association in associations:
        association_id = association['AssociationId']
        subnet_id = association['TargetNetworkId']
        print(f"Disassociating subnet {subnet_id} (Association ID: {association_id}) from VPN {vpn_endpoint_id}...")
        ec2.disassociate_client_vpn_target_network(
            ClientVpnEndpointId=vpn_endpoint_id,
            AssociationId=association_id
        )
        time.sleep(5)  # Small pause to avoid rate limits
        print(f"Subnet {subnet_id} disassociated.")

# Function to delete the Client VPN
def delete_client_vpn(vpn_endpoint_id):
    ec2 = boto3.client('ec2')
    print(f"Deleting Client VPN with ID: {vpn_endpoint_id}...")
    
    # Delete the Client VPN endpoint
    ec2.delete_client_vpn_endpoint(ClientVpnEndpointId=vpn_endpoint_id)
    
    print(f"Client VPN {vpn_endpoint_id} deleted successfully.")

def main():
    vpn_endpoint_id = input("Enter the VPN Endpoint ID to delete: ")
    
    # Step 1: Disassociate target networks
    disassociate_target_networks(vpn_endpoint_id)
    
    # Step 2: Delete the Client VPN
    delete_client_vpn(vpn_endpoint_id)

if __name__ == "__main__":
    main()

